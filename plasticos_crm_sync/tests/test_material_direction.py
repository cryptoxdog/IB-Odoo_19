"""VanillaSoft direction, the single-capability link, and the broker refusal."""

from odoo.addons.plasticos_crm_sync.services.import_summary import review_report_lines
from odoo.addons.plasticos_crm_sync.services.orchestrator import (
    AI_BROKER_CONTEXT,
    MATERIAL_DIRECTION_REVIEW,
    SyncOrchestrator,
)
from odoo.tests import tagged

from .test_orchestrator_upsert import CrmSyncOrchestratorCase


@tagged("post_install", "-at_install")
class TestMaterialDirection(CrmSyncOrchestratorCase):
    def _land(self, external_id, site, custom_fields, env=None):
        orch = SyncOrchestrator(env or self.env)
        lead = orch._upsert_lead(self.connection, self._lead(external_id))
        lead.partner_id = site
        orch._upsert_lead(self.connection, self._lead(external_id, custom_fields=custom_fields))
        return orch

    def _profiles(self, site):
        return self.env["plasticos.material.profile"].search([("partner_id", "=", site.id)])

    def _capability(self, site, code):
        facility = self.env["plasticos.facility.profile"].search([("partner_id", "=", site.id)], limit=1)
        if not facility:
            facility = self.env["plasticos.facility.profile"].create({"partner_id": site.id})
        cap_type = self.env["plasticos.capability.type"].search([("code", "=", code)], limit=1)
        self.assertTrue(cap_type)
        return self.env["plasticos.capability"].create(
            {"facility_profile_id": facility.id, "capability_type_id": cap_type.id}
        )

    def test_supplier_is_out_and_buyer_is_in_and_a_replay_is_the_same_profile(self):
        supplier_site = self._facility("C5 Direction Supplier")
        buyer_site = self._facility("C5 Direction Buyer")
        supplier = self._land(
            "c5-dir-supplier",
            supplier_site,
            {"Materials": "HDPE Drums", "Buyer/Supplier": "Supplier"},
        )
        self._land("c5-dir-buyer", buyer_site, {"Materials": "LDPE Film", "Buyer/Supplier": "Buyer"})
        outgoing = self._profiles(supplier_site)
        incoming = self._profiles(buyer_site)
        self.assertEqual(outgoing.direction, "out")
        self.assertEqual(outgoing.polymer_id.code, "HDPE")
        self.assertEqual(incoming.direction, "in")
        self.assertEqual(incoming.form_id.code, "FILM")
        supplier._upsert_lead(
            self.connection,
            self._lead(
                "c5-dir-supplier",
                custom_fields={"Materials": "HDPE Drums", "Buyer/Supplier": "Supplier"},
            ),
        )
        self.assertEqual(self._profiles(supplier_site), outgoing)
        self.assertEqual(outgoing.direction, "out")

    def test_both_without_a_site_decision_stays_blank_and_is_listed(self):
        site = self._facility("C5 Direction Both")
        fields = {"Materials": "HDPE Drums, LDPE Film", "Buyer/Supplier": "Supplier, Buyer"}
        orch = self._land("c5-dir-both", site, fields)
        profiles = self._profiles(site)
        self.assertEqual(set(profiles.mapped("polymer_id.code")), {"HDPE", "LDPE"})
        self.assertEqual(set(profiles.mapped("direction")), {False})
        rows = [row for row in orch.error_rows if row.get("error_type") == MATERIAL_DIRECTION_REVIEW]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_ref"], "c5-dir-both")
        lines = review_report_lines({"errors": orch.error_rows})
        self.assertTrue(any("no direction" in line and "1 VanillaSoft" in line for line in lines))
        orch._upsert_lead(self.connection, self._lead("c5-dir-both", custom_fields=fields))
        self.assertEqual(self._profiles(site), profiles)
        self.assertEqual(
            len([row for row in orch.error_rows if row.get("error_type") == MATERIAL_DIRECTION_REVIEW]),
            1,
        )

    def test_both_on_a_pickup_site_is_out(self):
        site = self._facility("C5 Direction Pickup")
        site.erp_address_label = "PICK-UP"
        orch = self._land(
            "c5-dir-pickup",
            site,
            {"Materials": "HDPE Drums", "Buyer/Supplier": "Buyer and Supplier"},
        )
        self.assertEqual(self._profiles(site).direction, "out")
        self.assertFalse(any(row.get("error_type") == MATERIAL_DIRECTION_REVIEW for row in orch.error_rows))

    def test_the_single_capability_is_linked_and_two_are_not(self):
        site = self._facility("C5 Direction Link")
        only = self._capability(site, "shredding")
        self._land("c5-dir-link", site, {"Materials": "HDPE Drums", "Buyer/Supplier": "Supplier"})
        self.assertEqual(self._profiles(site).capability_id, only)
        other = self._facility("C5 Direction Unlinked")
        self._capability(other, "shredding")
        self._capability(other, "grinding")
        self._land("c5-dir-two", other, {"Materials": "PP Supersacs", "Buyer/Supplier": "Buyer"})
        self.assertFalse(self._profiles(other).capability_id)
        self.assertEqual(self._profiles(site).capability_id, only)

    def test_a_broker_write_without_direction_is_refused(self):
        site = self._facility("C5 Direction Broker")
        env = self.env(context={**self.env.context, AI_BROKER_CONTEXT: True})
        before = self.env["plasticos.material.profile"].search_count([])
        orch = self._land("c5-dir-broker", site, {"Materials": "HDPE Drums"}, env=env)
        self.assertEqual(self.env["plasticos.material.profile"].search_count([]), before)
        self.assertFalse(self._profiles(site))
        self.assertIn(
            "material write refused: direction is required",
            [row["message"] for row in orch.error_rows],
        )
        orch._upsert_lead(
            self.connection,
            self._lead(
                "c5-dir-broker",
                custom_fields={"Materials": "HDPE Drums", "Buyer/Supplier": "Buyer"},
            ),
        )
        stored = self._profiles(site)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored.direction, "in")
