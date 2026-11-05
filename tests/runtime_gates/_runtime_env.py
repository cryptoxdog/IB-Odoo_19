"""Mack-only, fail-closed Odoo runtime configuration for independent-session gates.

This is the missing import used by _mack_runtime.py and both Mack gates.
Do not route these destructive test fixtures to an unknown or production DB.
"""

from __future__ import annotations

import glob
import os
import re
from pathlib import Path

import psycopg2

DB = os.environ.get("SEAM_DB", "")
PG_HOST = os.environ.get("SEAM_PG_HOST", "/tmp")
PG_PORT = int(os.environ.get("SEAM_PG_PORT", "5433"))
PG_USER = os.environ.get("SEAM_PG_USER", "odoo")
_REPO = Path(__file__).resolve().parents[2]


def bind_config(config) -> None:
    """Bind one explicitly named local, owned disposable Mack database."""
    if re.fullmatch(r"odoo_test_mack_[a-z0-9_]{1,32}", DB) is None:
        raise SystemExit("Mack gates require explicit SEAM_DB=odoo_test_mack_<id>; no default DB")
    if PG_HOST not in ("localhost", "127.0.0.1") and not PG_HOST.startswith("/"):
        raise SystemExit("Mack gates require a local PostgreSQL socket or localhost")
    if not 1 <= PG_PORT <= 65535:
        raise SystemExit("Invalid SEAM_PG_PORT")
    specified_repo = Path(os.environ.get("SEAM_REPO", str(_REPO))).resolve()
    if specified_repo != _REPO:
        raise SystemExit("SEAM_REPO is not this Mack checkout")
    # Read the actual Postgres ownership marker before any gate writes fixtures.
    connection = psycopg2.connect(dbname=DB, host=PG_HOST, port=PG_PORT, user=PG_USER, connect_timeout=5)
    try:
        with connection.cursor() as cr:
            cr.execute(
                "SELECT coalesce(shobj_description(oid, 'pg_database'), '') "
                "FROM pg_database WHERE datname = current_database()"
            )
            row = cr.fetchone()
        marker = row[0] if row else ""
    finally:
        connection.close()
    if not (
        ("role=clone" in marker and "owner=" in marker) or ("mack_owned_disposable=1" in marker and "owner=" in marker)
    ):
        raise SystemExit("SEAM_DB is not an owner-marked disposable clone; no Mack gate will run")
    source_env = os.environ.get("SEAM_ODOO_SRC", "")
    if source_env:
        source = Path(source_env).resolve()
    else:
        matches = sorted(glob.glob("/opt/odoo-src/odoo-19.0*"))
        if not matches:
            raise SystemExit("Provide SEAM_ODOO_SRC (Odoo 19 checkout); no local source found")
        source = Path(matches[-1]).resolve()
    addons = source / "odoo" / "addons"
    if not addons.is_dir():
        raise SystemExit(f"Odoo 19 addons path not found: {addons}")
    config["db_host"] = PG_HOST
    config["db_port"] = PG_PORT
    config["db_user"] = PG_USER
    config["addons_path"] = f"{addons},{_REPO}"
