"""Gates F1–F3 — manual full import, on a real registry and a real PostgreSQL.

Not a pytest module and deliberately not collected: needs a live Odoo 19
registry and a live PostgreSQL server. Setup: docs/runbooks/C1_C6_LOCAL_RUNTIME.md.
End-to-end procedure: docs/runbooks/CRM_SYNC_FULL_IMPORT_E2E.md.

The pure-Python tier drives `run_full_import` against an in-memory ORM, which
proves the algorithm but not the thing that has already bitten this module
twice: real commits, a real REPEATABLE READ snapshot, and real unique
constraints. Specifically —

  F1  a full import reaches past the 30-day rolling clamp, lands historical
      calls from the explicit floor, and leaves watermarks an immediate
      `run_connection` resumes from without duplicating a lead or a call.
  F2  the census verdict is `success` only when a contact older than the
      31-day Contacts horizon actually came back, and `partial` otherwise —
      and an unusable floor creates no sync-run row at all.
  F3  provider delete archives with provenance, restore reactivates, and a
      lead an Odoo user archived is never reopened.

Every assertion reads through an independent psycopg2 session, because reading
through the env under test can return uncommitted values and prove nothing.
"""

import os
import sys
from datetime import UTC, datetime, timedelta

import psycopg2

import odoo
import odoo.modules.module
from odoo.api import Environment
from odoo.tools import config

DB = os.environ.get("F1_DB", "c1c6_test")
PG_HOST = os.environ.get("F1_PG_HOST", "/tmp")
PG_PORT = int(os.environ.get("F1_PG_PORT", "5433"))
PG_USER = os.environ.get("F1_PG_USER", "odoo")
ADDONS = os.environ.get("F1_ADDONS_PATH", "")

config["db_host"] = PG_HOST
config["db_port"] = PG_PORT
config["db_user"] = PG_USER
if ADDONS:
    config["addons_path"] = ADDONS
odoo.modules.module.initialize_sys_path()

from odoo.addons.plasticos_crm_sync.adapters.base import (  # noqa: E402
    CanonicalCall,
    CanonicalLead,
)
from odoo.addons.plasticos_crm_sync.services.orchestrator import (  # noqa: E402
    CrmFullImportArgumentError,
    SyncOrchestrator,
)

_now = datetime.now(UTC)


def _iso(dt):
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# Older than the 31-day Contacts horizon in both directions: the floor the
# operator asks for, and the contact whose presence proves it was served.
CONTACT_FLOOR = _iso(_now - timedelta(days=400))
ANCIENT_MODIFIED = _iso(_now - timedelta(days=365))
RECENT_MODIFIED = _iso(_now - timedelta(days=2))
# Hours, not days: `_sync_calls` slices its window into 1-day chunks, so a
# multi-year call floor would issue a thousand adapter calls per phase.
CALL_FLOOR = _iso(_now - timedelta(hours=6))

# Private external-id namespace per execution — without it the gate passes once
# and then counts the previous execution's rows.
TAG = f"fi{os.getpid()}x{int(_now.timestamp())}"
results = {}


def indep(sql, args=()):
    """Assert from a session Odoo does not own."""
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, dbname=DB)
    conn.set_session(autocommit=True)
    with conn.cursor() as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    conn.close()
    return rows


def lead(suffix, modified=RECENT_MODIFIED, deleted=False):
    return CanonicalLead(
        provider="vanillasoft",
        external_id=f"{TAG}-{suffix}",
        company=f"Co {suffix}",
        first_name="A",
        last_name="L",
        lead_status_raw="New",
        modified_utc=modified,
        deleted=deleted,
    )


def call(suffix, contact_suffix):
    return CanonicalCall(
        provider="vanillasoft",
        external_id=f"{TAG}-call-{suffix}",
        contact_external_id=f"{TAG}-{contact_suffix}",
        call_datetime_utc=_iso(_now - timedelta(hours=3)),
        duration_seconds=30,
    )


class Adapter:
    """Phase-aware stub: bootstrap pass, then catch-up pass.

    `_sync_calls` calls `iter_calls` once per 1-day chunk, so scripted batches
    are served once per PHASE rather than once per invocation.
    """

    provider = "vanillasoft"
    live = True

    def __init__(self, contact_passes, call_passes):
        self.contact_passes = contact_passes
        self.call_passes = call_passes
        self.contact_calls = []
        self.call_windows = []
        self._served = set()

    def healthcheck(self):
        return {}

    def iter_contacts(self, *, modified_after, limit=200):
        self.contact_calls.append(modified_after)
        index = len(self.contact_calls) - 1
        yield from (self.contact_passes[index] if index < len(self.contact_passes) else [])

    def iter_calls(self, *, start, end, limit=500):
        self.call_windows.append((start, end))
        phase = max(len(self.contact_calls) - 1, 0)
        if phase in self._served:
            return
        self._served.add(phase)
        yield from (self.call_passes[phase] if phase < len(self.call_passes) else [])

    def iter_table_rows(self, contact_external_id):
        return iter(())


