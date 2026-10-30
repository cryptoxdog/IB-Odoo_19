"""HOT web submissions become native Odoo opportunities; conversion never marks them Won.

Runs against the real ORM under ``odoo --test-enable``. AI/vision are disabled so
admission is deterministic; no external provider is called.
"""

import re

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

_HOSTILE = "<script>alert('x')</script> regrind"


def _payload(external_id, company="HOT Opportunity Co", weight="40000 lbs"):
    return {
        "Entry": {"Number": external_id},
        "YourBusinessCompanyName": company,
        "Name": {"FirstAndLast": "Alex Smith"},
        "Email": "alex@example.test",
        "Phone": "555-0100",
        "LocationOfPickUpCityState": "Dayton, OH",
        "DescribeYourMaterial": "HDPE pellets",
        "WhatIsTheSourceOfThisMaterial": "Manufacturing production scrap",
        "WhatIsTheQuantity": "2 loads per month",
        "WeightPerLoad": weight,
        "AreThereAnyContaminants": "none",
        "UploadPhotosOfYourScrapUpTo10": [],
    }


@tagged("post_install", "-at_install", "plasticos", "crm_bridge")
class TestWebLeadOpportunity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WebLead = cls.env["plasticos.web.lead"]
        cls.CrmLead = cls.env["crm.lead"]
        cls.Partner = cls.env["res.partner"]
        cls.Intake = cls.env["plasticos.intake"]
        cls.env["plasticos.web.lead.config"].sudo().get_config().write(
            {"ai_enabled": False, "vision_enabled": False, "hot_intake_reviewer_id": cls.env.ref("base.user_admin").id}
        )
        cls.stage_new = cls.env.ref("plasticos_crm_bridge.stage_new")
        cls.web_source = cls.env.ref("plasticos_crm_bridge.utm_source_web_lead")

    def _admit(self, external_id, **kwargs):
        return self.WebLead.create_from_cognito(_payload(external_id, **kwargs))

    def _opportunities_for(self, intake):
        return self.CrmLead.search([("type", "=", "opportunity"), ("source_intake_id", "=", intake.id)])

    def test_hot_admission_creates_one_new_opportunity_without_partner(self):
        partners_before = self.Partner.search_count([])
        lead = self._admit("OPP-HOT-001")
        self.assertEqual(lead.decision, "hot")
        self.assertTrue(lead.intake_id)

        opportunity = lead.crm_lead_id
        self.assertTrue(opportunity)
        self.assertEqual(opportunity.type, "opportunity")
        self.assertTrue(opportunity.active)
        self.assertEqual(opportunity.stage_id, self.stage_new)
        self.assertFalse(opportunity.stage_id.is_won)
        self.assertEqual(opportunity.source_intake_id, lead.intake_id)
        self.assertEqual(opportunity.source_id, self.web_source)
        self.assertEqual(self._opportunities_for(lead.intake_id), opportunity)

        self.assertEqual(opportunity.partner_name, "HOT Opportunity Co")
        self.assertEqual(opportunity.contact_name, "Alex Smith")
        self.assertEqual(opportunity.email_from, "alex@example.test")
        self.assertTrue(re.sub(r"\D", "", opportunity.phone or "").endswith("5550100"))
        self.assertIn("HDPE pellets", opportunity.description)
        self.assertIn("<b>Quantity (submitted):</b> 2 loads per month", opportunity.description)
        self.assertIn("<b>Weight per load (submitted):</b> 40000 lbs", opportunity.description)
        self.assertNotIn("<b>Quantity (submitted):</b> 40000 lbs", opportunity.description)
        self.assertIn("Dayton, OH", opportunity.description)

        self.assertFalse(opportunity.partner_id)
        self.assertFalse(opportunity.user_id)
        self.assertFalse(opportunity.expected_revenue)
        self.assertEqual(self.Partner.search_count([]), partners_before)
        self.assertEqual(lead.review_status, "clarification_required")
        self.assertIn(
            "Economic assessment is unavailable; broker review is required before commercial work.",
            lead.review_required_reason or "",
        )
        self.assertFalse(lead.review_snapshot_ids)

    def test_replay_is_idempotent_and_distinct_submission_is_separate(self):
        first = self._admit("OPP-IDEMP-001")
        replay = self._admit("OPP-IDEMP-001")
        self.assertEqual(replay, first)
        self.assertEqual(first._create_crm_lead(), first.crm_lead_id)
        self.assertEqual(len(self._opportunities_for(first.intake_id)), 1)
        self.assertEqual(self.Intake.search_count([("source_lead_id", "=", first.id)]), 1)

        second = self._admit("OPP-IDEMP-002")
        self.assertNotEqual(second, first)
        self.assertNotEqual(second.intake_id, first.intake_id)
        self.assertNotEqual(second.crm_lead_id, first.crm_lead_id)
        self.assertEqual(second.crm_lead_id.partner_name, first.crm_lead_id.partner_name)

    def test_cold_submission_creates_no_opportunity(self):
        opportunities_before = self.CrmLead.search_count([("type", "=", "opportunity")])
        cold = self._admit("OPP-COLD-001", weight="500 lbs")
        self.assertEqual(cold.decision, "cold")
        self.assertEqual(cold.state, "skipped")
        self.assertFalse(cold.intake_id)
        self.assertFalse(cold.crm_lead_id)
        self.assertFalse(cold.partner_id)
        self.assertEqual(cold.review_status, "pending")
        self.assertEqual(self.CrmLead.search_count([("type", "=", "opportunity")]), opportunities_before)

    def test_convert_to_intake_keeps_stage_and_reuses_source_intake(self):
        lead = self._admit("OPP-CONVERT-001")
        self.Partner.create({"name": "HOT Opportunity Co", "is_company": True})
        partners_before = self.Partner.search_count([])
        profiles_before = self.env["plasticos.material.profile"].search_count([])
        intake_fields = ["pending_company_name", "source_lead_id", "polymer_id", "form_id", "quantity_per_load_lbs"]
        intake_before = lead.intake_id.read(intake_fields)[0]
        lead_before = lead.read(["review_status", "state", "material_description"])[0]
        opportunity = lead.crm_lead_id
        opportunity_before = opportunity.read(["type", "stage_id", "expected_revenue", "description"])[0]
        for _ in range(2):
            action = opportunity.action_convert_to_intake()
        self.assertEqual(action["res_model"], "plasticos.intake")
        self.assertEqual(action["res_id"], lead.intake_id.id)
        self.assertEqual(opportunity.stage_id, self.stage_new)
        self.assertFalse(opportunity.stage_id.is_won)
        self.assertEqual(lead.intake_id.crm_lead_id, opportunity)
        self.assertFalse(opportunity.partner_id)
        self.assertFalse(lead.intake_id.partner_id)
        self.assertFalse(lead.intake_id.material_profile_id)
        self.assertFalse(opportunity.material_profile_id)
        self.assertEqual(self.Partner.search_count([]), partners_before)
        self.assertEqual(self.env["plasticos.material.profile"].search_count([]), profiles_before)
        self.assertEqual(lead.intake_id.read(intake_fields)[0], intake_before)
        self.assertEqual(lead.read(["review_status", "state", "material_description"])[0], lead_before)
        self.assertEqual(
            opportunity.read(["type", "stage_id", "expected_revenue", "description"])[0], opportunity_before
        )
        self.assertTrue(opportunity.message_ids.filtered(lambda m: "NOT_READY_FOR_MATCHING" in (m.body or "")))
        self.assertEqual(self.Intake.search_count([("source_lead_id", "=", lead.id)]), 1)

        manual = self.CrmLead.create(
            {
                "name": "Manual Co",
                "partner_name": "Manual Co",
                "description": "Manual material evidence",
                "type": "opportunity",
                "stage_id": self.stage_new.id,
            }
        )
        first = manual.action_convert_to_intake()
        self.assertEqual(manual.action_convert_to_intake()["res_id"], first["res_id"])
        self.assertEqual(manual.source_intake_id.id, first["res_id"])
        self.assertEqual(manual.source_intake_id.crm_lead_id, manual)
        self.assertEqual(manual.source_intake_id.pending_company_name, "Manual Co")
        self.assertFalse(manual.partner_id)
        self.assertFalse(manual.source_intake_id.partner_id)
        self.assertFalse(manual.source_intake_id.material_profile_id)
        self.assertEqual(manual.source_intake_id.intake_notes, manual.description)
        self.assertEqual(manual.source_intake_id.polymer_id.code.upper(), "OTHER")
        self.assertEqual(manual.source_intake_id.form_id.code.upper(), "OTHER")
        self.assertTrue(manual.message_ids.filtered(lambda m: "NOT_READY_FOR_MATCHING" in (m.body or "")))
        self.assertEqual(self.Partner.search_count([]), partners_before)
        self.assertEqual(self.env["plasticos.material.profile"].search_count([]), profiles_before)
        self.assertIn("Manual Co", first["name"])
        self.assertEqual(manual.stage_id, self.stage_new)
        self.assertEqual(manual.intake_count, 1)

    def test_explicit_source_partner_is_reused_without_overwriting_crm_partner(self):
        web = self._admit("OPP-SOURCE-PARTNER-001")
        source_partner = self.Partner.create({"name": "Verified Source", "is_company": True})
        crm_partner = self.Partner.create({"name": "Verified CRM", "is_company": True})
        web.intake_id.partner_id = source_partner
        partners_before = self.Partner.search_count([])
        partner_fields = ["name", "lead_source_id", "supplier_rank", "write_date"]
        source_before = source_partner.read(partner_fields)[0]
        crm_before = crm_partner.read(partner_fields)[0]
        opportunity = web.crm_lead_id
        opportunity.action_convert_to_intake()
        self.assertEqual(opportunity.partner_id, source_partner)
        opportunity.partner_id = crm_partner
        opportunity.action_convert_to_intake()
        self.assertEqual(opportunity.partner_id, crm_partner)
        self.assertEqual(web.intake_id.partner_id, source_partner)
        self.assertEqual(source_partner.read(partner_fields)[0], source_before)
        self.assertEqual(crm_partner.read(partner_fields)[0], crm_before)
        self.assertEqual(self.Partner.search_count([]), partners_before)

    def test_conversion_preserves_explicit_partner_profile_and_partner_data(self):
        web = self._admit("OPP-VERIFIED-001")
        partner = self.Partner.create({"name": "Verified Supplier", "is_company": True})
        profile = self.env["plasticos.material.profile"].create(
            {"partner_id": partner.id, "polymer_id": web.intake_id.polymer_id.id, "form_id": web.intake_id.form_id.id}
        )
        manual = self.CrmLead.create({"name": "Verified Manual", "type": "opportunity", "stage_id": self.stage_new.id})
        partner_before = partner.read(["name", "supplier_rank", "lead_source_id", "write_date"])[0]
        partners_before = self.Partner.search_count([])
        profiles_before = self.env["plasticos.material.profile"].search_count([])
        for opportunity in (web.crm_lead_id, manual):
            opportunity.write({"partner_id": partner.id, "material_profile_id": profile.id})
            first = opportunity.action_convert_to_intake()
            self.assertEqual(opportunity.action_convert_to_intake()["res_id"], first["res_id"])
            self.assertEqual(opportunity.partner_id, partner)
            self.assertEqual(opportunity.material_profile_id, profile)
            self.assertEqual(opportunity.source_intake_id.material_profile_id, profile)
            self.assertEqual(opportunity.source_intake_id.polymer_id, profile.polymer_id)
            self.assertEqual(opportunity.source_intake_id.form_id, profile.form_id)
            self.assertEqual(opportunity.intake_count, 1)
        self.assertFalse(web.intake_id.partner_id)
        self.assertEqual(web.intake_id.pending_company_name, "HOT Opportunity Co")
        self.assertEqual(partner.read(["name", "supplier_rank", "lead_source_id", "write_date"])[0], partner_before)
        self.assertEqual(self.Partner.search_count([]), partners_before)
        self.assertEqual(self.env["plasticos.material.profile"].search_count([]), profiles_before)

    def test_conversion_rejects_material_profile_owned_by_another_supplier(self):
        owner = self.Partner.create({"name": "Profile Owner", "is_company": True})
        supplier = self.Partner.create({"name": "Lead Supplier", "is_company": True})
        profile = self.env["plasticos.material.profile"].create(
            {
                "partner_id": owner.id,
                "polymer_id": self.env.ref("plasticos_material_profile.polymer_hdpe").id,
                "form_id": self.env.ref("plasticos_material_profile.form_pellets").id,
            }
        )
        lead = self.CrmLead.create(
            {
                "name": "Foreign Profile Lead",
                "type": "opportunity",
                "stage_id": self.stage_new.id,
                "partner_id": supplier.id,
                "material_profile_id": profile.id,
            }
        )
        intakes_before = self.Intake.search_count([])
        with self.assertRaises(ValidationError):
            lead.action_convert_to_intake()
        self.assertFalse(lead.source_intake_id)
        self.assertEqual(lead.partner_id, supplier)
        self.assertEqual(lead.material_profile_id, profile)
        self.assertEqual(self.Intake.search_count([]), intakes_before)

    def test_conversion_copies_material_profile_snapshot_without_source_intake(self):
        partner = self.Partner.create({"name": "Snapshot Supplier", "is_company": True})
        polymer = self.env.ref("plasticos_material_profile.polymer_hdpe")
        form = self.env.ref("plasticos_material_profile.form_pellets")
        color = self.env.ref("plasticos_material_profile.color_natural")
        source_type = self.env.ref("plasticos_material_profile.source_post_industrial")
        profile = self.env["plasticos.material.profile"].create(
            {
                "partner_id": partner.id,
                "polymer_id": polymer.id,
                "form_id": form.id,
                "color_id": color.id,
                "source_type_id": source_type.id,
                "melt_flow_index": 8.5,
                "contamination_percent": 2.5,
                "quantity_per_load_lbs": 12500,
            }
        )
        lead = self.CrmLead.create(
            {
                "name": "Snapshot Lead",
                "type": "opportunity",
                "stage_id": self.stage_new.id,
                "partner_id": partner.id,
                "material_profile_id": profile.id,
            }
        )
        self.assertFalse(lead.source_intake_id)
        lead.action_convert_to_intake()
        intake = lead.source_intake_id
        self.assertEqual(intake.partner_id, partner)
        self.assertEqual(intake.material_profile_id, profile)
        self.assertEqual(intake.polymer_id, polymer)
        self.assertEqual(intake.form_id, form)
        self.assertEqual(intake.color_id, color)
        self.assertEqual(intake.source_type_id, source_type)
        self.assertEqual(intake.mfi_value, 8.5)
        self.assertEqual(intake.contamination_pct, 2.5)
        self.assertEqual(intake.quantity_per_load_lbs, 12500)

    def test_incompatible_profile_keeps_intake_pending_without_copying_its_photos(self):
        web = self._admit("OPP-INCOMPATIBLE-001")
        web.intake_id.form_id = self.env.ref("plasticos_material_profile.form_pellets")
        partner = self.Partner.create({"name": "Verified Profile Supplier", "is_company": True})
        Attachment = self.env["ir.attachment"]
        Attachment.create(
            {
                "name": "intake-evidence.jpg",
                "type": "binary",
                "datas": "aW1hZ2U=",
                "mimetype": "image/jpeg",
                "res_model": "plasticos.intake",
                "res_id": web.intake_id.id,
            }
        )
        opportunity = web.crm_lead_id
        partners_before = self.Partner.search_count([])
        image_domain = [("mimetype", "like", "image/")]
        for form in (False, self.env.ref("plasticos_material_profile.form_other")):
            profile = self.env["plasticos.material.profile"].create(
                {
                    "partner_id": partner.id,
                    "polymer_id": web.intake_id.polymer_id.id,
                    "form_id": form.id if form else False,
                }
            )
            opportunity.write({"partner_id": partner.id, "material_profile_id": profile.id})
            for _ in range(2):
                opportunity.action_convert_to_intake()
            self.assertFalse(web.intake_id.material_profile_id)
            self.assertEqual(opportunity.material_profile_id, profile)
            self.assertEqual(opportunity.partner_id, partner)
            self.assertEqual(opportunity.stage_id, self.stage_new)
            self.assertEqual(opportunity.intake_count, 1)
            self.assertEqual(
                Attachment.search_count(
                    image_domain + [("res_model", "=", "crm.lead"), ("res_id", "=", opportunity.id)]
                ),
                1,
            )
            self.assertFalse(
                Attachment.search_count(
                    image_domain + [("res_model", "=", "plasticos.material.profile"), ("res_id", "=", profile.id)]
                )
            )
        self.assertEqual(self.Partner.search_count([]), partners_before)

    def test_linked_partner_is_kept_hostile_text_is_escaped_and_nothing_is_invented(self):
        partner = self.Partner.create({"name": "Linked Supplier", "is_company": True})
        other_source = self.env.ref("plasticos_crm_bridge.utm_source_other")
        lead = self.WebLead.create(
            {
                "lead_id": "OPP-PARTNER-001",
                "decision": "hot",
                "company_name": "Linked Supplier",
                "contact_name": "Pat",
                "material_description": _HOSTILE,
                "partner_id": partner.id,
                "lead_source_id": other_source.id,
            }
        )
        partners_before = self.Partner.search_count([])
        opportunity = lead._create_crm_lead()
        self.assertEqual(opportunity.type, "opportunity")
        self.assertEqual(opportunity.partner_id, partner)
        self.assertEqual(opportunity.source_id, other_source)
        self.assertEqual(self.Partner.search_count([]), partners_before)
        self.assertNotIn("<script>", opportunity.description)
        self.assertIn("regrind", opportunity.description)
        self.assertNotIn("(computed)", opportunity.description)
        self.assertFalse(opportunity.expected_revenue)
        self.assertFalse(opportunity.source_intake_id)
