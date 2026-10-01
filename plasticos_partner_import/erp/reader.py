"""Minimal exact-format reader for the tracked ERP export.

Scope
-----
Turn the authoritative ERP source files into Python records. Nothing else.
This module performs **no** Odoo mapping, **no** fuzzy identity matching, and
**no** silent coercion of unknown values: a malformed payload raises
:class:`SourcePayloadError` rather than yielding a partial table.

Payload form
------------
Statement SQL lives in ``plasticos_partner_import/erp_extracted_data/``.
The scripts checked in there today are ``SELECT`` definitions and carry no
rows. :func:`load_payload` reads ``INSERT INTO … VALUES …`` from that folder
first. When that folder has no statement rows, it falls back to the frozen
grid extract under ``plasticos_partner_import/erp_extracted_data/bulk/``.

* ``PayloadKind.STATEMENTS`` — ``INSERT INTO <table> (...) VALUES (...);``
* ``PayloadKind.GRID`` — one delimited golden extract per source table

Value fidelity
--------------
Cell values are kept as the source produced them:

* the SQL ``NULL`` token becomes :data:`None`; an empty cell stays ``""``
  (both occur in this payload and mean different things);
* every other value stays an exact :class:`str`, so no precision is lost before
  the mapping layer converts it explicitly.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

__all__ = [
    "DEFAULT_PAYLOAD_ROOT",
    "GRID_PAYLOAD_ROOT",
    "SQL_PAYLOAD_ROOT",
    "SOURCE_TABLES",
    "PayloadKind",
    "SourcePayload",
    "SourcePayloadError",
    "load_payload",
    "payload_root",
]

# INSERT statement files. The checked-in scripts are SELECT definitions.
SQL_PAYLOAD_ROOT = Path("plasticos_partner_import/erp_extracted_data")
# Frozen grid extract produced by those scripts (2026-08-07).
GRID_PAYLOAD_ROOT = Path("plasticos_partner_import/erp_extracted_data")
# Alias used by mapping-status tests that read the grid pack.
DEFAULT_PAYLOAD_ROOT = GRID_PAYLOAD_ROOT

# Source tables this importer consumes, and the extract file that carries each.
# Keys are the ERP table names; they are the only names mappers may use.
SOURCE_TABLES: dict[str, str] = {
    "CounterParty": "CounterParty.csv",
    "Address": "Address.csv",
    "Contact": "Contact.csv",
    "ContactRoleAssignment": "ContactRoleAssignment.csv",
    "WKSDetail": "WKSDetail.csv",
    "GPLedger": "GPLedger.csv",
    "Payables": "Payables.csv",
    "Receipt": "Receipt.csv",
    "ReceiptBatch": "ReceiptBatch.csv",
    "WksDelivery": "WksDelivery.csv",
}

# Tables required for a complete import. A payload missing one of these cannot
# reconstruct the partner or transaction graph, so loading fails loudly.
REQUIRED_TABLES: frozenset[str] = frozenset(SOURCE_TABLES)

# The literal SQL Server emits for NULL in these grids. An empty cell is a real
# empty string and is deliberately NOT folded into this.
SQL_NULL_LITERAL = "NULL"

_INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+(?:\[?dbo\]?\.)?\[?(?P<table>\w+)\]?\s*\((?P<cols>[^)]*)\)\s*VALUES\s*(?P<rows>.*?);",
    re.IGNORECASE | re.DOTALL,
)


class SourcePayloadError(RuntimeError):
    """The ERP payload is absent, incomplete, or malformed."""


class PayloadKind(StrEnum):
    """Which physical form the authoritative payload was found in."""

    STATEMENTS = "statements"
    GRID = "grid"


@dataclass(frozen=True)
class SourcePayload:
    """Reconstructed source rows, grouped by ERP table name."""

    kind: PayloadKind
    root: Path
    tables: dict[str, list[dict[str, str | None]]] = field(default_factory=dict)

    def rows(self, table: str) -> list[dict[str, str | None]]:
        """Rows of ``table``, or raise when the payload does not carry it."""
        try:
            return self.tables[table]
        except KeyError as exc:
            raise SourcePayloadError(f"source table {table!r} is not present in payload at {self.root}") from exc

    def row_counts(self) -> dict[str, int]:
        return {name: len(rows) for name, rows in sorted(self.tables.items())}


def _repo_root() -> Path:
    # plasticos_partner_import/erp/reader.py -> repository root
    return Path(__file__).resolve().parents[2]


def payload_root(repo_root: Path | str | None = None) -> Path:
    """Absolute path of the frozen grid extract.

    ``repo_root`` defaults to the repository containing this file, so callers
    running inside Odoo do not have to know the checkout layout.
    """
    if repo_root is None:
        repo_root = _repo_root()
    return Path(repo_root) / GRID_PAYLOAD_ROOT


def sql_payload_root(repo_root: Path | str | None = None) -> Path:
    """Absolute path of the SQL statement home."""
    if repo_root is None:
        repo_root = _repo_root()
    return Path(repo_root) / SQL_PAYLOAD_ROOT


def load_payload(root: Path | str | None = None) -> SourcePayload:
    """Load the authoritative payload, preferring statements over grid extracts.

    With no ``root``, statement files are read from
    ``plasticos_partner_import/erp_extracted_data``. An empty statement result
    (the checked-in ``SELECT`` scripts) falls back to the frozen grid pack.
    An explicit ``root`` is searched for both shapes, which is what tests and
    ``ERP_PAYLOAD_ROOT`` use.

    Raises:
        SourcePayloadError: the pack is missing, or a required source table has
            no extract, or an extract is malformed.
    """
    if root is not None:
        return _load_single_root(Path(root))

    sql_base = sql_payload_root()
    tables = _read_statement_payload(sql_base) if sql_base.is_dir() else {}
    if tables:
        _require_complete(sql_base, tables)
        return SourcePayload(kind=PayloadKind.STATEMENTS, root=sql_base, tables=tables)
    return _load_single_root(payload_root())


def _load_single_root(base: Path) -> SourcePayload:
    if not base.is_dir():
        raise SourcePayloadError(f"ERP payload root not found: {base}")

    tables = _read_statement_payload(base)
    kind = PayloadKind.STATEMENTS
    if not tables:
        tables = _read_grid_payload(base)
        kind = PayloadKind.GRID
    _require_complete(base, tables)
    return SourcePayload(kind=kind, root=base, tables=tables)


def _require_complete(base: Path, tables: dict[str, list[dict[str, str | None]]]) -> None:
    missing = sorted(REQUIRED_TABLES - set(tables))
    if missing:
        raise SourcePayloadError(f"payload at {base} is incomplete; missing source tables: {', '.join(missing)}")


# ---------------------------------------------------------------------------
# Grid extracts (the form this repository actually tracks)
# ---------------------------------------------------------------------------
def _read_grid_payload(base: Path) -> dict[str, list[dict[str, str | None]]]:
    bulk = base / "bulk"
    if not bulk.is_dir():
        return {}

    tables: dict[str, list[dict[str, str | None]]] = {}
    for table, filename in SOURCE_TABLES.items():
        path = bulk / filename
        if not path.is_file():
            continue
        tables[table] = _read_grid_file(path, table)
    return tables


def _read_grid_file(path: Path, table: str) -> list[dict[str, str | None]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise SourcePayloadError(f"{path}: extract for {table} is empty") from exc

        columns = [col.strip() for col in header]
        if not columns or not columns[0]:
            raise SourcePayloadError(f"{path}: extract for {table} has no usable header")

        width = len(columns)
        rows: list[dict[str, str | None]] = []
        for line_no, raw in enumerate(reader, start=2):
            if not raw:
                continue
            if len(raw) != width:
                raise SourcePayloadError(f"{path}:{line_no}: {table} row has {len(raw)} cells, header declares {width}")
            rows.append({col: _normalize_cell(cell) for col, cell in zip(columns, raw)})
    return rows


def _normalize_cell(cell: str) -> str | None:
    """SQL ``NULL`` becomes ``None``; every other value is preserved verbatim."""
    return None if cell == SQL_NULL_LITERAL else cell


# ---------------------------------------------------------------------------
# Statement payload (supported so a future INSERT-bearing extract just works)
# ---------------------------------------------------------------------------
def _read_statement_payload(base: Path) -> dict[str, list[dict[str, str | None]]]:
    tables: dict[str, list[dict[str, str | None]]] = {}
    for path in sorted(base.rglob("*.sql")):
        text = path.read_text(encoding="utf-8-sig", errors="strict")
        for match in _INSERT_RE.finditer(text):
            table = match.group("table")
            if table not in SOURCE_TABLES:
                continue
            columns = [c.strip().strip("[]\"'") for c in match.group("cols").split(",")]
            for values in _split_value_tuples(match.group("rows"), path, table):
                if len(values) != len(columns):
                    raise SourcePayloadError(
                        f"{path}: malformed {table} row — {len(values)} values for {len(columns)} columns"
                    )
                tables.setdefault(table, []).append(dict(zip(columns, values)))
    return tables


def _split_value_tuples(blob: str, path: Path, table: str) -> Iterator[list[str | None]]:
    """Yield one value list per ``(...)`` tuple, honouring SQL quoting.

    A quoted literal is preserved exactly, whitespace included; an unquoted one
    is trimmed, and the bare ``NULL`` keyword becomes ``None``. The two are
    tracked separately so a quoted ``'NULL'`` stays the string it is.
    """
    values: list[str | None] = []
    token: list[str] = []
    quoted = False
    in_tuple = False
    in_string = False
    index = 0
    length = len(blob)

    while index < length:
        char = blob[index]
        if in_string:
            if char == "'":
                # '' inside a quoted literal is an escaped apostrophe.
                if index + 1 < length and blob[index + 1] == "'":
                    token.append("'")
                    index += 2
                    continue
                in_string = False
                index += 1
                continue
            token.append(char)
            index += 1
            continue

        if char == "'":
            # Whitespace between the separator and the opening quote is
            # formatting, not content, so the literal starts clean.
            in_string = True
            quoted = True
            token = []
            index += 1
            continue
        if char == "(" and not in_tuple:
            in_tuple = True
            values, token, quoted = [], [], False
            index += 1
            continue
        if in_tuple and char in ",)":
            values.append(_statement_value(token, quoted))
            token, quoted = [], False
            if char == ")":
                in_tuple = False
                yield values
            index += 1
            continue
        if in_tuple:
            token.append(char)
        index += 1

    if in_string or in_tuple:
        raise SourcePayloadError(f"{path}: unterminated INSERT literal for {table}")


def _statement_value(token: list[str], quoted: bool) -> str | None:
    raw = "".join(token)
    if quoted:
        return raw
    stripped = raw.strip()
    if stripped.upper() == SQL_NULL_LITERAL:
        return None
    return stripped
