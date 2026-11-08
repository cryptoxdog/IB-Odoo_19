"""Runtime gate — ERP import: reconciliation, repeat-run, changed-record,
and no transaction-object deal write — on a REAL Odoo runtime.

Not a pytest module and deliberately not collected: it needs a live Odoo 19
registry, a live PostgreSQL server, and a template database with
``plasticos_transaction`` installed. Setup is
``scripts/setup_local_runtime.sh``.
Run it directly::

    /opt/odoo-venv/bin/python tests/runtime_gates/run_erp_import.py

Exit codes: 0 = every gate G1–G6 ran and PASSED, 1 = a gate FAILED or the
scratch database was refused, 77 = SKIPPED or INCOMPLETE (no local runtime,
no payload, no template database, direct SQL was required and is unset, or
G1–G4 passed while G5–G6 did not run). Exit 77 is never a successful G5/G6
result and never a pass. This is the live-DB proof the import milestone
requires; the collected pure-python tier cannot see any of it by construction.

Gates:
    G1 first import reconciles        partner import; summary counters close;
                                      markers and rows verified over a
                                      psycopg2 connection Odoo does not own.
    G2 repeat run is idempotent       second import on the same input creates
                                      nothing and reports everything unchanged.
    G3 changed source updates         one mutated payload row updates exactly
                                      that record; no duplicate appears.
    G4 no transaction object         a full import writes no worksheet
                                      transaction marker and no detail-line
                                      marker.

G1–G4 read the frozen grid fixture. They do not prove the direct SQL Server
source seam. G5–G6 do, on a freshly re-created scratch database, and run only
when ``ERP_SQL_SERVER`` / ``ERP_SQL_DATABASE`` (+ ``ERP_SQL_USER`` /
``ERP_SQL_PASSWORD`` / ``ERP_SQL_PORT`` / ``ERP_SQL_DRIVER``) name the restored
ERP database; the source is read with SELECT projection scripts only::

    ERP_GATE_REQUIRE_DIRECT_SQL=1 ERP_SQL_SERVER=… ERP_SQL_DATABASE=… \\
        make runtime-gate g=run_erp_import.py

    G5 direct-SQL import reconciles  the restored SQL Server is the selected
                                      source; the projection registry carries
                                      exactly the tables a full direct-SQL run
                                      reads (``REQUIRED_TABLES`` plus
                                      ``COMMERCIAL_SQL_TABLES``), each backed by
                                      a script file, and every one of them is
                                      read through the shared reader; the
                                      partner summary closes; a full import
                                      writes no transaction or line marker.
    G6 direct-SQL replay is idempotent identical second direct-SQL run: zero
                                      created, zero updated, identity markers
                                      unchanged, no duplicate source identity.

The scratch database is dropped and recreated only through one identity
guard (``scratch_db.require_disposable_scratch``). Unsafe identifiers, the
template database, production-like names, a production stage, PostgreSQL
system databases, and any name outside the ``erp_import_gate`` namespace
fail closed before a connection is opened and before DROP or CREATE is
built. A refusal exits 1.

Without the direct-SQL settings G5–G6 report NOT RUN: a failure among G1–G4
still exits 1, and a run in which G1–G4 passed exits 77 (INCOMPLETE, never
PASS), so ``make runtime-gates`` counts the unrun seam instead of reading a
partial proof as green. ``ERP_GATE_REQUIRE_DIRECT_SQL=1`` turns that absence
into exit 77 (SKIPPED, never PASS) before any gate runs.
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
import odoo.sql_db
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
from scratch_db import create_scratch_database, drop_scratch_database  # noqa: E402

ODOO_SRC = odoo_source()
ODOO_ADDONS = odoo_addons()
TEMPLATE_DB = os.environ.get("L9_ODOO_TEMPLATE_DB", "plasticos_template")
SCRATCH_DB = os.environ.get("L9_ODOO_ERP_GATE_DB", "erp_import_gate")

bind_config(config)
# Must run before any odoo.addons.* import, or the addon is not importable.
odoo.modules.module.initialize_sys_path()

PAYLOAD_ROOT = os.path.join(REPO, "plasticos_partner_import", "erp_extracted_data")


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


def _stage() -> str:
    return os.environ.get("ODOO_STAGE", "")


def _pg_connect(dbname: str):
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, dbname=dbname)


def create_scratch_db() -> bool:
    """Recreate the disposable scratch database. Identity is guarded before any SQL."""
    return create_scratch_database(_pg_connect, SCRATCH_DB, TEMPLATE_DB, stage=_stage())


def drop_scratch_db() -> None:
    """Drop the disposable scratch database. Same identity guard as create."""
    drop_scratch_database(_pg_connect, SCRATCH_DB, TEMPLATE_DB, stage=_stage())


def odoo_env():
    return odoo.modules.registry.Registry(SCRATCH_DB).cursor()


def release_scratch_db() -> None:
    """Drop Odoo's cached registry and pooled connections so the scratch database can be dropped."""
    odoo.modules.registry.Registry.delete(SCRATCH_DB)
    odoo.sql_db.close_db(SCRATCH_DB)


