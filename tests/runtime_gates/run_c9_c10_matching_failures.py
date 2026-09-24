"""Gates C9 / C10 — Gate matching failure durability (Gate disabled, transport failure).

Not a pytest module and deliberately not collected: needs a live Odoo 19
registry and a live PostgreSQL server. Setup: docs/runbooks/C1_C6_LOCAL_RUNTIME.md.

Both drive the operator entry point (`plasticos.intake.action_match_to_buyers`)
and assert, from a session Odoo does not own, that the classified
`plasticos.match.run` failure receipt and the operator note on the intake
survive the OUTER RPC rollback (a UserError in a real request rolls the request
transaction back), that no match result, intake match line, intake status
change or partner rank change happens (no local scoring, no commercial
mutation), that operator retry produces a new attempt bound to the prior run,
and that the call returns promptly without a second-cursor lock wait.
"""

import os
import socket
import sys
import threading
import time

import psycopg2

import odoo
import odoo.modules.module
from odoo.api import Environment
from odoo.tools import config

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _runtime_env import DB, PG_HOST, PG_PORT, PG_USER, bind_config  # noqa: E402

bind_config(config)

odoo.modules.module.initialize_sys_path()
from odoo.exceptions import UserError  # noqa: E402

results = {}
SUPPLIER_VALS = {
    "name": "Gate Match Canary Supplier",
    "website": "https://match-canary.example",
    "city": "Charlotte",
    "phone": "+1-704-555-0200",
    "is_company": True,
    "supplier_rank": 1,
    "customer_rank": 0,
}

# Skip contract (rules/95): C9 and C10 drive `plasticos.match.run`, which lives
# in `plasticos_matching` -> `plasticos_gate`, and that module declares the
# PRIVATE `constellation_node_sdk` in external_dependencies. Where the SDK is
# absent the module cannot install, so the model does not exist and this gate
# has nothing to drive.
#
#   Condition:  'plasticos.match.run' absent from the registry.
#   Why not a fixture: the gate's whole subject is real Gate transport failure
#     against the real match-run model and the real intake action. A stub for
#     the model under test would assert nothing (see this directory's README).
#   Removal trigger: install constellation_node_sdk, then -i plasticos_matching.
#     C1-C6, F1-F3 and S1-S3 need no SDK and still run, so an unrelated failure
#     cannot hide behind this skip.
#
# Exit 77 (the autotools "skipped" convention) so `make runtime-gates` counts it
# as SKIPPED rather than PASSED -- a gate that did not run must never read green.
SKIP_EXIT = 77


def require_matching_model() -> None:
    with odoo.modules.registry.Registry(DB).cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        if "plasticos.match.run" in env:
            return
    print(
        "SKIPPED  C9/C10 — 'plasticos.match.run' is not in this registry.\n"
        "         plasticos_matching -> plasticos_gate requires the private\n"
        "         constellation_node_sdk (external_dependencies). Install it and\n"
        "         `-i plasticos_matching`, then re-run. See\n"
        "         docs/runbooks/C1_C6_LOCAL_RUNTIME.md."
    )
    sys.exit(SKIP_EXIT)


require_matching_model()


def indep(sql, args=()):
    c = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, dbname=DB)
    c.set_session(autocommit=True)
    with c.cursor() as cur:
        cur.execute(sql, args)
        r = cur.fetchall()
    c.close()
    return r


def set_icp(**params):
    with odoo.modules.registry.Registry(DB).cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        for k, v in params.items():
            env["ir.config_parameter"].sudo().set_param(k.replace("__", "."), v)
        cr.commit()


def _ref_or_create(env, model, code, name):
    rec = env[model].search([("code", "=", code)], limit=1)
    return rec or env[model].create({"code": code, "name": name})


