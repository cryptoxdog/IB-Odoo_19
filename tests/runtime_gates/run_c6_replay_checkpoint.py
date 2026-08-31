"""Gate C6 — replay / checkpoint integrity from a real partial-success state.

Not a pytest module and deliberately not collected: needs a live Odoo 19
registry and a live PostgreSQL server. Setup: docs/runbooks/C1_C6_LOCAL_RUNTIME.md.

Run 1: page A (50 contacts, watermark W1) commits; page B fails -> run failed.
Run 2: same connection, adapter now serves page B. Must resume from W1, not
       re-consume page A, process the previously failed portion, advance the
       watermark forward only, and report only ITS OWN committed work.
"""

import os
import sys

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
odoo.modules.module.initialize_sys_path()
# _sync_contacts clamps modified_after to the source API's 31-day maximum
# (now - 30d). Watermarks older than that floor are legitimately rewritten to
# it, so a replay fixture MUST sit inside the window or it tests the clamp
# instead of the checkpoint.
from datetime import UTC, datetime, timedelta  # noqa: E402

from odoo.addons.plasticos_crm_sync.adapters.base import CanonicalLead, CrmAdapterError  # noqa: E402
from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator  # noqa: E402

_now = datetime.now(UTC)


def _iso(days_ago):
    return (_now - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


W0, W1, W2 = _iso(5), _iso(4), _iso(3)

# Every execution gets a private external-id namespace and its own connection.
# Without this the gate passes once: run 2's committed rows persist, and the
# next execution's "run 1 left 50 rows" assertion counts 75.
TAG = f"rq{os.getpid()}x{int(_now.timestamp())}"
results = {}
seen_modified_after = []


def indep(sql, args=()):
    c = psycopg2.connect(host="/tmp", port=5433, user="odoo", dbname=DB)
    c.set_session(autocommit=True)
    with c.cursor() as cur:
        cur.execute(sql, args)
        r = cur.fetchall()
    c.close()
    return r


def lead(i):
    return CanonicalLead(
        provider="vanillasoft",
        external_id=f"{TAG}-{i}",
        company=f"Co {i}",
        first_name="A",
        last_name="L",
        lead_status_raw="New",
    )


PAGE_A = [lead(i) for i in range(50)]  # committed by run 1
PAGE_B = [lead(i) for i in range(50, 75)]  # lost by run 1, must land in run 2


class _Base:
    provider = "vanillasoft"
    live = True

    def healthcheck(self):
        return {}

    def iter_calls(self, **k):
        return iter(())

    def iter_table_rows(self, x):
        return iter(())


class Run1(_Base):
    def iter_contacts(self, *, modified_after, limit=200):
        seen_modified_after.append(modified_after)
        yield (PAGE_A, W1, False)
        raise CrmAdapterError("replay: page B fails in run 1")


class Run2(_Base):
    """Serves only what the watermark says is outstanding."""

    def iter_contacts(self, *, modified_after, limit=200):
        seen_modified_after.append(modified_after)
        if modified_after == W1:
            yield (PAGE_B, W2, False)
        else:  # resumed from the wrong place — replay page A too
            yield (PAGE_A + PAGE_B, W2, False)


with odoo.modules.registry.Registry(DB).cursor() as cr:
    env = Environment(cr, odoo.SUPERUSER_ID, {})
    cid = (
        env["plasticos.crm.connection"]
        .create({"name": f"replay {TAG}", "provider": "vanillasoft", "active": True, "contact_watermark_utc": W0})
        .id
    )
    cr.commit()


def do_run(adapter, expect_fail):
    with odoo.modules.registry.Registry(DB).cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        o = SyncOrchestrator(env)
        o._build_adapter = lambda c: adapter
        rec = env["plasticos.crm.connection"].browse(cid)
        if expect_fail:
            try:
                o.run_connection(rec)
                return None
            except CrmAdapterError:
                return None
        return o.run_connection(rec).id


def state():
    wm = indep("select contact_watermark_utc from plasticos_crm_connection where id=%s", (cid,))[0][0]
    like = f"{TAG}-%"
    leads = indep("select count(*) from crm_lead where vanillasoft_id like %s", (like,))[0][0]
    distinct = indep("select count(distinct vanillasoft_id) from crm_lead where vanillasoft_id like %s", (like,))[0][0]
    runs = indep(
        "select id,status,contacts_upserted from plasticos_crm_sync_run where connection_id=%s order by id", (cid,)
    )
    return wm, leads, distinct, runs


# ---- run 1: partial success ------------------------------------------------
do_run(Run1(), expect_fail=True)
wm1, leads1, distinct1, runs1 = state()
print(f"run 1  watermark={wm1} leads={leads1} distinct={distinct1} runs={runs1}")
results["run 1 leaves the C2 partial state (50 committed, failed)"] = (
    leads1 == 50 and runs1 and runs1[-1][1] == "failed" and runs1[-1][2] == 50
)
results["run 1 watermark advanced to the committed page only"] = wm1 == W1

# ---- run 2: replay ---------------------------------------------------------
run2_id = do_run(Run2(), expect_fail=False)
wm2, leads2, distinct2, runs2 = state()
run2_row = [r for r in runs2 if r[0] == run2_id]
print(f"run 2  watermark={wm2} leads={leads2} distinct={distinct2} run2={run2_row}")
print(f"modified_after seen by the adapter across runs: {seen_modified_after}")

results["run 2 resumed from the last durable watermark"] = (
    len(seen_modified_after) == 2 and seen_modified_after[1] == W1
)
results["no duplicate committed records"] = leads2 == distinct2 == 75
results["previously failed portion was processed"] = (
    indep("select count(*) from crm_lead where vanillasoft_id in ('rq-50','rq-74')")[0][0] == 2
)
results["watermark advanced monotonically"] = wm2 == W2 and wm2 > wm1
results["run 2 reports only its own committed work"] = bool(run2_row and run2_row[0][2] == 25)
results["run 1's counter was not rewritten by run 2"] = runs2[-2][2] == 50 if len(runs2) >= 2 else False

print("\n" + "=" * 66)
for k, v in results.items():
    print(f"  {'PASS' if v else 'FAIL'}  {k}")
print("=" * 66)
sys.exit(0 if all(results.values()) else 1)
