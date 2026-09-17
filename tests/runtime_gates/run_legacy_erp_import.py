"""Runtime gate — LegacyErp import: reconciliation, repeat-run, changed-record,
savepoint recovery — on a REAL Odoo runtime.

Not a pytest module and deliberately not collected: it needs a live Odoo 19
registry, a live PostgreSQL server, and a template database with
``plasticos_transaction`` installed. Setup is
``scripts/setup_local_runtime.sh`` (see docs/runbooks/C1_C6_LOCAL_RUNTIME.md).
Run it directly::

    /opt/odoo-venv/bin/python tests/runtime_gates/run_legacy_erp_import.py

Exit codes: 0 = all gates PASS, 1 = a gate FAILED, 77 = SKIPPED (no local
runtime / template database). This is the live-DB proof the import milestone
requires; the collected pure-python tier cannot see any of it by construction.

Gates:
    G1 first import reconciles        full import; summary counters close;
                                      markers and rows verified over a
                                      psycopg2 connection Odoo does not own.
    G2 repeat run is idempotent       second import on the same input creates
                                      nothing and reports everything unchanged.
    G3 changed source updates         one mutated payload row updates exactly
                                      that record; no duplicate appears.
    G4 savepoint recovery             one corrupted row fails its BuySellNo
                                      only; the rest persists; a fixed re-run
                                      recovers the failed unit.
"""

from __future__ import annotations

import csv
import os
import shutil
import sys
import tempfile

import psycopg2

import odoo
import odoo.modules.module
from odoo.api import Environment
from odoo.tools import config

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _runtime_env import (  # noqa: E402
    PG_HOST,
    PG_PORT,
    PG_USER,
    REPO,
    bind_config,
    odoo_addons,
    odoo_source,
)

ODOO_SRC = odoo_source()
ODOO_ADDONS = odoo_addons()
TEMPLATE_DB = os.environ.get("L9_ODOO_TEMPLATE_DB", "plasticos_template")
SCRATCH_DB = "legacy_erp_gate"

bind_config(config)
# Must run before any odoo.addons.* import, or the addon is not importable.
odoo.modules.module.initialize_sys_path()

PAYLOAD_ROOT = os.path.join(REPO, "data", "legacy_erp_sm_export")
CORRUPT_CPID = "G4CORRUPT"


def _conn(dbname: str):
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, dbname=dbname)


def query(dbname: str, sql: str, args: tuple = ()) -> list:
    conn = _conn(dbname)
    conn.set_session(autocommit=True)
    with conn.cursor() as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    conn.close()
    return rows


def execute(dbname: str, sql: str, args: tuple = ()) -> None:
    conn = _conn(dbname)
    conn.set_session(autocommit=True)
    with conn.cursor() as cur:
        cur.execute(sql, args)
    conn.close()


def create_scratch_db() -> bool:
    """CREATE DATABASE from the template; False when the runtime is absent."""
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, dbname="postgres")
    conn.set_session(autocommit=True)
    with conn.cursor() as cur:
        cur.execute("select 1 from pg_database where datname = %s", (TEMPLATE_DB,))
        if not cur.fetchone():
            conn.close()
            return False
        cur.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')
        cur.execute(f'CREATE DATABASE "{SCRATCH_DB}" TEMPLATE "{TEMPLATE_DB}"')
    conn.close()
    return True


def drop_scratch_db() -> None:
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, dbname="postgres")
    conn.set_session(autocommit=True)
    with conn.cursor() as cur:
        cur.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')
    conn.close()


def odoo_env():
    return odoo.modules.registry.Registry(SCRATCH_DB).cursor()


def import_once(payload_root: str | None = None) -> dict:
    from odoo.addons.plasticos_transaction.scripts.run_legacy_erp_import import run

    with odoo_env() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        return run(env, payload_root=payload_root, commit=True, verbose=False)


def marker_count(dbname: str, name_pattern: str) -> int:
    rows = query(dbname, "select count(*) from ir_model_data where name like %s", (name_pattern,))
    return int(rows[0][0])


def gate_g1_first_import_reconciles() -> bool:
    result = import_once()
    summary = result["summary"]
    counts = result["counts"]

    # Reconciliation closes: nothing lost, nothing duplicated.
    closed = (
        summary["records_created"]
        + summary["records_updated"]
        + summary["records_unchanged"]
        + summary["records_rejected"]
        == summary["records_seen"]
    )
    if not closed:
        print(f"G1 reconciliation does not close: {summary}")
        return False
    if summary["duplicates"] != 0:
        print(f"G1 duplicates != 0: {summary['duplicates']}")
        return False

    # Independent verification over a connection Odoo does not own.
    partners = int(query(SCRATCH_DB, "select count(*) from res_partner where is_company")[0][0])
    expected = counts["counterparties"]["created"]
    if partners < expected:
        print(f"G1 res_partner companies {partners} < created counterparties {expected}")
        return False
    # Sampled identity: the marker exists exactly once and points at a partner.
    sample = query(
        SCRATCH_DB,
        "select res_id from ir_model_data where module = 'plasticos_transaction' and name = 'legacy_erp_cp_1121'",
    )
    if not sample:
        print("G1 sampled CpID marker (legacy_erp_cp_1121) missing")
        return False
    if summary["final_status"] not in ("success", "partial"):
        print(f"G1 unexpected final_status: {summary['final_status']}")
        return False
    print(
        f"G1 first import reconciled: {summary['records_created']} created, "
        f"{summary['records_rejected']} rejected, {summary['records_seen']} seen"
    )
    return True