def make_intake(tag):
    """Supplier + material profile + intake, committed before the request under test."""
    with odoo.modules.registry.Registry(DB).cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        vals = dict(SUPPLIER_VALS)
        vals["name"] = f"{SUPPLIER_VALS['name']} {tag}"
        supplier = env["res.partner"].create(vals)
        polymer = _ref_or_create(env, "plasticos.polymer", "HDPE", "HDPE")
        form = _ref_or_create(env, "plasticos.material.form", "pellet", "Pellet")
        profile = env["plasticos.material.profile"].create(
            {"partner_id": supplier.id, "polymer_id": polymer.id, "form_id": form.id}
        )
        intake = env["plasticos.intake"].create(
            {
                "partner_id": supplier.id,
                "polymer_id": polymer.id,
                "form_id": form.id,
                "quantity_per_load_lbs": 40000,
                "material_profile_id": profile.id,
            }
        )
        cr.commit()
        return intake.id, supplier.id, vals


def partner_row(pid):
    return indep(
        "select name, website, city, phone, supplier_rank, customer_rank from res_partner where id=%s",
        (pid,),
    )[0]


def intake_row(iid):
    return indep("select status, match_count, best_match_score from plasticos_intake where id=%s", (iid,))[0]


def run_rows(iid):
    return indep(
        "select id, state, failure_class, availability_status, engine, request_attempt, retry_of_id, "
        "operation_id, request_fingerprint, gate_response_digest "
        "from plasticos_match_run where intake_id=%s order by id",
        (iid,),
    )


def projection_counts(iid):
    lines = indep("select count(*) from plasticos_intake_match where intake_id=%s", (iid,))[0][0]
    results_n = indep("select count(*) from plasticos_match_result where intake_id=%s", (iid,))[0][0]
    return lines, results_n


def note_count(iid, run_id):
    return indep(
        "select count(*) from mail_message where model='plasticos.intake' and res_id=%s and body like %s",
        (iid, f"%match run {run_id}.%"),
    )[0][0]


def drive_expecting_userror(iid, action):
    """Call the intake action, then ROLL BACK the ambient transaction like a real RPC would."""
    started = time.monotonic()
    raised = None
    with odoo.modules.registry.Registry(DB).cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        intake = env["plasticos.intake"].browse(iid)
        try:
            getattr(intake, action)()
        except UserError as exc:
            raised = str(exc)
        cr.rollback()  # this is what the RPC layer does on UserError
    return raised, time.monotonic() - started


def assert_no_scoring_or_commercial_mutation(prefix, iid, pid, vals):
    status, match_count, best_score = intake_row(iid)
    lines, results_n = projection_counts(iid)
    name, website, city, phone, supplier_rank, customer_rank = partner_row(pid)
    print(f"  intake -> status={status} match_count={match_count} best_match_score={best_score}")
    print(f"  projections -> intake_match_lines={lines} match_results={results_n}")
    print(f"  partner -> website={website} city={city} phone={phone} ranks={supplier_rank}/{customer_rank}")
    results[f"{prefix}: no match result / intake match line written (no local scoring)"] = lines == 0 and results_n == 0
    results[f"{prefix}: intake status and match counters unchanged"] = (
        status == "draft" and match_count == 0 and float(best_score or 0) == 0.0
    )
    results[f"{prefix}: partner business fields and ranks unchanged"] = (
        website == vals["website"]
        and city == vals["city"]
        and phone == vals["phone"]
        and supplier_rank == vals["supplier_rank"]
        and customer_rank == vals["customer_rank"]
    )


# The intake button is feature-gated separately from Gate availability.
set_icp(**{"plasticos.matching_engine.enabled": "1"})