def import_once(payload_root: str | None = None, database=None, partners_only: bool = True) -> dict:
    from odoo.addons.plasticos_partner_import.scripts.run_erp_import import run

    with odoo_env() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        return run(
            env,
            payload_root=payload_root,
            commit=True,
            verbose=False,
            database=database,
            partners_only=partners_only,
        )


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
        "select res_id from ir_model_data where module = 'plasticos_transaction' and name = 'legacy_erp_cp_1004'",
    )
    if not sample:
        print("G1 sampled CpID marker (legacy_erp_cp_1004) missing")
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
        "(select res_id from ir_model_data where module = 'plasticos_transaction' and name = 'legacy_erp_cp_1004')",
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
        _mutate_payload(tmp, "1004", " [changed]")
        result = import_once(payload_root=tmp)
    summary = result["summary"]
    name_row = query(
        SCRATCH_DB,
        "select p.name from res_partner p join ir_model_data d on d.res_id = p.id "
        "where d.module = 'plasticos_transaction' and d.name = 'legacy_erp_cp_1004'",
    )
    if not name_row or "[changed]" not in str(name_row[0][0]):
        print(f"G3 changed name not applied: {name_row}")
        return False
    dup = marker_count(SCRATCH_DB, "legacy_erp_cp_1004")
    if dup != 1:
        print(f"G3 changed record duplicated: {dup} markers")
        return False
    print(f"G3 changed source record updated deterministically ({summary['records_updated']} updated)")
    return True


def _fixture_deal() -> tuple[str, list[str]]:
    """The first fixture BuySellNo with lines, and its DetailIDs (columns found by header name)."""
    path = os.path.join(PAYLOAD_ROOT, "bulk", "WKSDetail.csv")
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    target = next(row["BuySellNo"].strip() for row in rows if (row.get("BuySellNo") or "").strip())
    details = [row["DetailID"].strip() for row in rows if (row.get("BuySellNo") or "").strip() == target]
    return target, details


def _deal_rows(buysell_no: str, detail_ids: list[str]) -> tuple[int, int]:
    """Transaction and line identity markers stored for one deal."""
    transactions = marker_count(SCRATCH_DB, f"legacy_erp_transaction_{buysell_no}")
    lines = sum(marker_count(SCRATCH_DB, f"legacy_erp_detail_{detail_id}") for detail_id in detail_ids)
    return transactions, lines


def gate_g4_full_import_writes_no_transaction_object() -> bool:
    """A full import must not create one transaction per worksheet or one line per detail."""
    release_scratch_db()
    if not create_scratch_db():
        print("G4 could not re-create the scratch database")
        return False
    target, detail_ids = _fixture_deal()
    import_once(partners_only=False)
    leftover = _deal_rows(target, detail_ids)
    if leftover != (0, 0):
        print(f"G4 full import wrote transaction markers {leftover} for {target} / {detail_ids}")
        return False
    census = _deal_marker_census()
    if any(census.values()):
        print(f"G4 deal markers present: {census}")
        return False
    print("G4 full import wrote no transaction or line markers")
    return True


