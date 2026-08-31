"""Launch gates C1, C2, C4/C5 + a success regression, on a REAL runtime.

Not a pytest module and deliberately not collected: it needs a live Odoo 19
registry and a live PostgreSQL server. Setup is in
docs/runbooks/C1_C6_LOCAL_RUNTIME.md. Run it directly::

    /opt/odoo-venv/bin/python tests/runtime_gates/run_c1_c2_c4_c5.py

Every assertion is read over a psycopg2 connection Odoo does not own, so no
result here is read out of the transaction under test.
"""

from __future__ import annotations

import sys

import psycopg2

import odoo
import odoo.modules.module
from odoo.api import Environment
from odoo.tools import config

DB = "c1c6_test"
PG_HOST = "/tmp"
PG_PORT = 5433
PG_USER = "odoo"
ODOO_ADDONS = "/opt/odoo-src/odoo-19.0.post20260831/odoo/addons"
REPO = "/home/user/IB-Odoo_19"

config["db_host"] = PG_HOST
config["db_port"] = PG_PORT
config["db_user"] = PG_USER
config["addons_path"] = f"{ODOO_ADDONS},{REPO}"

# Must run before any odoo.addons.* import, or the addon is not importable.
odoo.modules.module.initialize_sys_path()

from odoo.addons.plasticos_crm_sync.adapters.base import (  # noqa: E402
    CanonicalLead,
    CrmAdapterError,
)
from odoo.addons.plasticos_crm_sync.services.orchestrator import (  # noqa: E402
    CrmSyncLockedError,
    SyncOrchestrator,
)


def query(sql: str, args: tuple = ()) -> list:
    """Read committed state over a connection Odoo does not own."""
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, dbname=DB)
    conn.set_session(autocommit=True)
    with conn.cursor() as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    conn.close()
    return rows


def make_connection(name: str) -> int:
    with odoo.modules.registry.Registry(DB).cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        record = env["plasticos.crm.connection"].create({"name": name, "provider": "vanillasoft", "active": True})
        cr.commit()
        return record.id


def lead(tag: str, index: int) -> CanonicalLead:
    return CanonicalLead(
        provider="vanillasoft",
        external_id=f"{tag}-{index}",
        company="Co",
        first_name="A",
        last_name="L",
        lead_status_raw="New",
    )


class _Adapter:
    provider = "vanillasoft"
    live = True

    def healthcheck(self) -> dict:
        return {}

    def iter_calls(self, **kwargs):
        return iter(())

    def iter_table_rows(self, contact_external_id):
        return iter(())


class HealthcheckFails(_Adapter):
    def healthcheck(self):
        raise CrmAdapterError("C1: source unreachable")

    def iter_contacts(self, **kwargs):
        return iter(())


class SecondPageFails(_Adapter):
    def iter_contacts(self, *, modified_after, limit=200):
        yield ([lead("g2", i) for i in range(50)], "2026-08-02T00:00:00Z", False)
        raise CrmAdapterError("C2: page 2 fails")


class OnePage(_Adapter):
    def __init__(self, probe=None):
        self.probe = probe
        self.tag = "g4"

    def iter_contacts(self, *, modified_after, limit=200):
        yield ([lead(self.tag, i) for i in range(5)], "2026-08-02T00:00:00Z", False)
        if self.probe:
            self.probe()


class Succeeds(_Adapter):
    def iter_contacts(self, *, modified_after, limit=200):
        yield ([lead("g5", i) for i in range(12)], "2026-08-02T00:00:00Z", False)


def run(connection_id: int, adapter, expect_raise=None):
    with odoo.modules.registry.Registry(DB).cursor() as cr:
        env = Environment(cr, odoo.SUPERUSER_ID, {})
        orchestrator = SyncOrchestrator(env)
        orchestrator._build_adapter = lambda c: adapter
        record = env["plasticos.crm.connection"].browse(connection_id)
        if expect_raise is None:
            return orchestrator.run_connection(record), True
        try:
            orchestrator.run_connection(record)
        except expect_raise:
            return None, True
        return None, False


def latest_run(connection_id: int):
    rows = query(
        "select status, contacts_upserted from plasticos_crm_sync_run where connection_id=%s order by id desc limit 1",
        (connection_id,),
    )
    return rows[0] if rows else None


def gate_c1() -> bool:
    connection_id = make_connection("C1")
    _, raised = run(connection_id, HealthcheckFails(), expect_raise=CrmAdapterError)
    row = latest_run(connection_id)
    print(f"C1: raised={raised} run={row}")
    return bool(raised and row and row[0] == "failed" and row[1] == 0)


def gate_c2() -> bool:
    connection_id = make_connection("C2")
    _, raised = run(connection_id, SecondPageFails(), expect_raise=CrmAdapterError)
    row = latest_run(connection_id)
    leads = query("select count(*) from crm_lead where vanillasoft_id like 'g2-%%'")[0][0]
    print(f"C2: raised={raised} run={row} committed_leads={leads}")
    return bool(raised and row and row[0] == "failed" and row[1] == 50 and leads == 50)


def gate_c4_c5() -> bool:
    """A second run on a separate PG backend must still be excluded after a page commit."""
    connection_id = make_connection("C45")
    outcome = {}

    def probe_after_commit():
        with odoo.modules.registry.Registry(DB).cursor() as cr:
            env = Environment(cr, odoo.SUPERUSER_ID, {})
            second = SyncOrchestrator(env)
            second._build_adapter = lambda c: OnePage()
            try:
                second.run_connection(env["plasticos.crm.connection"].browse(connection_id))
                outcome["locked"] = False
            except CrmSyncLockedError:
                outcome["locked"] = True

    run(connection_id, OnePage(probe=probe_after_commit))
    print(f"C4/C5: second run locked out = {outcome.get('locked')}")
    return outcome.get("locked") is True


def gate_success() -> bool:
    connection_id = make_connection("OK")
    result, _ = run(connection_id, Succeeds())
    row = query(
        "select status, contacts_upserted from plasticos_crm_sync_run where id=%s",
        (result.id,),
    )[0]
    print(f"success: run={row}")
    return row[0] == "success" and row[1] == 12


def main() -> int:
    gates = {
        "C1 sync-run durable + failed before any remote work": gate_c1,
        "C2 committed page + counter survive a later failure": gate_c2,
        "C4/C5 advisory lock still excludes after a page commit": gate_c4_c5,
        "success path still reports status + counter": gate_success,
    }
    results = {name: fn() for name, fn in gates.items()}
    print("\n" + "=" * 64)
    for name, passed in results.items():
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    print("=" * 64)
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
