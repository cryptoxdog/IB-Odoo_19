"""Odoo shell script: run with `odoo shell -d <clone> --no-http < this file`."""

from datetime import UTC, datetime, timedelta

from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator

env = globals().get("env")
conn = env["plasticos.crm.connection"].get_or_create_vanillasoft_connection()
adapter = SyncOrchestrator(env)._build_adapter(conn)
client = adapter.client
print("PROBE project", conn.project_id)
now = datetime.now(UTC)
for label, floor in [
    ("30d", now - timedelta(days=30)),
    ("31d", now - timedelta(days=31)),
    ("32d", now - timedelta(days=32)),
    ("60d", now - timedelta(days=60)),
    ("2019", datetime(2019, 1, 1, tzinfo=UTC)),
]:
    iso = floor.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        p = client.get_contacts(int(conn.project_id), iso, limit=1)
        rows = p.get("Contacts") or p.get("contacts") or p.get("Data") or []
        print(
            "PROBE",
            label,
            iso,
            "ok keys=",
            sorted(p)[:6],
            "rows=",
            len(rows) if isinstance(rows, list) else type(rows).__name__,
        )
    except Exception as e:
        print("PROBE", label, iso, "ERR", str(e)[:160])
