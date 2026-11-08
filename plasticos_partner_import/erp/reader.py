"""Minimal exact-format reader for the ERP source.

Scope
-----
Turn the authoritative ERP source into Python records. Nothing else.
This module performs **no** Odoo mapping, **no** fuzzy identity matching, and
**no** silent coercion of unknown values: a malformed payload raises
:class:`SourcePayloadError` rather than yielding a partial table.

Payload forms
-------------
ERP data enters through SQL (ADR-021). Three physical forms reach the same
:class:`SourcePayload`:

* ``PayloadKind.DATABASE`` — a direct read of the restored SQL Server database.
  Each source table is read by executing its projection script from
  ``plasticos_partner_import/erp_extracted_data/`` (:data:`PROJECTION_SCRIPTS`);
  those scripts are the extract authority, so the direct read and the grid
  extract they once produced carry the same columns, filters and ordering.
* ``PayloadKind.STATEMENTS`` — ``INSERT INTO <table> (...) VALUES (...);``
  files under the same folder.
* ``PayloadKind.GRID`` — the frozen 2026-08-07 grid extract under ``bulk/``.
  It is a regression and comparison fixture, not runtime authority.

Value fidelity
--------------
Cell values are kept as the source produced them:

* SQL ``NULL`` (the ``NULL`` token in a grid, ``None`` from the driver) becomes
  :data:`None`; an empty string stays ``""`` (both occur and mean different
  things);
* every other value is an exact :class:`str`, so no precision is lost before
  the mapping layer converts it explicitly. Driver-typed values are rendered
  the way the grid extract rendered them (``1``/``0`` for bits, decimals
  without trailing zeros, ``YYYY-MM-DD HH:MM:SS`` for datetimes).
"""

from __future__ import annotations

import csv
import os
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_PAYLOAD_ROOT",
    "GRID_PAYLOAD_ROOT",
    "SQL_PAYLOAD_ROOT",
    "SOURCE_TABLES",
    "PROJECTION_SCRIPTS",
    "DatabaseSource",
    "PayloadKind",
    "SourcePayload",
    "SourcePayloadError",
    "PARTNER_SOURCE_TABLES",
    "database_source_from_env",
    "load_payload",
    "payload_root",
]

# Projection scripts, INSERT statement files, and the frozen grid all live here.
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
    "SalesReps": "SalesReps.csv",
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

# Partner proof. These files are the company, its locations, its people, their
# role tags, and the company's Salesperson. Deal files are not part of that proof.
PARTNER_SOURCE_TABLES: frozenset[str] = frozenset(
    {"CounterParty", "Address", "Contact", "ContactRoleAssignment", "SalesReps"}
)

# The SELECT definition the direct database read executes for each source table.
# Partner tables are Concern 1. The six deal tables are the Concern 2A
# reconstruction inputs. ReceiptBatch and WksDelivery are the same SELECTs as
# 05_extract_all.sql, split out because that file returns several result sets.
PROJECTION_SCRIPTS: dict[str, str] = {
    "CounterParty": "10_counterparty.sql",
    "Address": "11_address.sql",
    "Contact": "12_contact.sql",
    "Payables": "13_payables.sql",
    "Receipt": "14_receipt.sql",
    "GPLedger": "15_gpledger.sql",
    "WKSDetail": "16_wksdetail.sql",
    "ContactRoleAssignment": "18_contactroleassignment.sql",
    "SalesReps": "19_salesreps.sql",
    "ReceiptBatch": "20_receiptbatch.sql",
    "WksDelivery": "21_wksdelivery.sql",
    "PO": "22_po.sql",
    "PODetail": "23_podetail.sql",
    "BuySell": "24_buysell.sql",
    "PayablesBatch": "25_payablesbatch.sql",
}

# Direct-SQL tables a full import reads in addition to the grid-backed set.
# They are not part of REQUIRED_TABLES: the frozen grid has no extract for them,
# and a partners-only run must not open them.
COMMERCIAL_SQL_TABLES: frozenset[str] = frozenset({"PO", "PODetail", "BuySell", "PayablesBatch"})

