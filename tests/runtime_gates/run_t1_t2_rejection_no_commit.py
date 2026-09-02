"""Launch gates T1, T2 — a rejected operation must not publish caller state.

Not a pytest module and deliberately not collected: it needs a live Odoo 19
registry and a live PostgreSQL server. Setup is in
docs/runbooks/C1_C6_LOCAL_RUNTIME.md. Run it directly::

    /opt/odoo-venv/bin/python tests/runtime_gates/run_t1_t2_rejection_no_commit.py

S1 proved that the durability commit is *necessary*: without it the audit row's
foreign key cannot see a connection the caller created. These two gates prove
where that commit is allowed to sit.

    T1  execution ownership refused  -> CrmSyncLockedError, nothing committed
    T2  invocation refused by validation -> CrmFullImportArgumentError, nothing committed

`_ensure_caller_state_durable()` commits the caller's transaction, so it makes
everything the caller had pending visible to every other session on the server.
Placed before the advisory-lock acquisition it fires on the path that then
*refuses* the call: the operator's first sync loses a race against the cron, is
told the sync will not run, and the connection it created is committed anyway.
Placed before argument validation it does the same for an invocation that was
never usable.

Why the collected suite cannot see either: under `TransactionCase` there is one
cursor, `cr.commit()` is neutered, and every assertion reads through the same
transaction that did the work — so a commit that should not have happened is
indistinguishable from one that did not. Only a second, independent session can
answer "is this row visible outside the transaction that wrote it", and that is
the entire question here.

Structural proxies for CI live in `tests/test_pristine_runtime_seams.py`
(`test_entrypoint_acquires_the_advisory_lock_before_it_commits`,
`test_full_import_validates_every_bound_before_it_commits`). They can see the
call order; they cannot see a commit.
"""

from __future__ import annotations

import os
import sys

import psycopg2

import odoo
import odoo.modules.module
from odoo.api import Environment
from odoo.tools import config

DB = os.environ.get("SEAM_DB", "seam_test")
PG_HOST = os.environ.get("SEAM_PG_HOST", "/tmp")
PG_PORT = int(os.environ.get("SEAM_PG_PORT", "5433"))
PG_USER = os.environ.get("SEAM_PG_USER", "odoo")
ODOO_SRC = os.environ.get("SEAM_ODOO_SRC") or ""
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if not ODOO_SRC:
    import glob

    matches = sorted(glob.glob("/opt/odoo-src/odoo-19.0*"))
    ODOO_SRC = matches[-1] if matches else ""
ODOO_ADDONS = os.path.join(ODOO_SRC, "odoo", "addons")

config["db_host"] = PG_HOST
config["db_port"] = PG_PORT
config["db_user"] = PG_USER
config["addons_path"] = f"{ODOO_ADDONS},{REPO}"

# Must run before any odoo.addons.* import, or the addon is not importable.
odoo.modules.module.initialize_sys_path()

from odoo.addons.plasticos_crm_sync.services.orchestrator import (  # noqa: E402
    CrmFullImportArgumentError,
    CrmSyncLockedError,
    SyncOrchestrator,
    advisory_lock_key,
)

TAG = "t1t2-rejection"


# ----------------------------------------------------------------------
# Every assertion reads over a session Odoo does not own. Reading through the
# transaction under test would return its own uncommitted rows and prove
# exactly nothing about what was published.
# ----------------------------------------------------------------------
def independent_connection():
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, dbname=DB)
    conn.set_session(autocommit=True)
    return conn


def visible_outside(connection_id: int) -> bool:
    conn = independent_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("select 1 from plasticos_crm_connection where id = %s", (connection_id,))
            return cur.fetchone() is not None
    finally:
        conn.close()


def cleanup() -> None:
    conn = independent_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "delete from plasticos_crm_sync_run where connection_id in "
                "(select id from plasticos_crm_connection where name like %s)",
                (f"%{TAG}%",),
            )
            cur.execute("delete from plasticos_crm_connection where name like %s", (f"%{TAG}%",))
    finally:
        conn.close()


def new_connection_payload(label: str) -> dict:
    return {
        "name": f"{label} {TAG}",
        "provider": "vanillasoft",
        "active": True,
        "enabled": False,
    }


