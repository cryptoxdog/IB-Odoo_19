"""TransactionCase: lead upsert idempotency + orphan resolve (requires Odoo runtime)."""

from unittest.mock import MagicMock

from odoo.addons.plasticos_crm_sync.adapters.base import CanonicalCall, CanonicalLead
from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCrmSyncOrchestrator(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connection = cls.env["plasticos.crm.connection"].create(
            {
                "name": "Test VS",
                "provider": "vanillasoft",
                "project_id": "139705",
                "enabled": False,
            }
        )

    def test_upsert_lead_idempotent(self):
        orch = SyncOrchestrator(self.env)
        dto = CanonicalLead(
            provider="vanillasoft",
            external_id="vs-1001",
            company="Test Co",
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            lead_status_raw="New",
        )
        lead1 = orch._upsert_lead(self.connection, dto)
        lead2 = orch._upsert_lead(self.connection, dto)
        self.assertEqual(lead1.id, lead2.id)
        refs = self.env["plasticos.crm.external.ref"].search(
            [
                ("provider", "=", "vanillasoft"),
                ("external_id", "=", "vs-1001"),
                ("res_model", "=", "crm.lead"),
            ]
        )
        self.assertEqual(len(refs), 1)
        self.assertEqual(lead1.vanillasoft_id, "vs-1001")

    def test_orphan_call_resolves_after_contact(self):
        orch = SyncOrchestrator(self.env)
        call = CanonicalCall(
            provider="vanillasoft",
            external_id="call-9",
            contact_external_id="vs-2002",
            call_datetime_utc="2026-08-01T12:00:00Z",
            duration_seconds=30,
            user_name="Rep",
            result_code="LM",
            comment="orphan",
        )
        orch._upsert_calls(self.connection, [call], None)
        orphans = self.env["plasticos.crm.sync.orphan"].search(
            [
                ("connection_id", "=", self.connection.id),
                ("resolved", "=", False),
                ("kind", "=", "call"),
            ]
        )
        self.assertEqual(len(orphans), 1)

        lead_dto = CanonicalLead(
            provider="vanillasoft",
            external_id="vs-2002",
            company="Later Co",
            first_name="Bob",
            last_name="Builder",
        )
        orch._upsert_lead(self.connection, lead_dto)
        resolved = orch._resolve_orphans(self.connection, MagicMock(), None)
        self.assertEqual(resolved, 1)
        event = self.env["plasticos.crm.call.event"].search(
            [("provider", "=", "vanillasoft"), ("external_id", "=", "call-9")],
            limit=1,
        )
        self.assertTrue(event)
        self.assertEqual(event.lead_id.vanillasoft_id, "vs-2002")
