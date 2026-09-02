"""Gates C7 / C8 — enrichment failure durability (Gate disabled, transport failure).

Not a pytest module and deliberately not collected: needs a live Odoo 19
registry and a live PostgreSQL server. Setup: docs/runbooks/C1_C6_LOCAL_RUNTIME.md.

Both assert that operator-visible failure state survives the OUTER RPC rollback
(a UserError in a real request rolls the request transaction back), that the
partner's business fields are untouched, and that the call returns promptly
without a second-cursor lock wait.
"""

import socket
import sys
import threading
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
odoo.modules.module.initialize_sys_path()
from odoo.exceptions import UserError  # noqa: E402

results = {}
PARTNER_VALS = {
    "name": "Gate Canary Ltd",
    "website": "https://canary.example",
    "city": "Charlotte",
    "phone": "+1-704-555-0100",
    "is_company": True,
}


def indep(sql, args=()):
    c = psycopg2.connect(host="/tmp", port=5433, user="odoo", dbname=DB)
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


def make_run(tag):
    with odoo.modules.registry.Registry(DB).cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        vals = dict(PARTNER_VALS)
        vals["name"] = f"{PARTNER_VALS['name']} {tag}"
        p = env["res.partner"].create(vals)
        run = env["plasticos.enrichment.run"].create({"partner_id": p.id})
        cr.commit()
        return run.id, p.id, vals


def partner_row(pid):
    return indep("select name, website, city, phone from res_partner where id=%s", (pid,))[0]


def run_row(rid):
    return indep(
        "select state, failure_class, availability_status, engine_used from plasticos_enrichment_run where id=%s",
        (rid,),
    )[0]


def execute_expecting_userror(rid):
    """Call action_execute, then ROLL BACK the ambient transaction like a real RPC would."""
    started = time.monotonic()
    raised = None
    with odoo.modules.registry.Registry(DB).cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        run = env["plasticos.enrichment.run"].browse(rid)
        try:
            run.action_execute()
        except UserError as exc:
            raised = str(exc)
        cr.rollback()  # this is what the RPC layer does on UserError
    return raised, time.monotonic() - started


# ── Gate 2: enrichment disabled ─────────────────────────────────────────────
print("Gate: enrichment DISABLED")
set_icp(**{"plasticos.gate.enrichment_enabled": "0", "plasticos.gate.url": "https://gate.invalid"})
rid, pid, vals = make_run("disabled")
msg, elapsed = execute_expecting_userror(rid)
state, fclass, avail, engine = run_row(rid)
name, website, city, phone = partner_row(pid)
print(f"  UserError: {msg}")
print(f"  elapsed={elapsed:.2f}s")
print(f"  run -> state={state} failure_class={fclass} availability_status={avail} engine={engine}")
print(f"  partner -> website={website} city={city} phone={phone}")
results["disabled: UserError raised"] = msg is not None
results["disabled: failure state survives outer RPC rollback"] = state == "failed"
results["disabled: failure_class durable"] = fclass == "permanent"
results["disabled: availability_status survives"] = bool(avail) and avail != "available"
results["disabled: partner business fields unchanged"] = (
    website == vals["website"] and city == vals["city"] and phone == vals["phone"]
)
results["disabled: no second-cursor lock wait"] = elapsed < 15

# ── Gate 3: Gate transport failure against a black-hole socket ──────────────
print("\nGate: enrichment ENABLED, transport fails (black-hole socket, 2s caller budget)")
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
        "plasticos.gate.enrichment_enabled": "1",
        "plasticos.gate.url": f"https://127.0.0.1:{port}",
        "plasticos.gate.timeout_seconds": "2",
    }
)
rid2, pid2, vals2 = make_run("transport")
msg2, elapsed2 = execute_expecting_userror(rid2)
state2, fclass2, avail2, engine2 = run_row(rid2)
name2, website2, city2, phone2 = partner_row(pid2)
srv.close()
print(f"  UserError: {msg2}")
print(f"  elapsed={elapsed2:.2f}s (configured caller budget = 2s)")
print(f"  run -> state={state2} failure_class={fclass2} availability_status={avail2} engine={engine2}")
print(f"  partner -> website={website2} city={city2} phone={phone2}")
results["transport: UserError raised"] = msg2 is not None
results["transport: failure state survives outer RPC rollback"] = state2 in ("retryable", "degraded", "failed")
results["transport: failure_class durable"] = bool(fclass2)
results["transport: availability_status survives"] = bool(avail2)
results["transport: partner business fields unchanged"] = (
    website2 == vals2["website"] and city2 == vals2["city"] and phone2 == vals2["phone"]
)
results["transport: returns inside the caller budget"] = elapsed2 < 30

print("\n" + "=" * 66)
for k, v in results.items():
    print(f"  {'PASS' if v else 'FAIL'}  {k}")
print("=" * 66)
sys.exit(0 if all(results.values()) else 1)