def make_connection(name, **vals):
    with odoo.modules.registry.Registry(DB).cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        payload = {"name": f"{name} {TAG}", "provider": "vanillasoft", "active": True, "enabled": False}
        payload.update(vals)
        cid = env["plasticos.crm.connection"].create(payload).id
        cr.commit()
    return cid


def drive(cid, adapter, method, **kwargs):
    with odoo.modules.registry.Registry(DB).cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        orch = SyncOrchestrator(env)
        orch._build_adapter = lambda connection: adapter
        record = env["plasticos.crm.connection"].browse(cid)
        return getattr(orch, method)(record, **kwargs).id


def watermarks(cid):
    return indep(
        "select contact_watermark_utc, call_watermark_utc from plasticos_crm_connection where id=%s",
        (cid,),
    )[0]


def run_row(run_id):
    return indep(
        "select status, contacts_upserted, calls_upserted, error_excerpt from plasticos_crm_sync_run where id=%s",
        (run_id,),
    )[0]


# ── F1 — full import reaches past the clamp, then hands off cleanly ─────────

f1_pages = [
    [([lead("old", ANCIENT_MODIFIED), lead("new")], RECENT_MODIFIED, False)],  # bootstrap
    [([lead("during")], RECENT_MODIFIED, False)],  # catch-up
]
f1_calls = [[[call("h1", "old"), call("h2", "new")]], [[call("c1", "during")]]]
f1_adapter = Adapter(f1_pages, f1_calls)
f1_cid = make_connection("full import")
f1_run = drive(
    f1_cid, f1_adapter, "run_full_import", call_history_floor=CALL_FLOOR, contact_modified_floor=CONTACT_FLOOR
)

f1_status, f1_contacts, f1_calls_n, f1_excerpt = run_row(f1_run)
f1_contact_wm, f1_call_wm = watermarks(f1_cid)
leads_like = f"{TAG}-%"
n_leads = indep("select count(*) from crm_lead where vanillasoft_id like %s", (leads_like,))[0][0]
n_distinct = indep("select count(distinct vanillasoft_id) from crm_lead where vanillasoft_id like %s", (leads_like,))[
    0
][0]
n_calls = indep("select count(*) from plasticos_crm_call_event where external_id like %s", (f"{TAG}-call-%",))[0][0]

print(f"F1  status={f1_status} contacts={f1_contacts} calls={f1_calls_n}")
print(f"F1  contact_wm={f1_contact_wm} call_wm={f1_call_wm} leads={n_leads} calls={n_calls}")
print(f"F1  bootstrap asked modified_after={f1_adapter.contact_calls[0]}")

results["F1 bootstrap asked for the operator's floor, unclamped"] = f1_adapter.contact_calls[0] == CONTACT_FLOOR
results["F1 a contact older than the rolling window was imported"] = (
    indep("select count(*) from crm_lead where vanillasoft_id=%s", (f"{TAG}-old",))[0][0] == 1
)
results["F1 historical calls started at the explicit floor"] = f1_adapter.call_windows[0][0] == CALL_FLOOR
results["F1 the catch-up pass imported a contact the bootstrap never saw"] = (
    indep("select count(*) from crm_lead where vanillasoft_id=%s", (f"{TAG}-during",))[0][0] == 1
)
results["F1 counters describe both phases"] = f1_contacts == 3 and f1_calls_n == 3
results["F1 contact watermark is the last committed batch_end"] = f1_contact_wm == RECENT_MODIFIED
results["F1 call watermark advanced to the catch-up boundary"] = bool(
    f1_call_wm and datetime.fromisoformat(f1_call_wm.replace("Z", "+00:00")) > _now - timedelta(minutes=30)
)

# Immediate incremental replay — the whole point of the handoff.
replay_adapter = Adapter([f1_pages[0]], [f1_calls[0]])
replay_run = drive(f1_cid, replay_adapter, "run_connection")
replay_status = run_row(replay_run)[0]
n_leads_after = indep("select count(*) from crm_lead where vanillasoft_id like %s", (leads_like,))[0][0]
n_distinct_after = indep(
    "select count(distinct vanillasoft_id) from crm_lead where vanillasoft_id like %s", (leads_like,)
)[0][0]
n_calls_after = indep("select count(*) from plasticos_crm_call_event where external_id like %s", (f"{TAG}-call-%",))[0][
    0
]
n_refs = indep("select count(*) from plasticos_crm_external_ref where external_id like %s", (leads_like,))[0][0]
print(f"F1  replay status={replay_status} leads={n_leads_after} refs={n_refs} calls={n_calls_after}")

