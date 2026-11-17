"""CRM-4 material sections and CRM-5 classification. Synthetic ORM readback."""

from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo.addons.plasticos_crm_bridge.models.crm_mapping import COMPANY_TYPE_MAPPING, UNAPPROVED_LEAD_STATUSES
from odoo.addons.plasticos_crm_bridge.models.crm_tag_adoption import MISSING_ROLE_TAG_BINDING, role_tag_binding
from odoo.addons.plasticos_crm_sync.services.import_summary import (
    REQUIRED_MAPPING,
    build_run_summary,
    business_acceptance,
)
from odoo.addons.plasticos_crm_sync.services.orchestrator import SyncOrchestrator
from odoo.exceptions import UserError
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

        queued = self.env["mail.mail"]
        before_approved = queued.search([])
        orch._upsert_lead(self.connection, self._lead("crm45-mail-new", lead_status_raw="New"))
        approved_mails = queued.search([]) - before_approved
        before_dnc = queued.search([])
        dnc = orch._upsert_lead(self.connection, self._lead("crm45-dnc", lead_status_raw="7=Do Not Call"))
        self.assertEqual(dnc.stage_id, self.env.ref("plasticos_crm_bridge.stage_new"))
        self.assertNotEqual(dnc.stage_id, self.env.ref("plasticos_crm_bridge.stage_dead_lead"))
        self.assertFalse(dnc.stage_id.is_won)
        self.assertTrue(dnc.active)
        self.assertFalse(dnc.vanillasoft_sync_archived)
        self.assertEqual(dnc.vanillasoft_id, "crm45-dnc")
        self.assertIn("7=Do Not Call", dnc.description or "")
        self.assertIn("crm45-dnc", dnc.description or "")
        dnc_mails = queued.search([]) - before_dnc
        self.assertEqual(len(dnc_mails), len(approved_mails))
        self.assertFalse(any("blacklist" in (mail.subject or "").casefold() for mail in dnc_mails))

        hot = orch._upsert_lead(self.connection, self._lead("crm45-hot", lead_status_raw="2a=Qualified/HOT"))
        self.assertEqual(hot.stage_id, self.env.ref("crm.stage_lead2"))
        orch._upsert_lead(self.connection, self._lead("crm45-hot", lead_status_raw="5=Dead Lead"))
        self.assertEqual(hot.stage_id, self.env.ref("crm.stage_lead2"))

        won = self.env.ref("plasticos_crm_bridge.stage_active_supplier")
        hot.stage_id = won
        orch._upsert_lead(self.connection, self._lead("crm45-hot", lead_status_raw="1= Currently Working With"))
        self.assertEqual(hot.stage_id, won)
        self.assertTrue(hot.stage_id.is_won)

    def test_buyer_and_supplier_raise_ranks_on_the_linked_company_not_erp_categories(self):
        # Operator D32/D33 (C1 C4): a Buyer at New becomes a partner; the existing company is
        # linked (never duplicated) and its ranks rise. The ERP Buyer/Supplier categories stay untouched.
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
        self.assertEqual(lead.partner_id, company)
        role = company.company_role
        orch._upsert_lead(self.connection, dto)
        self.assertEqual(set(lead.tag_ids.mapped("name")) - {"Manufacturer"}, {"Buyer", "Supplier"})
        self.assertIn(self.env.ref("plasticos_crm_bridge.categ_manufacturer"), company.category_id)
        self.assertNotIn(self.env.ref("plasticos_crm_bridge.categ_buyer"), company.category_id)
        self.assertNotIn(self.env.ref("plasticos_crm_bridge.categ_supplier"), company.category_id)
        self.assertGreaterEqual(company.supplier_rank, 1)
        self.assertGreaterEqual(company.customer_rank, 1)
        self.assertEqual(company.company_role, role)
        self.assertEqual(self.env["res.partner"].search_count([("name", "=", "CRM45 Maker")]), 1)
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
        self.assertEqual(profiles.material_grade_id.code, "DRUMS")
        self.assertEqual(
            (person.category_id.ids, person.company_role, person.supplier_rank, person.customer_rank), before
        )
        self.assertIn("BLOCKED_NO_CRM_LEAD", self._messages(orch))

    def _approved_person_upsert(self, person, external_id, ct_id):
        self._erp_marker(person, ct_id)
        orch = SyncOrchestrator(self.env)
        orch._crosswalk = {external_id: ct_id}
        orch._crosswalk_ready = True
        leads_before = self.env["crm.lead"].with_context(active_test=False).search_count([])
        orch._upsert_lead(self.connection, self._lead(external_id, custom_fields={"Materials": "HDPE Drums"}))
        self.assertEqual(self.env["crm.lead"].with_context(active_test=False).search_count([]), leads_before)
        return orch

    def test_person_material_lands_on_its_facility_without_a_facility_profile(self):
        facility = self._facility("CRM45 Profileless Facility")
        person = self.env["res.partner"].create({"name": "CRM45 Profileless", "parent_id": facility.id})
        orch = self._approved_person_upsert(person, "crm45-profileless", "4502")
        profiles = self.env["plasticos.material.profile"].search([("partner_id", "=", facility.id)])
        self.assertEqual(profiles.mapped("polymer_id.code"), ["HDPE"])
        self.assertEqual(profiles.material_grade_id.code, "DRUMS")
        self.assertFalse(self.env["plasticos.facility.profile"].search([("partner_id", "=", facility.id)]))
        self.assertFalse(any("facility unresolved" in message for message in self._messages(orch)))

    def test_person_material_is_never_stored_on_the_person_when_the_site_is_ambiguous(self):
        # Operator 2026-11-17 (material placement ADR): a material profile never lands on a person.
        company = self.env["res.partner"].create({"name": "CRM45 Two Sites", "is_company": True})
        for site in ("North", "South"):
            self.env["res.partner"].create({"name": f"CRM45 {site}", "is_company": True, "parent_id": company.id})
        person = self.env["res.partner"].create({"name": "CRM45 Two Sites Buyer", "parent_id": company.id})
        orch = self._approved_person_upsert(person, "crm45-two-sites", "4503")
        self.assertFalse(self.env["plasticos.material.profile"].search([("partner_id", "=", person.id)]))
        self.assertFalse(self.env["plasticos.material.profile"].search([("partner_id", "=", company.id)]))
        self.assertTrue(any("facility unresolved" in message for message in self._messages(orch)))

    def test_person_material_lands_on_the_linked_site_matching_the_address(self):
        company = self.env["res.partner"].create({"name": "CRM45 Linked Sites", "is_company": True})
        north = self.env["res.partner"].create(
            {"name": "CRM45 Linked North", "is_company": True, "parent_id": company.id, "zip": "11111"}
        )
        south = self.env["res.partner"].create(
            {"name": "CRM45 Linked South", "is_company": True, "parent_id": company.id, "zip": "22222"}
        )
        person = self.env["res.partner"].create({"name": "CRM45 Linked Buyer", "parent_id": company.id})
        person.location_partner_ids = north | south
        self._erp_marker(person, "4504")
        orch = SyncOrchestrator(self.env)
        orch._crosswalk = {"crm45-linked": "4504"}
        orch._crosswalk_ready = True
        orch._upsert_lead(
            self.connection, self._lead("crm45-linked", custom_fields={"Materials": "HDPE Drums"}, zip="22222")
        )
        Profile = self.env["plasticos.material.profile"]
        self.assertEqual(Profile.search([("partner_id", "=", south.id)]).mapped("polymer_id.code"), ["HDPE"])
        self.assertFalse(Profile.search([("partner_id", "in", (person | north).ids)]))

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
        self.assertEqual(profiles.material_grade_id.code, "DRUMS")

        mixed = orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-two",
                custom_fields={"Materials": "HDPE Drums\nLDPE Film", "Type": "PE"},
            ),
        )
        codes = set(self._profiles(mixed).mapped("polymer_id.code"))
        self.assertEqual(codes, {"HDPE", "LDPE"})
        # Operator 2026-11-17: a record-level Type is the Material Type (a source type); "PE" is not one.
        self.assertTrue(any("Material Type unresolved: PE" in message for message in self._messages(orch)))
        bare = orch._upsert_lead(
            self.connection,
            self._lead("crm45-pe", custom_fields={"Materials": "PE"}),
        )
        pe_profile = self._profiles(bare)
        self.assertEqual(pe_profile.polymer_id.code, "HDPE")
        self.assertFalse(pe_profile.form_id)
        bottles = orch._upsert_lead(
            self.connection,
            self._lead("crm45-bottles", custom_fields={"Materials": "1-7"}),
        )
        bottle_profile = self._profiles(bottles)
        self.assertEqual(bottle_profile.polymer_id.code, "1_7_COMMINGLED_BOTTLES")
        self.assertEqual(bottle_profile.material_grade_id.code, "BOTTLES")
        self.assertEqual(bottle_profile.source_type_id.code, "POST_CONSUMER")

    def test_type_hint_from_another_section_is_not_applied(self):
        orch = SyncOrchestrator(self.env)
        crossed = orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-cross",
                custom_fields={
                    "Materials (MRF's)": "Gaylord Boxes",
                    "Type (LDPE)": "LDPE Film",
                },
            ),
        )
        profiles = self._profiles(crossed)
        self.assertEqual(profiles.mapped("polymer_id.code"), ["GAYLORD_BOXES"])
        self.assertFalse(profiles.form_id)
        self.assertFalse(profiles.filtered(lambda profile: profile.polymer_id.code == "LDPE"))

        same = orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-same-section",
                custom_fields={
                    "Materials (LDPE)": "Gaylord Boxes",
                    "Type (LDPE)": "LDPE Film",
                },
            ),
        )
        self.assertFalse(self._profiles(same))
        self.assertTrue(
            any(
                "conflicting material evidence" in row["message"] and row["record_ref"] == "crm45-same-section"
                for row in orch.error_rows
            )
        )

    def test_existing_buyer_tag_is_reused_and_a_second_name_is_rejected(self):
        adopted = self.env.ref("plasticos_crm_bridge.crm_tag_buyer")
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.env["crm.tag"].create({"name": "Buyer"})
        self.assertEqual(self.env["crm.tag"].search_count([("name", "=", "Buyer")]), 1)
        company = self.env["res.partner"].create({"name": "CRM45 Tag Maker", "is_company": True})
        supplier_rank, categories = company.supplier_rank, company.category_id.ids
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(
            self.connection,
            self._lead("crm45-tag-replay", company="CRM45 Tag Maker", custom_fields={"Buyer/Supplier": "Buyer"}),
        )
        self.assertEqual(lead.tag_ids.filtered(lambda tag: tag.name == "Buyer"), adopted)
        orch._upsert_lead(
            self.connection,
            self._lead("crm45-tag-replay", company="CRM45 Tag Maker", custom_fields={"Buyer/Supplier": "Buyer"}),
        )
        self.assertEqual(self.env["crm.tag"].search_count([("name", "=", "Buyer")]), 1)
        self.assertEqual(lead.tag_ids.filtered(lambda tag: tag.name == "Buyer"), adopted)
        # C1 C4: the Buyer raises the linked company's customer rank; nothing else on it changes.
        self.assertEqual(company.customer_rank, 1)
        self.assertEqual((company.supplier_rank, company.category_id.ids), (supplier_rank, categories))

    def _buyer_binding(self):
        return self.env["ir.model.data"].search(
            [("module", "=", "plasticos_crm_bridge"), ("name", "=", "crm_tag_buyer")]
        )

    def _import_buyer(self, external_id):
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(
            self.connection,
            self._lead(external_id, custom_fields={"Buyer/Supplier": "Buyer"}),
        )
        return orch, lead

    def test_corrupt_role_tag_binding_does_not_link_another_buyer(self):
        buyer = self.env.ref("plasticos_crm_bridge.crm_tag_buyer")
        supplier = self.env.ref("plasticos_crm_bridge.crm_tag_supplier")
        data = self._buyer_binding()
        stage_before = self.env.ref("crm.stage_lead1")
        partner = self.env["res.partner"].create({"name": "CRM45 Foreign Model", "is_company": True})
        categories = partner.category_id.ids

        data.write({"model": "res.partner", "res_id": buyer.id})
        self.env.registry.clear_cache()
        self.assertIsNone(role_tag_binding(self.env, "Buyer", "plasticos_crm_bridge.crm_tag_buyer"))
        orch, lead = self._import_buyer("crm45-wrong-model")
        self.assertNotIn(buyer, lead.tag_ids)
        self.assertFalse(lead.tag_ids.filtered(lambda row: row.id == buyer.id))
        self.assertIn("BLOCKED_DESTINATION: Buyer", self._messages(orch))
        self.assertEqual(lead.stage_id, stage_before)
        self.assertEqual(partner.category_id.ids, categories)
        self.assertEqual(self.env["crm.tag"].search_count([("name", "=", "Buyer")]), 1)
        self.assertEqual(data.model, "res.partner")

        data.write({"model": "crm.tag", "res_id": 0})
        self.env.registry.clear_cache()
        self.assertIsNone(role_tag_binding(self.env, "Buyer", "plasticos_crm_bridge.crm_tag_buyer"))
        orch, lead = self._import_buyer("crm45-stale-tag")
        self.assertNotIn(buyer, lead.tag_ids)
        self.assertIn("BLOCKED_DESTINATION: Buyer", self._messages(orch))

        gone = self.env["crm.tag"].create({"name": "CRM45 Gone Role"})
        gone_id = gone.id
        gone.unlink()
        data.write({"model": "crm.tag", "res_id": gone_id})
        self.env.registry.clear_cache()
        orch, lead = self._import_buyer("crm45-deleted-tag")
        self.assertNotIn(buyer, lead.tag_ids)
        self.assertFalse(lead.tag_ids)
        self.assertIn("BLOCKED_DESTINATION: Buyer", self._messages(orch))

        other = self.env["crm.tag"].create({"name": "CRM45 Other Role"})
        data.write({"model": "crm.tag", "res_id": other.id})
        self.env.registry.clear_cache()
        self.assertIsNone(role_tag_binding(self.env, "Buyer", "plasticos_crm_bridge.crm_tag_buyer"))
        orch, lead = self._import_buyer("crm45-wrong-name")
        self.assertNotIn(other, lead.tag_ids)
        self.assertNotIn(buyer, lead.tag_ids)
        self.assertNotIn(supplier, lead.tag_ids)
        self.assertIn("BLOCKED_DESTINATION: Buyer", self._messages(orch))

        data.write({"model": "res.partner", "res_id": partner.id})
        self.env.registry.clear_cache()
        orch, lead = self._import_buyer("crm45-foreign-live")
        self.assertNotIn(buyer, lead.tag_ids)
        self.assertFalse(any(row.id == partner.id for row in lead.tag_ids))
        self.assertIn("BLOCKED_DESTINATION: Buyer", self._messages(orch))
        self.assertEqual(self.env["crm.tag"].search_count([("name", "=", "Buyer")]), 1)

    def test_missing_role_tag_binding_uses_only_one_exact_tag(self):
        buyer = self.env.ref("plasticos_crm_bridge.crm_tag_buyer")
        data = self._buyer_binding()
        data.unlink()
        self.env.registry.clear_cache()
        self.assertIs(
            role_tag_binding(self.env, "Buyer", "plasticos_crm_bridge.crm_tag_buyer"),
            MISSING_ROLE_TAG_BINDING,
        )
        orch, lead = self._import_buyer("crm45-missing-xmlid")
        self.assertEqual(lead.tag_ids, buyer)
        orch._upsert_lead(
            self.connection,
            self._lead("crm45-missing-xmlid", custom_fields={"Buyer/Supplier": "Buyer"}),
        )
        self.assertEqual(lead.tag_ids, buyer)
        self.assertEqual(self.env["crm.tag"].search_count([("name", "=", "Buyer")]), 1)
        self.assertFalse(self._buyer_binding())

        buyer.write({"name": "CRM45 Retired Buyer"})
        orch, lead = self._import_buyer("crm45-no-tag")
        self.assertFalse(lead.tag_ids.filtered(lambda row: row.name == "Buyer"))
        self.assertEqual(self.env["crm.tag"].search_count([("name", "=", "Buyer")]), 0)
        self.assertIn("BLOCKED_DESTINATION: Buyer", self._messages(orch))

    def test_valid_supplier_binding_replays_without_a_second_tag(self):
        supplier = self.env.ref("plasticos_crm_bridge.crm_tag_supplier")
        self.assertEqual(role_tag_binding(self.env, "Supplier", "plasticos_crm_bridge.crm_tag_supplier"), supplier)
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(
            self.connection,
            self._lead("crm45-supplier", custom_fields={"Buyer/Supplier": "Supplier"}),
        )
        self.assertEqual(lead.tag_ids, supplier)
        orch._upsert_lead(
            self.connection,
            self._lead("crm45-supplier", custom_fields={"Buyer/Supplier": "Supplier"}),
        )
        self.assertEqual(lead.tag_ids, supplier)
        self.assertEqual(self.env["crm.tag"].search_count([("name", "=", "Supplier")]), 1)
        self.assertFalse(any("BLOCKED_DESTINATION" in message for message in self._messages(orch)))

    def test_failed_tag_write_keeps_the_admitted_lead(self):
        orch = SyncOrchestrator(self.env)
        real_write = type(self.env["crm.lead"]).write

        def fail_tags(records, vals):
            if "tag_ids" in vals:
                raise UserError("tag write failed")
            return real_write(records, vals)

        with patch.object(type(self.env["crm.lead"]), "write", fail_tags):
            lead = orch._upsert_lead(
                self.connection,
                self._lead("crm45-tag-fail", custom_fields={"Buyer/Supplier": "Buyer"}),
            )
        self.assertTrue(lead)
        self.assertEqual(orch.last_lead_outcome, "created")
        self.assertFalse(lead.tag_ids)
        self.assertTrue(any("classification failed" in message for message in self._messages(orch)))

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
        self.assertEqual(profile.color_ids.mapped("code"), ["BLUE"])
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
        self.assertEqual(profile.color_ids.mapped("code"), ["BLUE"])

    def test_comma_color_phrase_fills_the_color_set(self):
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-two-colors",
                custom_fields={
                    "Material (HDPE)": "HDPE Drums",
                    "Color (HDPE)": "Blue, Green",
                },
            ),
        )
        profile = self._profiles(lead)
        self.assertEqual(set(profile.color_ids.mapped("code")), {"BLUE", "GREEN"})
        self.assertFalse(orch._exact_color(["Blue, not-a-color"]))

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

        replay = orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-pps-generic",
                custom_fields={"Material (PPS)": "PP Supersacs", "Notes (PPS)": "PPS-PROFILE-ONLY"},
            ),
        )
        replay_notes = self._profiles(replay).freeform_notes or ""
        self.assertNotIn("PPS-PROFILE-ONLY", replay_notes)
        self.assertIn("BLOCKED_PPS_PROFILE_IDENTITY", self._messages(orch))

    def test_exact_pe_and_one_seven_survive_case_replay_and_unknown_does_not_guess(self):
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(self.connection, self._lead("crm45-pe-case", custom_fields={"Materials": "  PE  "}))
        profile = self._profiles(lead)
        self.assertEqual(profile.polymer_id.code, "HDPE")
        self.assertFalse(profile.form_id)
        self.assertFalse(profile.source_type_id)
        orch._upsert_lead(self.connection, self._lead("crm45-pe-case", custom_fields={"Materials": "PE"}))
        self.assertEqual(len(self._profiles(lead)), 1)

        bottles = orch._upsert_lead(
            self.connection, self._lead("crm45-17-case", custom_fields={"Materials": "  1-7  "})
        )
        bottle = self._profiles(bottles)
        self.assertEqual(bottle.polymer_id.code, "1_7_COMMINGLED_BOTTLES")
        self.assertEqual(bottle.material_grade_id.code, "BOTTLES")
        self.assertEqual(bottle.source_type_id.code, "POST_CONSUMER")
        attributes_before = self.env["plasticos.material.attribute"].search_count([])
        unknown = orch._upsert_lead(
            self.connection, self._lead("crm45-unknown", custom_fields={"Materials": "mystery fluff"})
        )
        self.assertFalse(self._profiles(unknown))
        self.assertEqual(self.env["plasticos.material.attribute"].search_count([]), attributes_before)
        self.assertTrue(any(row["category"] == REQUIRED_MAPPING for row in orch.error_rows))

        facility = self._facility("CRM45 PE Facility")
        self.env["plasticos.facility.profile"].create({"partner_id": facility.id})
        person = self.env["res.partner"].create({"name": "CRM45 PE Person", "parent_id": facility.id})
        self._erp_marker(person, "4517")
        person_orch = SyncOrchestrator(self.env)
        person_orch._crosswalk = {"crm45-pe-person": "4517"}
        person_orch._crosswalk_ready = True
        person_orch._upsert_lead(self.connection, self._lead("crm45-pe-person", custom_fields={"Materials": "PE"}))
        owned = self.env["plasticos.material.profile"].search([("partner_id", "=", facility.id)])
        self.assertEqual(owned.polymer_id.code, "HDPE")
        self.assertFalse(owned.form_id)

    def test_same_section_contradiction_is_not_stored_by_dropping_the_hint(self):
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-conflict",
                custom_fields={"Material (HDPE)": "HDPE Drums", "Type (HDPE)": "LDPE Film"},
            ),
        )
        self.assertFalse(self._profiles(lead))
        self.assertTrue(any("conflicting material evidence" in message for message in self._messages(orch)))
        self.assertTrue(any(row["category"] == REQUIRED_MAPPING for row in orch.error_rows))
        orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-conflict",
                custom_fields={"Material (HDPE)": "HDPE Drums", "Type (HDPE)": "LDPE Film"},
            ),
        )
        self.assertFalse(self._profiles(lead))

        supported = orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-unsupported-hint",
                custom_fields={"Material (HDPE)": "HDPE Drums", "Type (HDPE)": "not a resin"},
            ),
        )
        profile = self._profiles(supported)
        self.assertEqual(profile.polymer_id.code, "HDPE")
        self.assertEqual(profile.material_grade_id.code, "DRUMS")
        self.assertTrue(any("unsupported type hint" in message for message in self._messages(orch)))
        self.assertFalse(
            any(
                "conflicting material evidence" in row["message"] and row["record_ref"] == "crm45-unsupported-hint"
                for row in orch.error_rows
            )
        )

    def test_cross_section_unknown_resin_does_not_borrow_hdpe(self):
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(
            self.connection,
            self._lead(
                "crm45-cross-unknown",
                custom_fields={"Material (LDPE)": "unknown resin", "Type (HDPE)": "HDPE Drums"},
            ),
        )
        self.assertFalse(self._profiles(lead).filtered(lambda profile: profile.polymer_id.code == "HDPE"))

    def test_stored_source_conflict_is_kept_and_reported(self):
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(self.connection, self._lead("crm45-source", custom_fields={"Materials": "1-7"}))
        profile = self._profiles(lead)
        industrial = self.env["plasticos.source.type"].search([("code", "=", "POST_INDUSTRIAL")], limit=1)
        profile.source_type_id = industrial
        orch.error_rows.clear()
        orch._upsert_lead(self.connection, self._lead("crm45-source", custom_fields={"Materials": "1-7"}))
        self.assertEqual(profile.source_type_id, industrial)
        self.assertTrue(
            any(row["category"] == REQUIRED_MAPPING and "source unchanged" in row["message"] for row in orch.error_rows)
        )
        summary = build_run_summary(
            type(
                "Run",
                (),
                {
                    "contacts_seen": 1,
                    "calls_seen": 0,
                    "contacts_created": 1,
                    "contacts_updated": 0,
                    "contacts_unchanged": 0,
                    "contacts_duplicate_rejected": 0,
                    "contacts_failed": 0,
                    "calls_created": 0,
                    "calls_updated": 0,
                    "calls_unchanged": 0,
                    "calls_failed": 0,
                    "status": "success",
                    "orphans_buffered": 0,
                },
            )(),
            error_rows=orch.error_rows,
        )
        self.assertEqual(summary["final_status"], "partial")
        self.assertEqual(business_acceptance(summary), "FAIL")
        self.assertIn("category", summary["errors"][0])

    def test_unapproved_statuses_do_not_move_stage_or_send_mail(self):
        self.assertEqual(len(UNAPPROVED_LEAD_STATUSES), 8)
        orch = SyncOrchestrator(self.env)
        native_new = self.env.ref("crm.stage_lead1")
        new_stage = self.env.ref("plasticos_crm_bridge.stage_new")
        warm = self.env.ref("plasticos_crm_bridge.stage_qualified_warm")
        dead = self.env.ref("plasticos_crm_bridge.stage_dead_lead")
        won = self.env.ref("plasticos_crm_bridge.stage_active_supplier")
        queued = self.env["mail.mail"]
        before_fresh = queued.search([])
        fresh = orch._upsert_lead(self.connection, self._lead("crm45-default-new", lead_status_raw="New"))
        self.assertEqual(fresh.stage_id, native_new)
        fresh_mails = len(queued.search([]) - before_fresh)
        for index, raw in enumerate(UNAPPROVED_LEAD_STATUSES):
            before_created = queued.search([])
            created = orch._upsert_lead(self.connection, self._lead(f"crm45-new-{index}", lead_status_raw=raw))
            self.assertEqual(created.stage_id, new_stage)
            self.assertFalse(created.stage_id.is_won)
            self.assertNotEqual(created.stage_id, warm)
            self.assertNotEqual(created.stage_id, dead)
            self.assertIn(raw, created.description or "")
            created_mails = queued.search([]) - before_created
            self.assertEqual(len(created_mails), fresh_mails)
            self.assertFalse(any("blacklist" in (mail.subject or "").casefold() for mail in created_mails))

        existing = orch._upsert_lead(self.connection, self._lead("crm45-existing", lead_status_raw="2a=Qualified/HOT"))
        hot = existing.stage_id
        for raw in UNAPPROVED_LEAD_STATUSES:
            orch._upsert_lead(self.connection, self._lead("crm45-existing", lead_status_raw=raw))
            self.assertEqual(existing.stage_id, hot)
        existing.stage_id = won
        for raw in UNAPPROVED_LEAD_STATUSES:
            orch._upsert_lead(self.connection, self._lead("crm45-existing", lead_status_raw=raw))
            self.assertEqual(existing.stage_id, won)
        existing.write({"active": False})
        for raw in UNAPPROVED_LEAD_STATUSES:
            orch._upsert_lead(self.connection, self._lead("crm45-existing", lead_status_raw=raw))
            self.assertFalse(existing.active)
            self.assertEqual(existing.stage_id, won)

    def test_category_failure_rolls_back_the_tag_and_the_cursor_continues(self):
        company = self.env["res.partner"].create({"name": "CRM45 Rollback", "is_company": True})
        orch = SyncOrchestrator(self.env)
        lead = orch._upsert_lead(self.connection, self._lead("crm45-rollback", company="CRM45 Rollback"))
        lead.partner_id = company
        real_write = type(company).write

        def fail_category(records, vals):
            if records._name == "res.partner" and "category_id" in vals:
                raise IntegrityError("category constraint")
            return real_write(records, vals)

        with patch.object(type(company), "write", fail_category):
            orch._upsert_lead(
                self.connection,
                self._lead(
                    "crm45-rollback",
                    company="CRM45 Rollback",
                    custom_fields={"Buyer/Supplier": "Buyer", "Company Type": "Manufacturer"},
                ),
            )
        self.assertFalse(lead.tag_ids)
        self.assertNotIn(self.env.ref("plasticos_crm_bridge.categ_manufacturer"), company.category_id)
        self.assertEqual(orch.last_lead_outcome, "updated")
        self.assertTrue(
            any(
                row["category"] == REQUIRED_MAPPING and "classification failed" in row["message"]
                for row in orch.error_rows
            )
        )
        nxt = orch._upsert_lead(self.connection, self._lead("crm45-after-rollback"))
        self.assertTrue(nxt)
        self.assertEqual(orch.last_lead_outcome, "created")

    def test_person_material_constraint_failure_keeps_the_person(self):
        facility = self._facility("CRM45 Person Constraint")
        self.env["plasticos.facility.profile"].create({"partner_id": facility.id})
        person = self.env["res.partner"].create({"name": "CRM45 Constrained", "parent_id": facility.id})
        self._erp_marker(person, "4599")
        orch = SyncOrchestrator(self.env)
        orch._crosswalk = {"crm45-person-fail": "4599"}
        orch._crosswalk_ready = True
        before = self.env["plasticos.material.profile"].search_count([("partner_id", "=", facility.id)])
        real = type(self.env["plasticos.material.profile"]).reuse_lead_facility_material

        def fail_after(records, facility_profile, polymer, forms, note_line=None):
            real(records, facility_profile, polymer, forms, note_line=note_line)
            raise IntegrityError("person material constraint")

        with patch.object(type(self.env["plasticos.material.profile"]), "reuse_lead_facility_material", fail_after):
            orch._upsert_lead(
                self.connection,
                self._lead("crm45-person-fail", custom_fields={"Materials": "HDPE Drums"}),
            )
        self.assertEqual(
            self.env["plasticos.material.profile"].search_count([("partner_id", "=", facility.id)]), before
        )
        self.assertTrue(person.exists())
        self.assertTrue(any("material normalization failed" in message for message in self._messages(orch)))
        orch._upsert_lead(
            self.connection,
            self._lead("crm45-person-fail", custom_fields={"Materials": "HDPE Drums"}),
        )
        self.assertEqual(
            self.env["plasticos.material.profile"].search_count([("partner_id", "=", facility.id)]), before + 1
        )

    def test_company_types_land_on_registered_categories_only(self):
        self.assertEqual(len(COMPANY_TYPE_MAPPING), 12)
        orch = SyncOrchestrator(self.env)
        for label, xmlid in COMPANY_TYPE_MAPPING.items():
            company = self.env["res.partner"].create({"name": f"CRM45 {label}", "is_company": True})
            external = f"crm45-type-{label}"
            lead = orch._upsert_lead(self.connection, self._lead(external, company=company.name))
            lead.partner_id = company
            supplier_rank, role = company.supplier_rank, company.company_role
            orch._upsert_lead(
                self.connection,
                self._lead(
                    external, company=company.name, custom_fields={"Company Type": label, "Buyer/Supplier": "Buyer"}
                ),
            )
            self.assertIn(self.env.ref(xmlid), company.category_id)
            self.assertNotIn(self.env.ref("plasticos_crm_bridge.categ_buyer"), company.category_id)
            # C1 C4: the Buyer raises the customer rank; supplier rank and role are unchanged.
            self.assertEqual(company.customer_rank, 1)
            self.assertEqual((company.supplier_rank, company.company_role), (supplier_rank, role))
            orch._upsert_lead(
                self.connection,
                self._lead(external, company=company.name, custom_fields={"Company Type": label}),
            )
            self.assertEqual(
                company.category_id.filtered(lambda category, xmlid=xmlid: category == self.env.ref(xmlid)),
                self.env.ref(xmlid),
            )
        unknown = self.env["res.partner"].create({"name": "CRM45 Unknown Type", "is_company": True})
        lead = orch._upsert_lead(self.connection, self._lead("crm45-type-unknown", company=unknown.name))
        lead.partner_id = unknown
        before = unknown.category_id.ids
        orch._upsert_lead(
            self.connection,
            self._lead("crm45-type-unknown", company=unknown.name, custom_fields={"Company Type": "Not Registered"}),
        )
        self.assertEqual(unknown.category_id.ids, before)
        self.assertTrue(
            any("BLOCKED_COMPANY_TYPE_VALUE: Not Registered" in message for message in self._messages(orch))
        )