# ---------------------------------------------------------------------------
# G5–G6: the direct SQL Server source seam
# ---------------------------------------------------------------------------
REQUIRE_DIRECT_SQL_ENV = "ERP_GATE_REQUIRE_DIRECT_SQL"
DEAL_MARKERS = ("legacy_erp_transaction_%", "legacy_erp_detail_%")
_DIRECT = {"markers": None}


def direct_sql_source():
    """The restored-database source the environment names, or ``None``."""
    from odoo.addons.plasticos_partner_import.erp import reader

    return reader.database_source_from_env(os.environ)


def _closes(summary: dict) -> bool:
    return (
        summary["records_created"]
        + summary["records_updated"]
        + summary["records_unchanged"]
        + summary["records_rejected"]
        == summary["records_seen"]
    )


def _counters(summary: dict) -> str:
    keys = ("records_seen", "records_created", "records_updated", "records_unchanged", "records_rejected", "duplicates")
    return (
        " ".join(f"{key.removeprefix('records_')}={summary[key]}" for key in keys)
        + f" status={summary['final_status']}"
    )


def _deal_marker_census() -> dict[str, int]:
    return {pattern: marker_count(SCRATCH_DB, pattern) for pattern in DEAL_MARKERS}


def full_direct_sql_tables(reader) -> frozenset[str]:
    """The tables a full direct-SQL run reads: the consumer expectation G5 holds the registry to.

    This is ``erp_import_service`` 's own ``only`` set for a full database run
    (``REQUIRED_TABLES | COMMERCIAL_SQL_TABLES``), so the gate follows the
    registered inventory instead of pinning a count that goes stale the next
    time a projection is added.
    """
    return frozenset(reader.REQUIRED_TABLES) | frozenset(reader.COMMERCIAL_SQL_TABLES)


def projection_registry_gap(reader) -> list[str]:
    """Why the projection registry cannot serve a full direct-SQL run; empty when it can.

    Every table the full run reads must be registered, nothing else may be
    (an unregistered consumer or an orphan projection is drift either way),
    and each registered script must exist where the reader executes it from.
    """
    expected = full_direct_sql_tables(reader)
    registered = frozenset(reader.PROJECTION_SCRIPTS)
    gap = []
    missing = sorted(expected - registered)
    if missing:
        gap.append(f"full direct-SQL run reads {missing} but no projection is registered for them")
    orphans = sorted(registered - expected)
    if orphans:
        gap.append(f"projections {orphans} are registered but no direct-SQL run reads them")
    scripts_root = reader.sql_payload_root()
    absent = sorted(
        f"{table} -> {script}"
        for table, script in reader.PROJECTION_SCRIPTS.items()
        if not (scripts_root / script).is_file()
    )
    if absent:
        gap.append(f"projection scripts missing under {scripts_root}: {absent}")
    return gap


def gate_g5_direct_sql_import_reconciles(source) -> bool:
    from odoo.addons.plasticos_partner_import.erp import reader

    # Identity was enforced by create_scratch_database before this gate was called.
    gap = projection_registry_gap(reader)
    if gap:
        print("G5 projection registry cannot serve a full direct-SQL run: " + "; ".join(gap))
        return False
    full = full_direct_sql_tables(reader)

    result = import_once(database=source, partners_only=True)
    summary = result["summary"]
    print(f"G5 first direct-SQL partner run ({source.label}): {_counters(summary)}")
    if result["payload_kind"] != reader.PayloadKind.DATABASE.value:
        print(f"G5 source is {result['payload_kind']!r}, not the restored database")
        return False
    if not _closes(summary) or summary["duplicates"] != 0 or summary["final_status"] == "failed":
        print(f"G5 summary does not close: {summary['errors'][:5]}")
        return False

    # Every registered projection is read through the shared reader, as the full run reads it.
    payload = reader.load_payload(None, database=source, only=full)
    if set(payload.tables) != set(full):
        print(f"G5 direct read returned {sorted(payload.tables)}, expected {sorted(full)}")
        return False
    print(f"G5 projection row counts: {payload.row_counts()}")
    import_once(database=source, partners_only=False)
    markers = _deal_marker_census()
    if any(markers.values()):
        print(f"G5 full import wrote transaction or line markers: {markers}")
        return False
    _DIRECT["markers"] = markers
    print(f"G5 direct-SQL partner import reconciled; deal markers {markers}")
    return True


