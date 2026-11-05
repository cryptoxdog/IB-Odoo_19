"""Gate W1 — concurrent identical provider admissions converge to one web lead (F187-07).

Not a pytest module and deliberately not collected: needs a live Odoo 19
registry and a live PostgreSQL server (`scripts/setup_local_runtime.sh`). Under
`TransactionCase` there is one cursor and one snapshot, so a unique-constraint
race between two sessions cannot even be expressed there.

Two real registry cursors, each in its own thread, admit the same Cognito
submission. The pre-check search is instrumented with a barrier so BOTH
sessions miss it before either flushes its INSERT — the exact window the audit
describes. The loser hits the `unique(lead_id)` violation on a savepoint; because
Odoo cursors run at REPEATABLE READ its snapshot predates the winner's commit,
so the model escalates with ``ConcurrencyError`` and the request layer
(``odoo.service.model.retrying``, driven here exactly as the HTTP/RPC dispatch
drives it) replays the admission in a fresh transaction, which then returns the
prior receipt. The assertion reads through an independent autocommit psycopg2
connection.

Run:
    SEAM_DB=<db with plasticos_web_leads installed> SEAM_PG_HOST=/tmp SEAM_PG_PORT=5433 SEAM_PG_USER=odoo \
      /opt/odoo-venv/bin/python tests/runtime_gates/run_web_lead_concurrent_admission.py
"""

import os
import sys
import threading
import time
import uuid

import psycopg2

import odoo
import odoo.modules.module
from odoo.api import Environment
from odoo.service.model import retrying
from odoo.tools import config

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _runtime_env import DB, PG_HOST, PG_PORT, PG_USER, bind_config  # noqa: E402

bind_config(config)
odoo.modules.module.initialize_sys_path()

SKIP_EXIT = 77
results = {}


def indep(sql, args=()):
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, dbname=DB)
    conn.set_session(autocommit=True)
    with conn.cursor() as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    conn.close()
    return rows


def require_web_lead_model():
    # Skip contract (rules/95): the gate's subject is `plasticos.web.lead`. If the
    # module is not installed in SEAM_DB there is nothing to drive; a stub would
    # assert nothing. Removal trigger: `-i plasticos_web_leads` into SEAM_DB.
    with odoo.modules.registry.Registry(DB).cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        if "plasticos.web.lead" in env:
            return
    print("SKIPPED  W1 — 'plasticos.web.lead' is not in this registry; install plasticos_web_leads into SEAM_DB.")
    sys.exit(SKIP_EXIT)


require_web_lead_model()

# ── Deterministic configuration: no external providers, explicit reviewer ─────
with odoo.modules.registry.Registry(DB).cursor() as cr:
    env = Environment(cr, odoo.SUPERUSER_ID, {})
    admin = env.ref("base.user_admin")
    env["plasticos.web.lead.config"].sudo().get_config().write(
        {"ai_enabled": False, "vision_enabled": False, "hot_intake_reviewer_id": admin.id}
    )
    cr.commit()

EXTERNAL_ID = f"W1-{uuid.uuid4().hex[:10].upper()}"
LEAD_ID = f"CG-{EXTERNAL_ID}"
PAYLOAD = {
    "Entry": {"Number": EXTERNAL_ID},
    "YourBusinessCompanyName": "Race Co",
    "DescribeYourMaterial": "HDPE pellets",
    "WhatIsTheSourceOfThisMaterial": "Manufacturing production scrap",
    "WhatIsTheQuantity": "2 loads per month",
    "WeightPerLoad": "40000 lbs",
    "AreThereAnyContaminants": "none",
    "UploadPhotosOfYourScrapUpTo10": [],
}

# ── Instrument the pre-check so both sessions miss it before either inserts ──
from odoo.addons.plasticos_web_leads.models.web_lead import PlasticosWebLead  # noqa: E402

_original_find = PlasticosWebLead._find_existing_lead
_barrier = threading.Barrier(2, timeout=30)
_local = threading.local()


def _racing_find(self, lead_id):
    found = _original_find(self, lead_id)
    # Only the FIRST pre-check of each session waits: the recovery re-query after
    # the unique violation must proceed immediately.
    if not getattr(_local, "waited", False):
        _local.waited = True
        try:
            _barrier.wait()
        except threading.BrokenBarrierError:
            pass
    return found


PlasticosWebLead._find_existing_lead = _racing_find

outcome = {}


def admit(tag):
    started = time.monotonic()
    attempts = {"n": 0}
    try:
        with odoo.modules.registry.Registry(DB).cursor() as cr:
            env = Environment(cr, odoo.SUPERUSER_ID, {})

            def _once():
                attempts["n"] += 1
                # Mirror a real request: an auth read precedes admission, so the
                # REPEATABLE READ snapshot is already taken before the pre-check.
                endpoint_active = env["plasticos.web.lead.config"].sudo().get_config().is_active
                if not endpoint_active:
                    raise RuntimeError("web-lead endpoint is disabled in SEAM_DB")
                lead = env["plasticos.web.lead"].create_from_cognito(PAYLOAD)
                return lead.lead_id, lead.id, lead.state

            # odoo.service.model.retrying is what HTTP and RPC dispatch wrap every
            # request in; a ConcurrencyError raised by the model is replayed here.
            lead_id, rec_id, state = retrying(_once, env)
            cr.commit()
        outcome[tag] = {"lead_id": lead_id, "id": rec_id, "state": state, "error": None}
    except Exception as exc:  # A raised exception is the defect this gate hunts.
        outcome[tag] = {"lead_id": None, "id": None, "state": None, "error": f"{type(exc).__name__}: {exc}"}
    outcome[tag]["attempts"] = attempts["n"]
    outcome[tag]["elapsed"] = time.monotonic() - started


print(f"Gate W1: two concurrent admissions of {LEAD_ID}")
threads = [threading.Thread(target=admit, args=(tag,), daemon=True) for tag in ("A", "B")]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join(timeout=120)

PlasticosWebLead._find_existing_lead = _original_find

for tag in ("A", "B"):
    row = outcome.get(tag, {"error": "thread did not finish"})
    print(f"  session {tag}: {row}")

rows = indep("select id, lead_id, state, provider_external_id from plasticos_web_lead where lead_id=%s", (LEAD_ID,))
print(f"  committed rows for {LEAD_ID}: {rows}")

ids = {outcome.get(tag, {}).get("id") for tag in ("A", "B")}
errors = [outcome.get(tag, {}).get("error") for tag in ("A", "B")]
results["both sessions returned without an exception"] = all(error is None for error in errors)
results["exactly one committed lead for the identity"] = len(rows) == 1
results["both sessions returned the same lead id"] = len(ids) == 1 and None not in ids
results["returned lead is the committed row"] = bool(rows) and rows[0][0] in ids
results["committed lead is not in error state"] = bool(rows) and rows[0][2] != "error"
results["the race was real: one session needed a replay"] = any(
    (outcome.get(tag, {}).get("attempts") or 0) > 1 for tag in ("A", "B")
)
results["loser converged inside the caller budget"] = all(
    (outcome.get(tag, {}).get("elapsed") or 999) < 60 for tag in ("A", "B")
)

print("\n" + "=" * 66)
for key, value in results.items():
    print(f"  {'PASS' if value else 'FAIL'}  {key}")
print("=" * 66)
sys.exit(0 if all(results.values()) else 1)