# The literal SQL Server emits for NULL in these grids. An empty cell is a real
# empty string and is deliberately NOT folded into this.
SQL_NULL_LITERAL = "NULL"

# Environment names the direct database read binds. The password is never
# echoed, logged, or carried on the payload.
ENV_SQL_SERVER = "ERP_SQL_SERVER"
ENV_SQL_DATABASE = "ERP_SQL_DATABASE"
ENV_SQL_USER = "ERP_SQL_USER"
ENV_SQL_CREDENTIAL = "ERP_SQL_PASSWORD"  # the environment variable name; the value is never stored here
ENV_SQL_PORT = "ERP_SQL_PORT"
ENV_SQL_DRIVER = "ERP_SQL_DRIVER"
ENV_SQL_ODBC_DRIVER = "ERP_SQL_ODBC_DRIVER"
DEFAULT_SQL_PORT = 1433
DEFAULT_ODBC_DRIVER = "ODBC Driver 18 for SQL Server"
SUPPORTED_SQL_DRIVERS = ("pymssql", "pyodbc")

_INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+(?:\[?dbo\]?\.)?\[?(?P<table>\w+)\]?\s*\((?P<cols>[^)]*)\)\s*VALUES\s*(?P<rows>.*?);",
    re.IGNORECASE | re.DOTALL,
)


class SourcePayloadError(RuntimeError):
    """The ERP payload is absent, incomplete, malformed, or unreachable."""


class PayloadKind(StrEnum):
    """Which physical form the authoritative payload was found in."""

    DATABASE = "database"
    STATEMENTS = "statements"
    GRID = "grid"


@dataclass(frozen=True)
class SourcePayload:
    """Reconstructed source rows, grouped by ERP table name."""

    kind: PayloadKind
    root: Path
    tables: dict[str, list[dict[str, str | None]]] = field(default_factory=dict)
    # Where the rows came from, for reports. Never a credential.
    origin: str = ""

    def rows(self, table: str) -> list[dict[str, str | None]]:
        """Rows of ``table``, or raise when the payload does not carry it."""
        try:
            return self.tables[table]
        except KeyError as exc:
            raise SourcePayloadError(f"source table {table!r} is not present in payload at {self.root}") from exc

    def row_counts(self) -> dict[str, int]:
        return {name: len(rows) for name, rows in sorted(self.tables.items())}


@dataclass(frozen=True)
class DatabaseSource:
    """A direct read of the restored ERP database.

    ``connect`` returns a DB-API 2.0 connection. ``label`` names the target for
    reports (``server/database``) and must never carry a credential.
    """

    connect: Callable[[], Any]
    label: str


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
    """Absolute path of the projection scripts and statement files."""
    if repo_root is None:
        repo_root = _repo_root()
    return Path(repo_root) / SQL_PAYLOAD_ROOT