# ── Gate C9: matching disabled ──────────────────────────────────────────────
print("Gate C9: matching DISABLED")
set_icp(**{"plasticos.gate.matching_enabled": "0", "plasticos.gate.url": "https://gate.invalid"})
iid, pid, vals = make_intake("disabled")
msg, elapsed = drive_expecting_userror(iid, "action_match_to_buyers")
rows = run_rows(iid)
print(f"  UserError: {msg}")
print(f"  elapsed={elapsed:.2f}s")
print(f"  runs -> {rows}")
results["disabled: UserError raised"] = msg is not None
results["disabled: exactly one failure receipt survives outer RPC rollback"] = len(rows) == 1
first = rows[0] if rows else (None,) * 10
run_id, state, fclass, avail, engine, attempt, retry_of, op_id, fingerprint, digest = first
results["disabled: state failed"] = state == "failed"
results["disabled: failure_class permanent"] = fclass == "permanent"
results["disabled: availability_status survives"] = avail == "matching_disabled"
results["disabled: engine gate, attempt 1, no Gate receipt (never dispatched)"] = (
    engine == "gate" and attempt == 1 and not op_id and not fingerprint and not digest
)
results["disabled: operator note on the intake survives"] = bool(run_id) and note_count(iid, run_id) == 1
results["disabled: UserError names the durable run"] = bool(run_id) and f"match run {run_id}" in (msg or "")
results["disabled: no second-cursor lock wait"] = elapsed < 15
assert_no_scoring_or_commercial_mutation("disabled", iid, pid, vals)

print("\nGate C9b: operator retry while still DISABLED")
msg_r, elapsed_r = drive_expecting_userror(iid, "action_retry_latest_match")
rows_r = run_rows(iid)
print(f"  UserError: {msg_r}")
print(f"  runs -> {rows_r}")
results["disabled retry: UserError raised"] = msg_r is not None
results["disabled retry: new durable attempt bound to the prior run"] = (
    len(rows_r) == 2
    and rows_r[1][1] == "failed"
    and rows_r[1][5] == 2
    and rows_r[1][6] == run_id
    and rows_r[0] == first
)
results["disabled retry: no second-cursor lock wait"] = elapsed_r < 15
assert_no_scoring_or_commercial_mutation("disabled retry", iid, pid, vals)

# ── Gate C10: Gate transport failure against a black-hole socket ─────────────
print("\nGate C10: matching ENABLED, transport fails (black-hole socket, 2s caller budget)")
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", 0))
srv.listen(8)
port = srv.getsockname()[1]
held = []


def accept_and_never_reply():
    while True:
        try:
            conn, _ = srv.accept()
            held.append(conn)  # accept, then say nothing
        except OSError:
            return


threading.Thread(target=accept_and_never_reply, daemon=True).start()

# 2s budget: proves the validated timeout actually reaches the HTTP client.
set_icp(
    **{
        "plasticos.gate.matching_enabled": "1",
        "plasticos.gate.url": f"https://127.0.0.1:{port}",
        "plasticos.gate.timeout_seconds": "2",
    }
)
iid2, pid2, vals2 = make_intake("transport")
msg2, elapsed2 = drive_expecting_userror(iid2, "action_match_to_buyers")
rows2 = run_rows(iid2)
srv.close()
print(f"  UserError: {msg2}")
print(f"  elapsed={elapsed2:.2f}s (configured caller budget = 2s)")
print(f"  runs -> {rows2}")
results["transport: UserError raised"] = msg2 is not None
results["transport: exactly one failure receipt survives outer RPC rollback"] = len(rows2) == 1
second = rows2[0] if rows2 else (None,) * 10
run_id2, state2, fclass2, avail2, engine2, attempt2, _retry2, op_id2, fingerprint2, digest2 = second
results["transport: failure state durable"] = state2 in ("retryable", "degraded", "failed")
results["transport: failure_class durable"] = bool(fclass2)
results["transport: availability_status survives"] = avail2 == "available"
results["transport: request receipt (operation identity + fingerprint) durable, no response digest"] = (
    bool(op_id2) and str(op_id2).startswith("odoo:matching:") and len(fingerprint2 or "") == 64 and not digest2
)
results["transport: operator note on the intake survives"] = bool(run_id2) and note_count(iid2, run_id2) == 1
results["transport: returns inside the caller budget"] = elapsed2 < 30
assert_no_scoring_or_commercial_mutation("transport", iid2, pid2, vals2)

print("\n" + "=" * 66)
for k, v in results.items():
    print(f"  {'PASS' if v else 'FAIL'}  {k}")
print("=" * 66)
sys.exit(0 if all(results.values()) else 1)