results: dict[str, bool] = {}


# ----------------------------------------------------------------------
# Control — the sentinel has teeth.
#
# Without this, both gates below could pass because the sentinel is never
# visible outside its transaction under ANY circumstances (a mis-built row, the
# wrong table, a typo in the predicate). The control commits deliberately and
# requires the same query to see it.
# ----------------------------------------------------------------------
def control_sentinel_is_observable() -> bool:
    with odoo.modules.registry.Registry(DB).cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        record = env["plasticos.crm.connection"].create(new_connection_payload("CONTROL"))
        env.flush_all()
        connection_id = record.id
        before = visible_outside(connection_id)
        cr.commit()
        after = visible_outside(connection_id)
    print(f"   control: visible_before_commit={before} visible_after_commit={after}")
    return (not before) and after


# ----------------------------------------------------------------------
# T1 — refused for want of execution ownership
# ----------------------------------------------------------------------
def gate_t1() -> bool:
    """The first-run Settings sync loses the race against the cron.

    The caller creates the connection and hands it straight in — the pristine
    path S1 covers — but another session already holds this connection's
    session advisory lock. `run_connection` must refuse before it has started
    any work, and refusing must leave the caller's connection exactly as
    unpublished as it found it.
    """
    holder = independent_connection()
    try:
        with odoo.modules.registry.Registry(DB).cursor() as cr:
            env = Environment(cr, odoo.SUPERUSER_ID, {})
            record = env["plasticos.crm.connection"].create(new_connection_payload("T1"))
            # Force the INSERT into this transaction. The row now exists here,
            # uncommitted — precisely the caller state a refusal must not publish.
            env.flush_all()
            connection_id = record.id
            sentinel_leaked_early = visible_outside(connection_id)

            # A second session takes the lock this connection's sync would need.
            with holder.cursor() as cur:
                cur.execute("select pg_try_advisory_lock(hashtext(%s))", (advisory_lock_key(connection_id),))
                acquired_elsewhere = bool(cur.fetchone()[0])

            raised = None
            try:
                SyncOrchestrator(env).run_connection(record)
            except CrmSyncLockedError as exc:
                raised = exc

            # Read while transaction A is STILL OPEN. After a rollback the row
            # would be invisible whether or not a commit had happened, so the
            # assertion has to land here to mean anything.
            leaked = visible_outside(connection_id)
            cr.rollback()

        print(
            f"T1: lock_held_by_other_session={acquired_elsewhere} "
            f"raised={type(raised).__name__ if raised else None} "
            f"leaked_before_call={sentinel_leaked_early} caller_state_published={leaked}"
        )
        results["T1. the other session really holds the lock"] = acquired_elsewhere
        results["T1. sentinel is unpublished before the call"] = not sentinel_leaked_early
        results["T1. run_connection raises CrmSyncLockedError"] = isinstance(raised, CrmSyncLockedError)
        results["T1. a refused run publishes no caller state"] = not leaked
        return (
            acquired_elsewhere and not sentinel_leaked_early and isinstance(raised, CrmSyncLockedError) and not leaked
        )
    finally:
        # Session-scoped locks die with the session; closing releases it.
        holder.close()


