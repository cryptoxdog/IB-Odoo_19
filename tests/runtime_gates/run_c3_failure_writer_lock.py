"""Gate C3 — the failure writer cannot block on the transaction that failed.

Not a pytest module and deliberately not collected: needs a live Odoo 19
registry and a live PostgreSQL server. Setup: docs/runbooks/C1_C6_LOCAL_RUNTIME.md.

Two parts, because a timing assertion with no teeth proves nothing:
  A. the hazard is REAL   — an uncommitted, flushed write to the sync-run row
                            does block a second cursor's UPDATE of that row
  B. the real handler is SAFE — run_connection rolls back first, so the durable
                            failure write proceeds and the RPC returns promptly
"""

import sys
import time

import psycopg2

import odoo
import odoo.modules.module
from odoo.api import Environment
from odoo.tools import config

DB = "c1c6_test"
config["db_host"] = "/tmp"
config["db_port"] = 5433
config["db_user"] = "odoo"
config["addons_path"] = "/opt/odoo-src/odoo-19.0.post20260831/odoo/addons,/home/user/IB-Odoo_19"
# Must run before any odoo.addons.* import, or the addon is not importable.
odoo.modules.module.initialize_sys_path()

from odoo.addons.plasticos_crm_sync.adapters.base import (  # noqa: E402
    CanonicalLead,
    CrmAdapterError,
)
from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator  # noqa: E402


def indep(sql, args=()):
    c = psycopg2.connect(host="/tmp", port=5433, user="odoo", dbname=DB)
    c.set_session(autocommit=True)
    with c.cursor() as cur:
        cur.execute(sql, args)
        r = cur.fetchall()
    c.close()
    return r


def lead(tag, i):
    return CanonicalLead(
        provider="vanillasoft",
        external_id=f"{tag}-{i}",
        company="Co",
        first_name="A",
        last_name="L",
        lead_status_raw="New",
    )


def mkconn(n):
    with odoo.modules.registry.Registry(DB).cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        cid = env["plasticos.crm.connection"].create({"name": n, "provider": "vanillasoft", "active": True}).id
        cr.commit()
        return cid


results = {}

# ---------- PART A: prove the hazard is real -------------------------------
print("A. hazard check — does an uncommitted flushed write to the run row block a 2nd cursor?")
with odoo.modules.registry.Registry(DB).cursor() as cr:
    env = Environment(cr, odoo.SUPERUSER_ID, {})
    cid = env["plasticos.crm.connection"].create({"name": "C3-hazard", "provider": "vanillasoft", "active": True}).id
    rid = env["plasticos.crm.sync.run"].create({"connection_id": cid, "status": "running"}).id
    cr.commit()
    run = env["plasticos.crm.sync.run"].browse(rid)
    run.contacts_upserted = 7
    env.flush_all()  # row is now locked by THIS transaction, uncommitted
    blocked = None
    c2 = psycopg2.connect(host="/tmp", port=5433, user="odoo", dbname=DB)
    with c2.cursor() as cur:
        cur.execute("set statement_timeout = 3000")
        try:
            cur.execute("update plasticos_crm_sync_run set status='failed' where id=%s", (rid,))
            c2.commit()
            blocked = False
        except psycopg2.errors.QueryCanceled:
            c2.rollback()
            blocked = True
    c2.close()
    cr.rollback()
print(f"   second cursor blocked by the uncommitted row lock: {blocked}")
results["A. lock hazard is real (test has teeth)"] = blocked is True

# ---------- PART B: the real handler is safe -------------------------------
print("\nB. real run_connection failure AFTER the ambient txn dirtied+flushed the run row")


class DirtyThenFail:
    provider = "vanillasoft"
    live = True

    def __init__(self, env):
        self.env = env

    def healthcheck(self):
        return {}

    def iter_contacts(self, *, modified_after, limit=200):
        yield ([lead("c3", i) for i in range(5)], "2026-08-02T00:00:00Z", False)  # commits -> T2
        # T2 now writes the run row and FLUSHES it, taking the row lock, then fails
        self.env.flush_all()
        raise CrmAdapterError("C3: failure while the run row is locked by this transaction")

    def iter_calls(self, **k):
        return iter(())

    def iter_table_rows(self, x):
        return iter(())


cid = mkconn("C3")
started = time.monotonic()
raised = False
with odoo.modules.registry.Registry(DB).cursor() as cr:
    env = Environment(cr, odoo.SUPERUSER_ID, {})
    o = SyncOrchestrator(env)
    o._build_adapter = lambda c: DirtyThenFail(env)
    try:
        o.run_connection(env["plasticos.crm.connection"].browse(cid))
    except CrmAdapterError:
        raised = True
elapsed = time.monotonic() - started
row = indep(
    "select status,contacts_upserted,error_excerpt is not null from plasticos_crm_sync_run "
    "where connection_id=%s order by id desc limit 1",
    (cid,),
)
print(f"   raised={raised} elapsed={elapsed:.2f}s")
print(f"   independent session -> status={row[0][0]} contacts_upserted={row[0][1]} error_excerpt_set={row[0][2]}")
results["B. RPC returns promptly (no lock wait)"] = raised and elapsed < 15
results["B. failed state durable from an independent session"] = bool(row and row[0][0] == "failed" and row[0][2])
results["B. committed page counter preserved on the failed run"] = bool(row and row[0][1] == 5)

print("\n" + "=" * 64)
for k, v in results.items():
    print(f"  {'PASS' if v else 'FAIL'}  {k}")
print("=" * 64)
sys.exit(0 if all(results.values()) else 1)