results["F1 replay immediately after the full import succeeds"] = replay_status == "success"
results["F1 replay created no duplicate lead"] = n_leads_after == n_distinct_after == n_leads == 3
results["F1 replay created no duplicate external ref"] = n_refs == 3
results["F1 replay created no duplicate call event"] = n_calls_after == n_calls == 3
results["F1 watermark never rewound"] = watermarks(f1_cid)[0] == RECENT_MODIFIED


# ── F2 — the census verdict is evidence-based, and bad floors create nothing ─

f2_adapter = Adapter([[([lead("recentonly")], RECENT_MODIFIED, False)], []], [[], []])
f2_cid = make_connection("unproven census")
f2_run = drive(
    f2_cid, f2_adapter, "run_full_import", call_history_floor=CALL_FLOOR, contact_modified_floor=CONTACT_FLOOR
)
f2_status, _, _, f2_excerpt = run_row(f2_run)
f2_conn_error = indep("select last_error from plasticos_crm_connection where id=%s", (f2_cid,))[0][0]
print(f"F2  unproven status={f2_status}")

results["F2 an unproven census is recorded partial, not success"] = f2_status == "partial"
results["F2 the reason is durable on the run row"] = bool(f2_excerpt and "census unproven" in f2_excerpt)
results["F2 the operator sees it on the connection"] = bool(f2_conn_error and "census unproven" in f2_conn_error)
results["F2 a proven census is recorded success"] = f1_status == "success" and not f1_excerpt

f2b_cid = make_connection("bad floor")
runs_before = indep("select count(*) from plasticos_crm_sync_run where connection_id=%s", (f2b_cid,))[0][0]
bad_floor_raised = False
try:
    drive(f2b_cid, Adapter([[]], [[]]), "run_full_import", call_history_floor="not-a-date")
except CrmFullImportArgumentError:
    bad_floor_raised = True
runs_after = indep("select count(*) from plasticos_crm_sync_run where connection_id=%s", (f2b_cid,))[0][0]
locks = indep("select count(*) from pg_locks where locktype='advisory'")[0][0]
print(f"F2  bad floor raised={bad_floor_raised} runs {runs_before}->{runs_after} advisory_locks={locks}")

results["F2 an unusable floor fails before any work begins"] = bad_floor_raised
results["F2 an unusable floor leaves no sync-run row"] = runs_after == runs_before
results["F2 an unusable floor leaves no advisory lock held"] = locks == 0


# ── F3 — delete / restore provenance against the real ORM ──────────────────

f3_cid = make_connection("lifecycle")
with odoo.modules.registry.Registry(DB).cursor() as cr:
    env = Environment(cr, odoo.SUPERUSER_ID, {})
    orch = SyncOrchestrator(env)
    conn = env["plasticos.crm.connection"].browse(f3_cid)

    synced = orch._upsert_lead(conn, lead("life-sync"))
    orch._upsert_lead(conn, lead("life-sync", deleted=True))

    manual = orch._upsert_lead(conn, lead("life-manual"))
    manual.active = False
    cr.commit()


def lead_state(suffix):
    return indep(
        "select active, vanillasoft_sync_archived from crm_lead where vanillasoft_id=%s",
        (f"{TAG}-{suffix}",),
    )[0]


archived_active, archived_flag = lead_state("life-sync")
manual_active, manual_flag = lead_state("life-manual")
print(f"F3  sync-archived active={archived_active} flag={archived_flag}")
print(f"F3  user-archived active={manual_active} flag={manual_flag}")

results["F3 a provider deletion archives the lead"] = archived_active is False
results["F3 the archive records that sync caused it"] = archived_flag is True
results["F3 a user's archive carries no sync provenance"] = manual_active is False and manual_flag is False

with odoo.modules.registry.Registry(DB).cursor() as cr:
    env = Environment(cr, odoo.SUPERUSER_ID, {})
    orch = SyncOrchestrator(env)
    conn = env["plasticos.crm.connection"].browse(f3_cid)
    # VanillaSoft reports both contacts as it always does: not deleted.
    orch._upsert_lead(conn, lead("life-sync"))
    orch._upsert_lead(conn, lead("life-manual"))
    cr.commit()

restored_active, restored_flag = lead_state("life-sync")
untouched_active, _ = lead_state("life-manual")
n_life = indep("select count(*) from crm_lead where vanillasoft_id like %s", (f"{TAG}-life-%",))[0][0]
print(f"F3  restored active={restored_active} flag={restored_flag} user-archived active={untouched_active}")

results["F3 a restored contact reactivates the sync-archived lead"] = restored_active is True
results["F3 restoring clears the provenance flag"] = restored_flag is False
results["F3 sync never reopens a lead a user archived"] = untouched_active is False
results["F3 the archived lead was matched, not duplicated"] = n_life == 2


print("\n" + "=" * 72)
for name, ok in results.items():
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
print("=" * 72)
sys.exit(0 if all(results.values()) else 1)