# ----------------------------------------------------------------------
# T2 — refused by deterministic argument validation
# ----------------------------------------------------------------------
def gate_t2() -> bool:
    """An unusable historical bound rejects the invocation before anything runs.

    `_require_utc_bound` decides this from the arguments alone. Nothing has
    been locked, no audit row exists, no adapter has been built — so the
    caller's pending state must still be its own.
    """
    with odoo.modules.registry.Registry(DB).cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        record = env["plasticos.crm.connection"].create(new_connection_payload("T2"))
        env.flush_all()
        connection_id = record.id
        sentinel_leaked_early = visible_outside(connection_id)

        raised = None
        try:
            SyncOrchestrator(env).run_full_import(record, call_history_floor="not-an-iso-8601-instant")
        except CrmFullImportArgumentError as exc:
            raised = exc

        leaked = visible_outside(connection_id)

        # The same refusal for the *other* deterministic rejection shape: a
        # bound that parses but names a future instant.
        record_2 = env["plasticos.crm.connection"].create(new_connection_payload("T2b"))
        env.flush_all()
        raised_future = None
        try:
            SyncOrchestrator(env).run_full_import(record_2, call_history_floor="2999-01-01T00:00:00Z")
        except CrmFullImportArgumentError as exc:
            raised_future = exc
        leaked_future = visible_outside(record_2.id)

        cr.rollback()

    print(
        f"T2: raised={type(raised).__name__ if raised else None} "
        f"leaked_before_call={sentinel_leaked_early} caller_state_published={leaked} | "
        f"future_bound raised={type(raised_future).__name__ if raised_future else None} "
        f"caller_state_published={leaked_future}"
    )
    results["T2. sentinel is unpublished before the call"] = not sentinel_leaked_early
    results["T2. unparseable bound raises CrmFullImportArgumentError"] = isinstance(raised, CrmFullImportArgumentError)
    results["T2. a rejected invocation publishes no caller state"] = not leaked
    results["T2. future bound raises CrmFullImportArgumentError"] = isinstance(
        raised_future, CrmFullImportArgumentError
    )
    results["T2. a rejected future bound publishes no caller state"] = not leaked_future
    return (
        not sentinel_leaked_early
        and isinstance(raised, CrmFullImportArgumentError)
        and not leaked
        and isinstance(raised_future, CrmFullImportArgumentError)
        and not leaked_future
    )


# ----------------------------------------------------------------------
# T3 — the lock the repair now holds across the commit really does survive it
# ----------------------------------------------------------------------
def gate_t3() -> bool:
    """`pg_try_advisory_lock` is session-scoped, so a commit does not drop it.

    The whole repair rests on this: the durability commit was moved *inside*
    the guarded region, so if the lock were transaction-scoped the commit would
    silently release execution ownership and two syncs could interleave — a
    worse defect than the one being fixed. `pg_advisory_lock`'s session/
    transaction distinction is one function name apart (`_xact_`), so the
    property is asserted rather than assumed.

    Driven through the orchestrator's own helpers on a real Odoo cursor, so a
    future switch to `pg_try_advisory_xact_lock` fails here.
    """
    key = advisory_lock_key(-987654321)  # no row needed; the lock is just a key
    contender = independent_connection()
    try:
        with odoo.modules.registry.Registry(DB).cursor() as cr:
            env = Environment(cr, odoo.SUPERUSER_ID, {})
            orchestrator = SyncOrchestrator(env)
            acquired = orchestrator._try_advisory_lock(key)

            # Exactly what `_ensure_caller_state_durable` does.
            orchestrator._ensure_caller_state_durable()

            with contender.cursor() as cur:
                cur.execute("select pg_try_advisory_lock(hashtext(%s))", (key,))
                stolen_after_commit = bool(cur.fetchone()[0])
                if stolen_after_commit:  # pragma: no cover - only on a broken lock scope
                    cur.execute("select pg_advisory_unlock(hashtext(%s))", (key,))

            orchestrator._advisory_unlock(key)

            with contender.cursor() as cur:
                cur.execute("select pg_try_advisory_lock(hashtext(%s))", (key,))
                free_after_unlock = bool(cur.fetchone()[0])
                cur.execute("select pg_advisory_unlock(hashtext(%s))", (key,))
            cr.rollback()
    finally:
        contender.close()

    print(
        f"T3: acquired={acquired} stolen_by_other_session_after_commit={stolen_after_commit} "
        f"released_on_unlock={free_after_unlock}"
    )
    results["T3. the orchestrator acquires the lock"] = acquired
    results["T3. the session lock survives the durability commit"] = not stolen_after_commit
    results["T3. the lock is genuinely released on unlock"] = free_after_unlock
    return acquired and not stolen_after_commit and free_after_unlock


def main() -> int:
    cleanup()
    try:
        results["CONTROL. the sentinel is observable once committed"] = control_sentinel_is_observable()
        gate_t1()
        gate_t2()
        gate_t3()
    finally:
        cleanup()

    print("\n" + "=" * 72)
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print("=" * 72)
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