def database_source_from_env(environ: Mapping[str, str] | None = None) -> DatabaseSource | None:
    """The direct database read the environment asks for, or ``None``.

    ``ERP_SQL_SERVER`` and ``ERP_SQL_DATABASE`` together select the direct
    read. ``ERP_SQL_USER`` / ``ERP_SQL_PASSWORD`` are SQL authentication;
    without them the pyodbc driver uses the caller's Windows login.
    ``ERP_SQL_DRIVER`` is ``pymssql`` (default, no system ODBC driver needed)
    or ``pyodbc`` (``ERP_SQL_ODBC_DRIVER`` names the installed ODBC driver).
    The driver module is imported only when the connection is opened, so the
    grid and statement forms never need it installed.
    """
    env = os.environ if environ is None else environ
    server = (env.get(ENV_SQL_SERVER) or "").strip()
    database = (env.get(ENV_SQL_DATABASE) or "").strip()
    if not server and not database:
        return None
    if not server or not database:
        raise SourcePayloadError(f"{ENV_SQL_SERVER} and {ENV_SQL_DATABASE} must both be set for a direct database read")
    user = (env.get(ENV_SQL_USER) or "").strip()
    password = env.get(ENV_SQL_CREDENTIAL) or ""
    port_raw = (env.get(ENV_SQL_PORT) or "").strip()
    if port_raw and not port_raw.isdigit():
        raise SourcePayloadError(f"{ENV_SQL_PORT} must be a port number, got {port_raw!r}")
    port = int(port_raw) if port_raw else DEFAULT_SQL_PORT
    driver = (env.get(ENV_SQL_DRIVER) or SUPPORTED_SQL_DRIVERS[0]).strip().lower()
    if driver not in SUPPORTED_SQL_DRIVERS:
        raise SourcePayloadError(f"{ENV_SQL_DRIVER} must be one of {', '.join(SUPPORTED_SQL_DRIVERS)}, got {driver!r}")
    odbc_driver = (env.get(ENV_SQL_ODBC_DRIVER) or DEFAULT_ODBC_DRIVER).strip()

    def connect() -> Any:
        if driver == "pymssql":
            try:
                import pymssql  # noqa: PLC0415 - driver is optional until a direct read is requested
            except ImportError as exc:
                raise SourcePayloadError("direct database read needs the pymssql driver (pip install pymssql)") from exc
            return pymssql.connect(
                server=server,
                port=str(port),
                user=user or None,
                password=password or None,
                database=database,
                as_dict=False,
            )
        try:
            import pyodbc  # noqa: PLC0415 - driver is optional until a direct read is requested
        except ImportError as exc:
            raise SourcePayloadError("direct database read needs the pyodbc driver (pip install pyodbc)") from exc
        parts = [
            f"DRIVER={{{odbc_driver}}}",
            f"SERVER={server},{port}",
            f"DATABASE={database}",
            "TrustServerCertificate=yes",
        ]
        if user:
            parts.append(f"UID={user}")
            parts.append(f"PWD={password}")
        else:
            parts.append("Trusted_Connection=yes")
        return pyodbc.connect(";".join(parts))

    return DatabaseSource(connect=connect, label=f"{server}/{database}")


def load_payload(
    root: Path | str | None = None,
    *,
    only: frozenset[str] | None = None,
    database: DatabaseSource | None = None,
) -> SourcePayload:
    """Load the authoritative payload.

    ``database`` wins: the requested tables are read directly from the restored
    ERP database through their projection scripts. Otherwise, with no ``root``,
    statement files are read from ``plasticos_partner_import/erp_extracted_data``
    and an empty statement result (the checked-in ``SELECT`` scripts) falls back
    to the frozen grid pack. An explicit ``root`` is searched for both file
    shapes, which is what tests and ``ERP_PAYLOAD_ROOT`` use.

    ``only`` limits the read to those source tables. The partner proof passes
    :data:`PARTNER_SOURCE_TABLES` so the deal files are not opened.

    Raises:
        SourcePayloadError: the source is missing or unreachable, a required
            source table has no extract or projection, or an extract is
            malformed.
    """
    required = only if only is not None else REQUIRED_TABLES
    if database is not None:
        tables = _read_database_payload(database, required, sql_payload_root())
        _require_complete(sql_payload_root(), tables, required)
        return SourcePayload(kind=PayloadKind.DATABASE, root=sql_payload_root(), tables=tables, origin=database.label)
    if root is not None:
        return _load_single_root(Path(root), required)

    sql_base = sql_payload_root()
    tables = _read_statement_payload(sql_base, required) if sql_base.is_dir() else {}
    if tables:
        _require_complete(sql_base, tables, required)
        return SourcePayload(kind=PayloadKind.STATEMENTS, root=sql_base, tables=tables, origin=str(sql_base))
    return _load_single_root(payload_root(), required)


def _load_single_root(base: Path, required: frozenset[str]) -> SourcePayload:
    if not base.is_dir():
        raise SourcePayloadError(f"ERP payload root not found: {base}")

    tables = _read_statement_payload(base, required)
    kind = PayloadKind.STATEMENTS
    if not tables:
        tables = _read_grid_payload(base, required)
        kind = PayloadKind.GRID
    _require_complete(base, tables, required)
    return SourcePayload(kind=kind, root=base, tables=tables, origin=str(base))


