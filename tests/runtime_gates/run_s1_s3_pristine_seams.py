"""Launch gates S1, S2, S3 — pristine operator seams, on a REAL runtime.

Not a pytest module and deliberately not collected: it needs a live Odoo 19
registry and a live PostgreSQL server. Setup is in
docs/runbooks/C1_C6_LOCAL_RUNTIME.md. Run it directly::

    /opt/odoo-venv/bin/python tests/runtime_gates/run_s1_s3_pristine_seams.py

Where C1-C6 prove the orchestrator's internals, these three prove the seams an
operator actually crosses on a database that has never synced before:

    S1  Settings -> "Run VanillaSoft sync" with no connection yet
    S2  authenticated webhook -> elevated environment -> orchestrator
    S3  LegacyErp contact import -> res.partner against the installed registry

Each of the three defects these gates cover is invisible to the collected
suite by construction, and the reason differs per gate -- see the docstring on
each `gate_*` function.

Only the external CRM network boundary is stubbed, by a loopback HTTP server
(`client.require_secure_endpoint` permits plaintext http for loopback exactly
so a test endpoint needs no TLS). The controller, the Odoo environment, the
cursor boundary and the model registry are all real.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

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

WEBHOOK_TOKEN = "s2-webhook-token-not-a-real-secret"
PROJECT_ID = "139705"
S2_CONTACT_ID = "770001"
HTTP_PORT = int(os.environ.get("SEAM_ODOO_HTTP_PORT", "8169"))


# ----------------------------------------------------------------------
# Assertions read committed state over a connection Odoo does not own.
# ----------------------------------------------------------------------
def query(sql: str, args: tuple = ()) -> list:
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, dbname=DB)
    conn.set_session(autocommit=True)
    with conn.cursor() as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    conn.close()
    return rows


def execute(sql: str, args: tuple = ()) -> None:
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, dbname=DB)
    conn.set_session(autocommit=True)
    with conn.cursor() as cur:
        cur.execute(sql, args)
    conn.close()


def odoo_env():
    return odoo.modules.registry.Registry(DB).cursor()


# ----------------------------------------------------------------------
# Stubbed CRM network boundary (the ONLY thing these gates fake).
# ----------------------------------------------------------------------
CONTACT_PAYLOAD = {
    "contact_id": S2_CONTACT_ID,
    "company": "Seam Test Plastics",
    "first_name": "Dana",
    "last_name": "Ortiz",
    "email": "dana@example.invalid",
    "phone": "+1-555-0100",
    "modified_date_time_utc": "2026-09-01T00:00:00Z",
    "custom_fields": [{"name": "Lead Status", "value": "New"}],
}


class _StubHandler(BaseHTTPRequestHandler):
    def _send(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        path = urllib.parse.urlsplit(self.path).path
        lowered = path.lower()
        if lowered.endswith("/verifykey"):
            return self._send({"status": "ok"})
        if lowered.endswith("/callhistory") or lowered.endswith("/getcallhistory"):
            return self._send({"call_histories": []})
        if "/customtables" in lowered:
            return self._send({"custom_tables": []})
        if "/contacts/" in lowered:
            return self._send(CONTACT_PAYLOAD)
        if lowered.endswith("/contacts"):
            return self._send({"contacts": [CONTACT_PAYLOAD], "partial_fulfillment": False})
        return self._send({"error": "unhandled", "path": path}, status=404)

    def log_message(self, *args):  # silence per-request logging
        return


class StubCrm:
    """Loopback VanillaSoft. `require_secure_endpoint` allows http on loopback."""

    def __init__(self):
        self.server = HTTPServer(("127.0.0.1", 0), _StubHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    @property
    def root(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def configure_crm(root_endpoint: str) -> None:
    with odoo_env() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        icp = env["ir.config_parameter"].sudo()
        icp.set_param("plasticos_crm_sync.vanillasoft_api_key", "s1-key-not-a-real-secret")
        icp.set_param("plasticos_crm_sync.vanillasoft_root_endpoint", root_endpoint)
        icp.set_param("plasticos_crm_sync.vanillasoft_project_id", PROJECT_ID)
        icp.set_param("plasticos_crm_sync.webhook_token", WEBHOOK_TOKEN)
        cr.commit()


def make_pristine() -> None:
    """Return the CRM tables to their never-synced state.

    A first-run defect is only observable from a database with no connection
    row, which is exactly the state every existing gate skips past by creating
    and committing a connection before it starts.
    """
    execute("delete from plasticos_crm_sync_run")
    execute("delete from plasticos_crm_external_table_row")
    execute("delete from plasticos_crm_sync_orphan")
    execute("delete from plasticos_crm_external_ref")
    execute("delete from plasticos_crm_connection")


# ----------------------------------------------------------------------
# S1 - first-run Settings sync across the orchestrator's owned cursor
# ----------------------------------------------------------------------
def gate_s1(stub: StubCrm) -> bool:
    """First run from Settings: create the connection and sync it in one RPC.

    Why the collected suite cannot see this: `test_settings_import_action.py`
    patches `action_sync_now`, so the orchestrator never runs and no second
    cursor is ever opened. And under `TransactionCase` it could not fail even
    unpatched -- `registry.cursor()` hands back the test cursor, so the INSERT
    that carries the foreign key runs in the same transaction that created the
    connection and sees it.

    On a real server the connection is created in the Settings transaction and
    `_create_sync_run_durable` inserts its audit row on a cursor of its own.
    An uncommitted parent is invisible to that second transaction, so the FK
    fails and the operator's first sync dies before any work is attempted.
    """
    make_pristine()
    configure_crm(stub.root)
    assert not query("select id from plasticos_crm_connection"), "not pristine"

    with odoo_env() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        settings = env["res.config.settings"].create(
            {
                "plasticos_crm_sync_vanillasoft_api_key": "s1-key-not-a-real-secret",
                "plasticos_crm_sync_vanillasoft_root_endpoint": stub.root,
                "plasticos_crm_sync_vanillasoft_project_id": PROJECT_ID,
            }
        )
        settings.action_plasticos_crm_sync_run_vanillasoft()
        cr.commit()

    connections = query("select id from plasticos_crm_connection")
    runs = query(
        "select r.status, r.connection_id from plasticos_crm_sync_run r "
        "join plasticos_crm_connection c on c.id = r.connection_id order by r.id"
    )
    ok = len(connections) == 1 and len(runs) == 1 and runs[0][0] == "success"
    print(f"S1: connections={len(connections)} runs={runs}")

    # Idempotency: a second press reuses the connection, adds one more run.
    with odoo_env() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        settings = env["res.config.settings"].create(
            {
                "plasticos_crm_sync_vanillasoft_api_key": "s1-key-not-a-real-secret",
                "plasticos_crm_sync_vanillasoft_root_endpoint": stub.root,
                "plasticos_crm_sync_vanillasoft_project_id": PROJECT_ID,
            }
        )
        settings.action_plasticos_crm_sync_run_vanillasoft()
        cr.commit()

    connections_after = query("select id from plasticos_crm_connection")
    runs_after = query("select status from plasticos_crm_sync_run order by id")
    replay_ok = (
        len(connections_after) == 1
        and connections_after[0][0] == connections[0][0]
        and len(runs_after) == 2
        and all(status == "success" for (status,) in runs_after)
    )
    print(f"S1 replay: connections={len(connections_after)} runs={[r[0] for r in runs_after]}")
    return bool(ok and replay_ok)


# ----------------------------------------------------------------------
# S2 - authenticated webhook reaches the orchestrator with a valid Environment
# ----------------------------------------------------------------------
def post(path: str, body: dict, timeout: int = 30):
    data = json.dumps(body).encode()
    req = urllib.request.Request(  # noqa: S310 - loopback test server
        f"http://127.0.0.1:{HTTP_PORT}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def start_odoo_http(log_path: str):
    binary = shutil.which("odoo") or os.path.join(os.path.dirname(sys.executable), "odoo")
    log = open(log_path, "wb")  # noqa: SIM115 - closed by stop_odoo_http
    proc = subprocess.Popen(
        [
            binary,
            "-d",
            DB,
            f"--db_host={PG_HOST}",
            f"--db_port={PG_PORT}",
            f"--db_user={PG_USER}",
            f"--addons-path={ODOO_ADDONS},{REPO}",
            f"--http-port={HTTP_PORT}",
            "--workers=0",
            "--max-cron-threads=0",
            "--log-level=warn",
        ],
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    for _ in range(120):
        if proc.poll() is not None:
            raise RuntimeError(f"odoo http server exited early; see {log_path}")
        try:
            urllib.request.urlopen(  # noqa: S310
                f"http://127.0.0.1:{HTTP_PORT}/web/login", timeout=2
            )
            return proc, log
        except urllib.error.HTTPError:
            return proc, log
        except Exception:  # noqa: BLE001 - server not up yet
            time.sleep(1)
    raise RuntimeError(f"odoo http server did not become ready; see {log_path}")


def stop_odoo_http(proc, log) -> None:
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()


def gate_s2(stub: StubCrm, log_path: str) -> bool:
    """The webhook over real HTTP, through Odoo's real dispatcher.

    Why the collected suite cannot see this: there is no test anywhere in the
    repository that exercises this controller. The defect is an invalid
    elevation API -- `Environment` has no `sudo()`, that is a recordset method
    -- so it raises only when the route body actually executes.

    The route's `except Exception` turns any failure into a 500, so a status
    code alone does not separate "environment API is wrong" from "the CRM is
    unreachable". The stub CRM removes the second possibility: with a valid
    environment this path now has to reach 200 and land a lead.
    """
    make_pristine()
    configure_crm(stub.root)
    route = "/plasticos/crm_sync/vanillasoft/weblead"

    no_token = post(route, {"ContactID": S2_CONTACT_ID})
    bad_token = post(f"{route}?token=wrong-token", {"ContactID": S2_CONTACT_ID})
    no_contact = post(f"{route}?token={WEBHOOK_TOKEN}", {})
    good = post(f"{route}?token={WEBHOOK_TOKEN}", {"ContactID": S2_CONTACT_ID})

    lead_sql = (
        "select l.id from crm_lead l join plasticos_crm_external_ref r "
        "on r.lead_id = l.id where r.external_id = %s and r.provider = 'vanillasoft'"
    )
    leads = query(lead_sql, (S2_CONTACT_ID,))
    # Replay: the same webhook twice must upsert, never duplicate.
    replay = post(f"{route}?token={WEBHOOK_TOKEN}", {"ContactID": S2_CONTACT_ID})
    leads_after = query(lead_sql, (S2_CONTACT_ID,))

    env_api_error = False
    with open(log_path, encoding="utf-8", errors="replace") as handle:
        env_api_error = "'Environment' object has no attribute 'sudo'" in handle.read()

    print(
        f"S2: no_token={no_token[0]} bad_token={bad_token[0]} no_contact={no_contact[0]} "
        f"authenticated={good[0]} leads={len(leads)} replay={replay[0]} leads_after={len(leads_after)} "
        f"env_api_error_in_log={env_api_error}"
    )
    return bool(
        no_token[0] == 401
        and bad_token[0] == 401
        and no_contact[0] == 400
        and good[0] == 200
        and len(leads) == 1
        and replay[0] == 200
        and len(leads_after) == 1
        and not env_api_error
    )


# ----------------------------------------------------------------------
# S3 - LegacyErp contact import against the installed res.partner registry
# ----------------------------------------------------------------------
def gate_s3() -> bool:
    """Import a contact carrying both a business and a mobile number.

    Why the collected suite cannot see this: the LegacyErp contract tests parse
    the source with `ast` and never build a registry, and the `pure-python`
    CI tier has no Odoo at all. The `_upsert` update path silently drops a
    field missing from `_fields`, so only a *create* -- a first import --
    raises, and only against a registry where `res.partner.mobile` is absent,
    which is every stock Odoo 19.
    """
    from odoo.addons.plasticos_transaction.legacy_erp import report as report_module
    from odoo.addons.plasticos_transaction.legacy_erp import source_index

    business_phone = "+1-555-0111"
    mobile_phone = "+1-555-0222"
    cp_id = "S3CP"
    contact_id = "S3CONTACT"

    # Re-runnable, and deterministic about WHICH path is exercised. `_upsert`
    # routes an existing record to `write()`, where `_differs` drops a field
    # missing from `_fields` silently -- so a leftover partner from an earlier
    # execution would hide the create-path failure behind a quiet no-op.
    execute(
        "delete from res_partner where id in ("
        "  select res_id from ir_model_data where model = 'res.partner' and name = %s)",
        (f"legacy_erp_contact_{contact_id}",),
    )
    execute(
        "delete from ir_model_data where model = 'res.partner' and name = %s",
        (f"legacy_erp_contact_{contact_id}",),
    )

    with odoo_env() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        partner_model = env["res.partner"]
        registry_has_mobile = "mobile" in partner_model._fields

        company = partner_model.create({"name": "Seam Test Counterparty", "is_company": True})
        index = source_index.SourceIndex()
        index.contacts = {
            contact_id: {
                "CT_ID": contact_id,
                "CpID": cp_id,
                "ContactNm": "Dana Ortiz",
                "Email": "dana@example.invalid",
                "PhoneBusiness": business_phone,
                "PhoneMobile": mobile_phone,
                "PhoneOther": "+1-555-0333",
                "Notes": "imported by S3",
                "IsActive": "Y",
                "Location": "",
            }
        }
        index.contacts_by_cp = {cp_id: [contact_id]}

        service = env["plasticos.legacy_erp.import"]
        report = report_module.ImportReport()
        # Real service method, real registry, real create().
        service._import_contacts(index, report, {cp_id: company.id}, {}, False)
        cr.commit()

        # Replay must not duplicate: identity is the ir.model.data marker.
        report_two = report_module.ImportReport()
        service._import_contacts(index, report_two, {cp_id: company.id}, {}, False)
        cr.commit()

    rows = query(
        "select p.id, p.phone, p.comment from res_partner p "
        "join ir_model_data d on d.res_id = p.id and d.model = 'res.partner' "
        "where d.name = %s",
        (f"legacy_erp_contact_{contact_id}",),
    )
    if len(rows) != 1:
        print(f"S3: expected exactly one imported partner, got {len(rows)}")
        return False

    _, phone, comment = rows[0]
    comment_text = comment or ""
    business_preserved = phone == business_phone
    mobile_retained = registry_has_mobile or mobile_phone in comment_text
    # The business number must never be displaced by the mobile one.
    not_overwritten = phone != mobile_phone

    print(
        f"S3: registry_has_mobile={registry_has_mobile} phone={phone!r} "
        f"mobile_retained={mobile_retained} business_preserved={business_preserved} "
        f"partners={len(rows)}"
    )
    return bool(business_preserved and mobile_retained and not_overwritten)


def attempt(name: str, fn, *args) -> bool:
    """Run one gate. An exception is the gate FAILING, never the run aborting.

    A defect these gates exist to catch can surface as a raised database error
    rather than a false assertion, and one gate crashing must not hide the
    verdict of the other two. The exception is reported and the gate is FAIL --
    it is never swallowed into a pass.
    """
    try:
        return bool(fn(*args))
    except Exception as exc:  # noqa: BLE001 - a crash IS the failure signal
        print(f"{name}: raised {type(exc).__name__}: {str(exc).strip().splitlines()[0]}")
        return False


def main() -> int:
    if not ODOO_SRC or not os.path.isdir(ODOO_ADDONS):
        print(f"odoo source not found (looked for {ODOO_ADDONS}); see C1_C6_LOCAL_RUNTIME.md")
        return 2

    log_path = os.environ.get("SEAM_HTTP_LOG", "/tmp/seam_odoo_http.log")
    results = {}
    with StubCrm() as stub:
        results["S1 first-run Settings sync crosses the owned cursor"] = attempt("S1", gate_s1, stub)
        results["S3 legacy contact import matches the installed registry"] = attempt("S3", gate_s3)
        proc, log = start_odoo_http(log_path)
        try:
            results["S2 authenticated webhook builds a valid Environment"] = attempt("S2", gate_s2, stub, log_path)
        finally:
            stop_odoo_http(proc, log)

    print("\n" + "=" * 64)
    for name, passed in results.items():
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    print("=" * 64)
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