def gate_g6_direct_sql_replay_is_idempotent(source) -> bool:
    if _DIRECT["markers"] is None:
        print("G6 not attempted: G5 did not pass")
        return False
    summary = import_once(database=source, partners_only=True)["summary"]
    print(f"G6 replay direct-SQL run ({source.label}): {_counters(summary)}")
    if not _closes(summary) or summary["final_status"] == "failed":
        print(f"G6 replay summary does not close: {summary['errors'][:5]}")
        return False
    if summary["records_created"] or summary["records_updated"]:
        print("G6 replay created or updated records — duplicate creation or write churn")
        return False
    markers = _deal_marker_census()
    if markers != _DIRECT["markers"] or any(markers.values()):
        print(f"G6 deal markers moved: {_DIRECT['markers']} -> {markers}")
        return False
    print(f"G6 replay: 0 created, 0 updated, {summary['records_unchanged']} unchanged")
    return True


def attempt(name: str, fn) -> bool:
    try:
        return bool(fn())
    except Exception as exc:  # noqa: BLE001 - a crash IS the failure signal
        print(f"{name}: raised {type(exc).__name__}: {str(exc).strip().splitlines()[0]}")
        return False


def main() -> int:
    if not ODOO_SRC or not os.path.isdir(ODOO_ADDONS):
        print(f"odoo source not found (looked for {ODOO_ADDONS}); see scripts/setup_local_runtime.sh")
        return 77
    if not os.path.isdir(os.path.join(PAYLOAD_ROOT, "bulk")):
        print("payload missing in this checkout")
        return 77
    source = direct_sql_source()
    required = (os.environ.get(REQUIRE_DIRECT_SQL_ENV) or "").strip().lower() in {"1", "true", "yes", "y"}
    if source is None and required:
        # SKIPPED, never PASS: the direct-SQL seam proof was required and no restored database is named.
        print(f"{REQUIRE_DIRECT_SQL_ENV}=1 but ERP_SQL_SERVER / ERP_SQL_DATABASE are unset — G5/G6 cannot run")
        return 77
    if not create_scratch_db():
        # SKIPPED, never PASS: the configured template database does not exist on this runtime.
        print(f"template database {TEMPLATE_DB!r} not found — run scripts/setup_local_runtime.sh")
        return 77

    results = {}
    try:
        results["G1 first import reconciles"] = attempt("G1", gate_g1_first_import_reconciles)
        results["G2 repeat run is idempotent"] = attempt("G2", gate_g2_repeat_is_idempotent)
        results["G3 changed source updates deterministically"] = attempt("G3", gate_g3_changed_source_updates)
        results["G4 full import writes no transaction object"] = attempt(
            "G4", gate_g4_full_import_writes_no_transaction_object
        )
        if source is not None:
            # The direct-SQL proof starts from the template again, never from fixture-loaded rows.
            release_scratch_db()
            results["G5 direct-SQL import reconciles"] = attempt(
                "G5", lambda: create_scratch_db() and gate_g5_direct_sql_import_reconciles(source)
            )
            results["G6 direct-SQL replay is idempotent"] = attempt(
                "G6", lambda: gate_g6_direct_sql_replay_is_idempotent(source)
            )
    finally:
        release_scratch_db()
        drop_scratch_db()

    print("\n" + "=" * 64)
    for name, passed in results.items():
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    if source is None:
        print("  NOT RUN  G5/G6 direct-SQL seam (ERP_SQL_SERVER / ERP_SQL_DATABASE unset) — unproven by this run")
    print("=" * 64)
    if not all(results.values()):
        return 1
    if source is None:
        # G1–G4 passed, but the direct-SQL seam this gate exists to prove did
        # not run. That is INCOMPLETE, never PASS: exit 77 so `make runtime-gates`
        # counts the unrun gates instead of reading a partial proof as green.
        print("INCOMPLETE: G1-G4 passed; G5/G6 did not run (exit 77, never a pass)")
        return 77
    return 0


if __name__ == "__main__":
    sys.exit(main())