def _require_complete(base: Path, tables: dict[str, list[dict[str, str | None]]], required: frozenset[str]) -> None:
    missing = sorted(required - set(tables))
    if missing:
        raise SourcePayloadError(f"payload at {base} is incomplete; missing source tables: {', '.join(missing)}")


# ---------------------------------------------------------------------------
# Direct database read (the ADR-021 target form)
# ---------------------------------------------------------------------------
def _read_database_payload(
    source: DatabaseSource, required: frozenset[str], scripts_root: Path
) -> dict[str, list[dict[str, str | None]]]:
    """Execute each required table's projection script on one connection."""
    unsupported = sorted(required - set(PROJECTION_SCRIPTS))
    if unsupported:
        raise SourcePayloadError("no projection script for: " + ", ".join(unsupported))
    try:
        connection = source.connect()
    except SourcePayloadError:
        raise
    except Exception as exc:  # noqa: BLE001 - every driver has its own exception hierarchy
        raise SourcePayloadError(f"cannot connect to ERP database {source.label}: {type(exc).__name__}") from exc

    tables: dict[str, list[dict[str, str | None]]] = {}
    try:
        for table in sorted(required):
            script = scripts_root / PROJECTION_SCRIPTS[table]
            if not script.is_file():
                raise SourcePayloadError(f"projection script missing for {table}: {script}")
            cursor = connection.cursor()
            try:
                cursor.execute(script.read_text(encoding="utf-8-sig"))
                description = cursor.description or ()
                columns = [str(column[0]).strip() for column in description]
                if not columns:
                    raise SourcePayloadError(f"{script.name}: projection for {table} returned no columns")
                rows: list[dict[str, str | None]] = []
                for raw in cursor.fetchall():
                    if len(raw) != len(columns):
                        raise SourcePayloadError(
                            f"{script.name}: {table} row has {len(raw)} values, projection declares {len(columns)}"
                        )
                    rows.append({column: _database_value(value) for column, value in zip(columns, raw)})
            finally:
                close = getattr(cursor, "close", None)
                if callable(close):
                    close()
            tables[table] = rows
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()
    return tables


def _database_value(value: Any) -> str | None:
    """Render a driver-typed value exactly the way the grid extract did.

    ``None`` stays ``None`` (SQL NULL). Strings are untouched, padding and
    all, so RTRIM decisions stay in the projection scripts.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return _plain_decimal(value)
    if isinstance(value, float):
        return _plain_decimal(Decimal(repr(value)))
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, bytes | bytearray | memoryview):
        return bytes(value).decode("utf-8", errors="replace")
    return str(value)


def _plain_decimal(value: Decimal) -> str:
    if value.is_nan() or value.is_infinite():
        return str(value)
    text = format(value.normalize(), "f")
    return "0" if text in {"-0", "0.0"} else text


# ---------------------------------------------------------------------------
# Grid extracts (the frozen regression fixture)
# ---------------------------------------------------------------------------
def _read_grid_payload(base: Path, required: frozenset[str]) -> dict[str, list[dict[str, str | None]]]:
    bulk = base / "bulk"
    if not bulk.is_dir():
        return {}

    tables: dict[str, list[dict[str, str | None]]] = {}
    for table, filename in SOURCE_TABLES.items():
        if table not in required:
            continue
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
# Statement payload (an INSERT-bearing extract)
# ---------------------------------------------------------------------------
def _read_statement_payload(
    base: Path, required: frozenset[str] = REQUIRED_TABLES
) -> dict[str, list[dict[str, str | None]]]:
    tables: dict[str, list[dict[str, str | None]]] = {}
    for path in sorted(base.rglob("*.sql")):
        text = path.read_text(encoding="utf-8-sig", errors="strict")
        for match in _INSERT_RE.finditer(text):
            table = match.group("table")
            if table not in required:
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
