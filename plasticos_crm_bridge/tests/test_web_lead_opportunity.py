"""HOT web submissions become native Odoo opportunities; conversion never marks them Won.

Runs against the real ORM under ``odoo --test-enable``. AI/vision are disabled so
admission is deterministic; no external provider is called.
"""

import re

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
        self.assertIn("40000 lbs", opportunity.description)
        self.assertIn("Dayton, OH", opportunity.description)

        self.assertFalse(opportunity.partner_id)
        self.assertFalse(opportunity.user_id)
        self.assertFalse(opportunity.expected_revenue)
        self.assertEqual(self.Partner.search_count([]), partners_before)
        self.assertEqual(lead.review_status, "pending")
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
        opportunity = lead.crm_lead_id
        action = opportunity.action_convert_to_intake()
        self.assertEqual(action["res_model"], "plasticos.intake")
        self.assertEqual(action["res_id"], lead.intake_id.id)
        self.assertEqual(opportunity.stage_id, self.stage_new)
        self.assertFalse(opportunity.stage_id.is_won)
        self.assertEqual(lead.intake_id.crm_lead_id, opportunity)
        self.assertTrue(opportunity.partner_id)
        self.assertEqual(self.Intake.search_count([("source_lead_id", "=", lead.id)]), 1)

        manual = self.CrmLead.create({"name": "Manual Co", "partner_name": "Manual Co", "stage_id": self.stage_new.id})
        manual.action_convert_to_intake()
        self.assertEqual(manual.stage_id, self.stage_new)
        self.assertEqual(manual.intake_count, 1)

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
