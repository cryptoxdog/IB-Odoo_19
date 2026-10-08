"""Disposable scratch-database lifecycle for the ERP runtime gate.

``create_scratch_database`` and ``drop_scratch_database`` are the only places
that may DROP or CREATE the gate database. Both call
``require_disposable_scratch`` before opening a connection and before
importing the SQL adapter, so a refused identity never reaches a destructive
statement.

A database is disposable only when all of the following hold:

- both names are syntactic PostgreSQL identifiers
- ``ODOO_STAGE`` is not production
- the scratch name is not a PostgreSQL system database
- the scratch name does not identify as production
- the scratch name is not the template it would be cloned from
- the scratch name is in the ``erp_import_gate`` namespace

Anything else raises ``SystemExit`` (exit 1). That is a refusal, not a skip.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

# Database identifiers cannot be bound parameters. This alphabet is necessary
# and not sufficient: a production database can still be a legal identifier.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_\-]{0,62}$")
# The only names this gate may drop or create. A suffix lets a parallel proof
# use erp_import_gate_<token> without ever naming a real database.
_DISPOSABLE_RE = re.compile(r"^erp_import_gate(?:_[A-Za-z0-9][A-Za-z0-9_]*)?$")
_PRODUCTION_MARKERS = ("production", "prod")
_SYSTEM_DATABASES = frozenset({"postgres", "template0", "template1"})
_PRODUCTION_STAGE = "production"


def require_disposable_scratch(scratch: str, template: str, *, stage: str = "") -> tuple[str, str]:
    """Return ``(scratch, template)`` only when scratch may be dropped or created.

    Raises ``SystemExit`` before the caller may open a connection or build SQL.
    """
    scratch_name = scratch if isinstance(scratch, str) else ""
    template_name = template if isinstance(template, str) else ""
    if not _IDENTIFIER_RE.match(scratch_name):
        raise SystemExit(f"L9_ODOO_ERP_GATE_DB {scratch!r} is not a safe database identifier")
    if not _IDENTIFIER_RE.match(template_name):
        raise SystemExit(f"L9_ODOO_TEMPLATE_DB {template!r} is not a safe database identifier")
    stage_name = (stage if isinstance(stage, str) else "").strip().lower()
    if stage_name == _PRODUCTION_STAGE:
        raise SystemExit("ODOO_STAGE=production: the ERP runtime gate never drops or creates a database")
    lowered = scratch_name.lower()
    if lowered in _SYSTEM_DATABASES:
        raise SystemExit(f"refusing to drop or create system database {scratch_name!r}")
    if any(marker in lowered for marker in _PRODUCTION_MARKERS):
        raise SystemExit(f"refusing to drop or create {scratch_name!r}: it identifies as production")
    if lowered == template_name.lower():
        raise SystemExit(f"refusing to drop or create {scratch_name!r}: it is the template database")
    if not _DISPOSABLE_RE.match(scratch_name):
        raise SystemExit(f"refusing to drop or create {scratch_name!r}: only an erp_import_gate database is disposable")
    return scratch_name, template_name


def _open_maintenance(
    connect: Callable[[str], Any],
    scratch: str,
    template: str,
    *,
    stage: str,
) -> tuple[Any, str, str, Any]:
    """Open the maintenance connection only after the identity guard has passed."""
    scratch_name, template_name = require_disposable_scratch(scratch, template, stage=stage)
    from psycopg2 import sql as sql_mod

    conn = connect("postgres")
    conn.set_session(autocommit=True)
    return conn, scratch_name, template_name, sql_mod


def create_scratch_database(
    connect: Callable[[str], Any],
    scratch: str,
    template: str,
    *,
    stage: str = "",
) -> bool:
    """DROP and CREATE the scratch database from ``template``.

    Returns False when the template database is absent. A refused identity
    raises ``SystemExit`` and does not connect.
    """
    conn, scratch_name, template_name, sql_mod = _open_maintenance(connect, scratch, template, stage=stage)
    try:
        with conn.cursor() as cur:
            cur.execute("select 1 from pg_database where datname = %s", (template_name,))
            if not cur.fetchone():
                return False
            cur.execute(sql_mod.SQL("DROP DATABASE IF EXISTS {}").format(sql_mod.Identifier(scratch_name)))
            cur.execute(
                sql_mod.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                    sql_mod.Identifier(scratch_name),
                    sql_mod.Identifier(template_name),
                )
            )
        return True
    finally:
        conn.close()


def drop_scratch_database(
    connect: Callable[[str], Any],
    scratch: str,
    template: str,
    *,
    stage: str = "",
) -> None:
    """DROP the scratch database. A refused identity raises before any SQL."""
    conn, scratch_name, _template_name, sql_mod = _open_maintenance(connect, scratch, template, stage=stage)
    try:
        with conn.cursor() as cur:
            cur.execute(sql_mod.SQL("DROP DATABASE IF EXISTS {}").format(sql_mod.Identifier(scratch_name)))
    finally:
        conn.close()
