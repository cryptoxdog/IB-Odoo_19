"""TransactionCase: lead upsert idempotency + orphan resolve (requires Odoo runtime)."""

from unittest.mock import MagicMock, patch

from odoo.addons.plasticos_crm_sync.adapters.base import CanonicalCall, CanonicalLead
from odoo.addons.plasticos_crm_sync.adapters.vanillasoft.adapter import contact_to_canonical
from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator, _new_outcomes
from odoo.exceptions import UserError
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

    def _lead(self, external_id, **kwargs):
        values = {
            "provider": "vanillasoft",
            "external_id": external_id,
            "company": "Test Co",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "lead_status_raw": "New",
        }
        values.update(kwargs)
        return CanonicalLead(**values)

    def _assert_identity_absent(self, external_id):
        leads = self.env["crm.lead"].with_context(active_test=False).search([("vanillasoft_id", "=", external_id)])
        refs = self.env["plasticos.crm.external.ref"].search(
            [("provider", "=", "vanillasoft"), ("external_id", "=", external_id), ("res_model", "=", "crm.lead")]
        )
        self.assertFalse(leads)
        self.assertFalse(refs)

    def test_failure_after_lead_insert_rolls_back_both_identity_rows(self):
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        dto = self._lead("vs-insert-fail")
        lead_model = type(self.env["crm.lead"])
        original = lead_model.create

        def boom(records, vals_list):
            original(records, vals_list)
            raise UserError("injected after lead insert")

        with patch.object(lead_model, "create", boom):
            returned = orch._upsert_lead(self.connection, dto)

        self.assertEqual(orch.last_lead_outcome, "failed")
        self.assertEqual(orch.outcomes["failed"], 1)
        self.assertEqual(orch.outcomes["created"], 0)
        self.assertFalse(returned)
        self.assertTrue(orch.error_rows)
        self._assert_identity_absent(dto.external_id)

        follow = orch._upsert_lead(self.connection, self._lead("vs-after-insert-fail"))
        self.assertEqual(orch.last_lead_outcome, "created")
        self.assertTrue(follow)
        self.assertEqual(follow.vanillasoft_id, "vs-after-insert-fail")

    def test_external_ref_create_failure_rolls_back_the_lead(self):
        orch = SyncOrchestrator(self.env)
        orch.outcomes = _new_outcomes()
        dto = self._lead("vs-ref-fail")
        ref_model = type(self.env["plasticos.crm.external.ref"])

        def boom(records, vals_list):
            raise UserError("injected ref failure")

        with patch.object(ref_model, "create", boom):
            returned = orch._upsert_lead(self.connection, dto)

        self.assertEqual(orch.last_lead_outcome, "failed")
        self.assertEqual(orch.outcomes["failed"], 1)
        self.assertEqual(orch.outcomes["created"], 0)
        self.assertFalse(returned)
        self._assert_identity_absent(dto.external_id)

    def test_usa_does_not_select_minor_outlying_islands(self):
        orch = SyncOrchestrator(self.env)
        us = self.env["res.country"].search([("code", "=", "US")], limit=1)
        um = self.env["res.country"].search([("code", "=", "UM")], limit=1)
        self.assertTrue(us)
        self.assertTrue(um)
        for raw in ("USA", "usa", "US", "United States", "United States Of America"):
            vals = orch._lead_vals_from_dto(self._lead("vs-country", country_code=raw, state_code="PA"))
            self.assertEqual(vals["country_id"], us.id, raw)
            state = self.env["res.country.state"].browse(vals["state_id"])
            self.assertEqual(state.code, "PA")
            self.assertEqual(state.country_id, us)
        minor = orch._lead_vals_from_dto(
            self._lead("vs-um", country_code="USA Minor Outlying Islands", state_code="PA")
        )
        self.assertEqual(minor["country_id"], um.id)
        self.assertFalse(minor["state_id"])

    def test_dead_lead_uses_the_existing_stage(self):
        orch = SyncOrchestrator(self.env)
        vals = orch._lead_vals_from_dto(self._lead("vs-dead", lead_status_raw="5=Dead Lead"))
        self.assertEqual(vals["stage_id"], self.env.ref("plasticos_crm_bridge.stage_dead_lead").id)

    def test_contact_name_collapses_whitespace(self):
        orch = SyncOrchestrator(self.env)
        spaced = orch._lead_vals_from_dto(self._lead("vs-name", first_name="  Ada   ", last_name=" \n Lovelace  "))
        self.assertEqual(spaced["contact_name"], "Ada Lovelace")
        blank = orch._lead_vals_from_dto(self._lead("vs-blank", first_name="   ", last_name="\t"))
        self.assertFalse(blank["contact_name"])

    def test_unmapped_source_and_owner_are_left_empty(self):
        self.env["res.users"].create({"name": "CRM3 Exact Owner", "login": "crm3-exact-owner"})
        self.env["res.users"].create({"name": "CRM3 Twin Owner", "login": "crm3-twin-a"})
        self.env["res.users"].create({"name": "CRM3 Twin Owner", "login": "crm3-twin-b"})
        orch = SyncOrchestrator(self.env)
        missing_source = orch._lead_vals_from_dto(self._lead("vs-source", lead_source_raw="Not A Mapped Source"))
        self.assertFalse(missing_source["source_id"])
        mapped = orch._lead_vals_from_dto(self._lead("vs-google", lead_source_raw="Google"))
        self.assertEqual(mapped["source_id"], self.env.ref("plasticos_crm_bridge.utm_source_google").id)
        exact = orch._lead_vals_from_dto(self._lead("vs-owner", owner_name="  CRM3 Exact Owner  "))
        self.assertEqual(self.env["res.users"].browse(exact["user_id"]).name, "CRM3 Exact Owner")
        self.assertFalse(orch._lead_vals_from_dto(self._lead("vs-missing", owner_name="No Such CRM3 Owner"))["user_id"])
        self.assertFalse(orch._lead_vals_from_dto(self._lead("vs-twin", owner_name="CRM3 Twin Owner"))["user_id"])

    def test_observed_aliases_land_on_native_lead_fields(self):
        self.env["res.users"].create({"name": "CRM3 Alias Owner", "login": "crm3-alias-owner"})
        dto = contact_to_canonical(
            {
                "contact_id": "vs-alias-land",
                "company": "Alias Co",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "address1": "9 Observed St",
                "postal_code": "30301",
                "city": "Atlanta",
                "state": "GA",
                "country": "USA",
                "lead_status": "5=Dead Lead",
                "lead_source_name": "Google",
                "contact_owner": "CRM3 Alias Owner",
                "phone_numbers": [
                    {"name": "business", "number": "555-100-0003"},
                    {"name": "direct", "number": "555-100-0001"},
                    {"name": "mobile 1", "number": "555-100-0002"},
                ],
            }
        )
        lead = SyncOrchestrator(self.env)._upsert_lead(self.connection, dto)
        self.assertEqual(lead.street, "9 Observed St")
        self.assertEqual(lead.zip, "30301")
        self.assertEqual(lead.phone, "555-100-0001")
        self.assertEqual(lead.mobile, "555-100-0002")
        self.assertEqual(lead.country_id.code, "US")
        self.assertEqual(lead.state_id.code, "GA")
        self.assertEqual(lead.stage_id, self.env.ref("plasticos_crm_bridge.stage_dead_lead"))
        self.assertEqual(lead.source_id, self.env.ref("plasticos_crm_bridge.utm_source_google"))
        self.assertEqual(lead.user_id.name, "CRM3 Alias Owner")
        self.assertEqual(
            len(
                self.env["plasticos.crm.external.ref"].search(
                    [("external_id", "=", "vs-alias-land"), ("res_model", "=", "crm.lead")]
                )
            ),
            1,
        )
