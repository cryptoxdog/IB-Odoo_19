"""CRM-4 material sections and CRM-5 classification. Synthetic ORM readback."""

from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator
from odoo.tests import tagged

from .test_orchestrator_upsert import CrmSyncOrchestratorCase


@tagged("post_install", "-at_install")
class TestCrm45Classification(CrmSyncOrchestratorCase):
    def _messages(self, orch):
        return [row["message"] for row in orch.error_rows]

    def _profiles(self, lead):
        return self.env["plasticos.material.profile"].search([("facility_profile_id.crm_lead_id", "=", lead.id)])

    def test_unapproved_stages_stay_off_won_warm_and_dead(self):
        orch = SyncOrchestrator(self.env)
        cold = orch._upsert_lead(self.connection, self._lead("crm45-cold", lead_status_raw="2c=Qualified/COLD"))
        self.assertEqual(cold.stage_id, self.env.ref("plasticos_crm_bridge.stage_new"))
        self.assertNotEqual(cold.stage_id, self.env.ref("plasticos_crm_bridge.stage_qualified_warm"))
        self.assertIn("BLOCKED_STAGE_APPROVAL: 2c=Qualified/COLD", self._messages(orch))
        self.assertIn("VanillaSoft ContactID crm45-cold Lead Status: 2c=Qualified/COLD", cold.description or "")

        dnc = orch._upsert_lead(self.connection, self._lead("crm45-dnc", lead_status_raw="7=Do Not Call"))
        self.assertNotEqual(dnc.stage_id, self.env.ref("plasticos_crm_bridge.stage_dead_lead"))
        self.assertFalse(dnc.stage_id.is_won)

        hot = orch._upsert_lead(self.connection, self._lead("crm45-hot", lead_status_raw="2a=Qualified/HOT"))
        self.assertEqual(hot.stage_id, self.env.ref("plasticos_crm_bridge.stage_qualified_hot"))
        orch._upsert_lead(self.connection, self._lead("crm45-hot", lead_status_raw="5=Dead Lead"))
        self.assertEqual(hot.stage_id, self.env.ref("plasticos_crm_bridge.stage_qualified_hot"))

        won = self.env.ref("plasticos_crm_bridge.stage_active_supplier")
        hot.stage_id = won
        orch._upsert_lead(self.connection, self._lead("crm45-hot", lead_status_raw="1= Currently Working With"))
        self.assertEqual(hot.stage_id, won)
        self.assertTrue(hot.stage_id.is_won)

    def test_buyer_and_supplier_tags_do_not_touch_the_erp_partner(self):
        company = self.env["res.partner"].create({"name": "CRM45 Maker", "is_company": True})
        orch = SyncOrchestrator(self.env)
        dto = self._lead(
            "crm45-roles",
            company="CRM45 Maker",
            custom_fields={
                "Buyer/Supplier": "Supplier, Buyer",
                "Company Type": "Manufacturer",
            },
        )
        lead = orch._upsert_lead(self.connection, dto)
        lead.partner_id = company
        ranks = (company.supplier_rank, company.customer_rank, company.company_role)
        orch._upsert_lead(self.connection, dto)
        self.assertEqual(set(lead.tag_ids.mapped("name")), {"Buyer", "Supplier"})
        self.assertIn(self.env.ref("plasticos_crm_bridge.categ_manufacturer"), company.category_id)
        self.assertNotIn(self.env.ref("plasticos_crm_bridge.categ_buyer"), company.category_id)
        self.assertNotIn(self.env.ref("plasticos_crm_bridge.categ_supplier"), company.category_id)
        self.assertEqual((company.supplier_rank, company.customer_rank, company.company_role), ranks)
        self.assertEqual(company.company_type, "company")
        tag_ids = set(lead.tag_ids.ids)
        orch._upsert_lead(self.connection, dto)
        self.assertEqual(set(lead.tag_ids.ids), tag_ids)

    def test_unknown_role_and_company_type_overlap_are_blocked(self):
        company = self.env["res.partner"].create({"name": "CRM45 Broker", "is_company": True, "company_role": "broker"})
        orch = SyncOrchestrator(self.env)
        dto = self._lead(
            "crm45-block",
            custom_fields={"Buyer/Supplier": "End User", "Company Type": "Broker"},
        )
        lead = orch._upsert_lead(self.connection, dto)
        lead.partner_id = company
        orch.error_rows.clear()
        orch._upsert_lead(self.connection, dto)
        self.assertFalse(lead.tag_ids)
        self.assertNotIn(self.env.ref("plasticos_crm_bridge.categ_broker"), company.category_id)
        self.assertEqual(company.company_role, "broker")
        messages = self._messages(orch)
        self.assertIn("BLOCKED_ROLE_TOKEN: End User", messages)
        self.assertIn("BLOCKED_COMPANY_TYPE_SEMANTIC_OVERLAP: Broker", messages)

        alias = self._lead("crm45-alias", custom_fields={"Company Type": "Grinder_Processor"})
        aliased = orch._upsert_lead(self.connection, alias)
        aliased.partner_id = company
        company.company_role = False
        orch._upsert_lead(self.connection, alias)
        self.assertIn(self.env.ref("plasticos_crm_bridge.categ_grinder_processor"), company.category_id)

    def _erp_marker(self, partner, ct_id):
        self.env["ir.model.data"].create(
            {
                "module": "plasticos_transaction",
                "name": f"legacy_erp_contact_{ct_id}",
                "model": "res.partner",
                "res_id": partner.id,
                "noupdate": True,
            }
        )

    def test_person_without_a_lead_keeps_material_and_skips_crm_tags(self):
        facility = self._facility("CRM45 Person Facility")
        self.env["plasticos.facility.profile"].create({"partner_id": facility.id})
        person = self.env["res.partner"].create({"name": "CRM45 Person", "parent_id": facility.id})
        self._erp_marker(person, "4501")
        before = (person.category_id.ids, person.company_role, person.supplier_rank, person.customer_rank)
        orch = SyncOrchestrator(self.env)
        orch._crosswalk = {"crm45-person": "4501"}
        orch._crosswalk_ready = True
        leads_before = self.env["crm.lead"].with_context(active_test=False).search_count([])
        orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-person",
                custom_fields={"Materials": "HDPE Drums", "Buyer/Supplier": "Buyer"},
            ),
        )
        self.assertEqual(self.env["crm.lead"].with_context(active_test=False).search_count([]), leads_before)
        profiles = self.env["plasticos.material.profile"].search([("partner_id", "=", facility.id)])
        self.assertEqual(profiles.mapped("polymer_id.code"), ["HDPE"])
        self.assertEqual(profiles.form_id.code, "DRUMS")
        self.assertEqual(
            (person.category_id.ids, person.company_role, person.supplier_rank, person.customer_rank), before
        )
        self.assertIn("BLOCKED_NO_CRM_LEAD", self._messages(orch))

    def test_section_materials_do_not_broadcast_type_or_guess_pe(self):
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-mrf",
                custom_fields={"Materials (MRF's)": "HDPE Drums"},
            ),
        )
        profiles = self._profiles(lead)
        self.assertEqual(profiles.mapped("polymer_id.code"), ["HDPE"])
        self.assertEqual(profiles.form_id.code, "DRUMS")

        mixed = orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-two",
                custom_fields={"Materials": "HDPE Drums\nLDPE Film", "Type": "PE"},
            ),
        )
        codes = set(self._profiles(mixed).mapped("polymer_id.code"))
        self.assertEqual(codes, {"HDPE", "LDPE"})
        self.assertTrue(any("type hint is not contact-unique" in message for message in self._messages(orch)))
        bare = orch._upsert_lead(
            self.connection,
            self._lead("crm45-pe", custom_fields={"Materials": "PE\n1-7"}),
        )
        self.assertFalse(self._profiles(bare))
        self.assertTrue(any("BLOCKED_UNRESOLVED: PE" in message for message in self._messages(orch)))
        self.assertTrue(any("BLOCKED_UNRESOLVED: 1-7" in message for message in self._messages(orch)))

    def test_weight_loads_and_color_are_section_bound(self):
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-spec",
                custom_fields={
                    "Material (HDPE)": "HDPE Drums",
                    "Weight (HDPE)": "40000 lbs",
                    "Loads/Month (HDPE)": "4",
                    "Color (HDPE)": "Blue",
                },
            ),
        )
        profile = self._profiles(lead)
        self.assertEqual(len(profile), 1)
        self.assertEqual(profile.quantity_per_load_lbs, 40000)
        self.assertEqual(profile.loads_per_month, 4)
        self.assertEqual(profile.color_id.code, "BLUE")
        profile.quantity_per_load_lbs = 1000
        orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-spec",
                custom_fields={
                    "Material (HDPE)": "HDPE Drums",
                    "Weight (HDPE)": "2000 lbs",
                    "Loads/Month (HDPE)": "5+",
                    "Color (HDPE)": "Blue, Green",
                },
            ),
        )
        self.assertEqual(profile.quantity_per_load_lbs, 1000)
        self.assertEqual(profile.loads_per_month, 4)
        self.assertEqual(profile.color_id.code, "BLUE")

    def test_pps_notes_attach_only_to_a_distinguished_profile(self):
        orch = SyncOrchestrator(self.env)
        generic = orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-pps-generic",
                custom_fields={"Material (PPS)": "PP Supersacs", "Notes (PPS)": "PPS-PROFILE-ONLY"},
            ),
        )
        generic_profile = self._profiles(generic)
        self.assertEqual(generic_profile.polymer_id.code, "PP")
        self.assertNotIn("PPS-PROFILE-ONLY", generic_profile.freeform_notes or "")
        self.assertNotIn("PPS-PROFILE-ONLY", generic.description or "")
        self.assertIn("BLOCKED_PPS_PROFILE_IDENTITY", self._messages(orch))

        facility = self._facility("CRM45 Supersacs")
        self.env["plasticos.facility.profile"].create({"partner_id": facility.id})
        polymer = self.env["plasticos.polymer"].search([("code", "=", "PP")], limit=1)
        distinguished = self.env["plasticos.material.profile"].create(
            {
                "partner_id": facility.id,
                "polymer_id": polymer.id,
                "freeform_notes": "PP Supersacs (Lined)",
            }
        )
        bound = orch._upsert_lead(self.connection, self._lead("crm45-pps-bound"))
        bound.partner_id = facility
        orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-pps-bound",
                custom_fields={
                    "Previous Content (PPS)": "resin",
                    "Size (PPS)": "48 inch",
                    "Notes (PPS)": "lined only",
                },
            ),
        )
        notes = distinguished.freeform_notes or ""
        self.assertIn("VanillaSoft ContactID crm45-pps-bound Previous Content (PPS): resin", notes)
        self.assertIn("VanillaSoft ContactID crm45-pps-bound Size (PPS): 48 inch", notes)
        self.assertIn("VanillaSoft ContactID crm45-pps-bound Notes (PPS): lined only", notes)
        self.assertNotIn("lined only", bound.description or "")