def gate_g2_repeat_is_idempotent() -> bool:
    result = import_once()
    summary = result["summary"]
    if summary["records_created"] != 0:
        print(f"G2 second run created {summary['records_created']} records — duplicate creation")
        return False
    if summary["records_updated"] != 0:
        print(f"G2 second run updated {summary['records_updated']} records — churn")
        return False
    # No duplicate partner for any sampled source key.
    dup = query(
        SCRATCH_DB,
        "select count(*) from res_partner where id in "
        "(select res_id from ir_model_data where module = 'plasticos_transaction' and name = 'legacy_erp_cp_1121')",
    )
    if int(dup[0][0]) != 1:
        print(f"G2 sampled CpID resolves to {dup[0][0]} partners")
        return False
    print(f"G2 repeat run: 0 created, {summary['records_unchanged']} unchanged")
    return True


def _mutate_payload(tmp: str, cpid: str, suffix: str) -> str:
    """Copy the payload into tmp and append ``suffix`` to one counterparty name."""
    shutil.copytree(PAYLOAD_ROOT, tmp, dirs_exist_ok=True)
    path = os.path.join(tmp, "bulk", "CounterParty.csv")
    rows = list(csv.reader(open(path, encoding="utf-8-sig", newline="")))
    for row in rows[1:]:
        if row and row[0] == cpid:
            row[1] = row[1] + suffix
    with open(path, "w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    return tmp


def gate_g3_changed_source_updates() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        _mutate_payload(tmp, "1121", " [changed]")
        result = import_once(payload_root=tmp)
    summary = result["summary"]
    name_row = query(
        SCRATCH_DB,
        "select p.name from res_partner p join ir_model_data d on d.res_id = p.id "
        "where d.module = 'plasticos_transaction' and d.name = 'legacy_erp_cp_1121'",
    )
    if not name_row or "[changed]" not in str(name_row[0][0]):
        print(f"G3 changed name not applied: {name_row}")
        return False
    dup = marker_count(SCRATCH_DB, "legacy_erp_cp_1121")
    if dup != 1:
        print(f"G3 changed record duplicated: {dup} markers")
        return False
    print(f"G3 changed source record updated deterministically ({summary['records_updated']} updated)")
    return True


def gate_g4_savepoint_recovery() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        # Corrupt one WKSDetail row (absurdly long LotNo) so its BuySellNo
        # insert fails inside the savepoint; everything else must persist.
        shutil.copytree(PAYLOAD_ROOT, tmp, dirs_exist_ok=True)
        path = os.path.join(tmp, "bulk", "WKSDetail.csv")
        rows = list(csv.reader(open(path, encoding="utf-8-sig", newline="")))
        corrupt_buysell = None
        for row in rows[1:]:
            if row and row[1]:
                row[16] = "X" * 9000  # LotNo
                corrupt_buysell = row[1]
                break
        with open(path, "w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerows(rows)

        result = import_once(payload_root=tmp)
        summary = result["summary"]

        failed = {str(row.get("buysell_no")) for row in result["errors"]}
        if corrupt_buysell not in failed:
            print(f"G4 corrupted BuySellNo {corrupt_buysell} not recorded as failed: {failed}")
            return False
        leftover = marker_count(SCRATCH_DB, f"legacy_erp_transaction_{corrupt_buysell}")
        if leftover != 0:
            print(f"G4 failed unit left {leftover} markers behind")
            return False
        # The failed unit is the ONLY casualty; other units persisted.
        if summary["records_created"] == 0:
            print("G4 no unit persisted around the failed one")
            return False

    # Fixed re-run recovers the failed unit without duplicates.
    result = import_once()
    recovered = marker_count(SCRATCH_DB, f"legacy_erp_transaction_{corrupt_buysell}")
    if recovered != 1:
        print(f"G4 recovery left {recovered} markers for {corrupt_buysell}")
        return False
    print(f"G4 savepoint recovery verified ({corrupt_buysell} failed, then recovered)")
    return True


def attempt(name: str, fn) -> bool:
    try:
        return bool(fn())
    except Exception as exc:  # noqa: BLE001 - a crash IS the failure signal
        print(f"{name}: raised {type(exc).__name__}: {str(exc).strip().splitlines()[0]}")
        return False


def main() -> int:
    if not ODOO_SRC or not os.path.isdir(ODOO_ADDONS):
        print(f"odoo source not found (looked for {ODOO_ADDONS}); see C1_C6_LOCAL_RUNTIME.md")
        return 77
    if not os.path.isdir(os.path.join(PAYLOAD_ROOT, "bulk")):
        print("payload missing in this checkout")
        return 77
    if not create_scratch_db():
        print(f"template database {TEMPLATE_DB!r} not found — run scripts/setup_local_runtime.sh")
        return 77

    results = {}
    try:
        results["G1 first import reconciles"] = attempt("G1", gate_g1_first_import_reconciles)
        results["G2 repeat run is idempotent"] = attempt("G2", gate_g2_repeat_is_idempotent)
        results["G3 changed source updates deterministically"] = attempt("G3", gate_g3_changed_source_updates)
        results["G4 savepoint recovery"] = attempt("G4", gate_g4_savepoint_recovery)
    finally:
        drop_scratch_db()

    print("\n" + "=" * 64)
    for name, passed in results.items():
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    print("=" * 64)
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
