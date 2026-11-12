"""A bale word is packaging Bales on the web-lead intake, never the retired Bales form.

Operator decision 2026-11-12 (coordinator ruling OP7-E09 option a): the Bales form
was retired on 2026-11-10 and bales are packaging. ``plasticos.intake`` requires a
form, so a bales intake keeps the OTHER fallback and gains packaging Bales, the
same packaging fact enrichment records. Real merge and intake paths; only the
economic assessment is fixed, as in the other web-lead material tests.
"""

from __future__ import annotations

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from .test_web_lead_material_grade import _ASSESSED, _WEB_LEAD, _payload


@tagged("post_install", "-at_install", "plasticos", "web_lead")
class TestWebLeadBalesPackaging(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WebLead = cls.env["plasticos.web.lead"]
        cls.config = cls.env["plasticos.web.lead.config"].sudo().get_config()
        cls.config.write(
            {
                "ai_enabled": False,
                "vision_enabled": False,
                "hot_intake_reviewer_id": cls.env.ref("base.user_admin").id,
            }
        )
        cls.form_other = cls.env.ref("plasticos_material_profile.form_other")
        cls.form_regrind = cls.env.ref("plasticos_material_profile.form_regrind")
        cls.form_bale = cls.env.ref("plasticos_material_profile.form_bale").with_context(active_test=False)
        cls.bales = cls.env.ref("plasticos_material_profile.packaging_bales")

    def _lead(self, external_id, description, weight="500 lbs"):
        with patch(f"{_WEB_LEAD}.evaluate_economic_opportunity", return_value=dict(_ASSESSED)):
            return self.WebLead.create_from_cognito(_payload(external_id, description, weight))

    def test_bale_words_merge_to_packaging_and_no_form(self):
        lead = self._lead("bales-merge", "HDPE scrap")
        for word in ("bale", "baled", "bales", " Bales "):
            merged = lead._merge_ai_and_vision({"form": word, "polymer": "HDPE"}, [])
            self.assertEqual(merged["packaging"], "bales", word)
            self.assertIsNone(merged["form"], word)
        regrind = lead._merge_ai_and_vision({"form": "regrind"}, [])
        self.assertEqual(regrind["form"], "REGRIND")
        self.assertIsNone(regrind["packaging"])
        seen = lead._merge_ai_and_vision({}, [{"observed_form": "bales", "confidence": 0.9}])
        self.assertNotEqual(seen["form"], "BALES")

    def test_bales_intake_gets_packaging_bales_and_the_other_form(self):
        lead = self._lead("bales-intake", "HDPE scrap")
        merged = lead._merge_ai_and_vision({"form": "bales", "polymer": "HDPE"}, [])
        merged["estimated_lbs"] = 40000
        intake = lead._create_intake(merged, self.config)
        self.assertEqual(intake.packaging_type_id, self.bales)
        self.assertEqual(intake.form_id, self.form_other)
        self.assertNotEqual(intake.form_id, self.form_bale)

    def test_stored_analysis_naming_the_bales_form_becomes_packaging(self):
        lead = self._lead("bales-stored", "HDPE scrap")
        intake = lead._create_intake({"form": "BALES", "polymer": "HDPE", "estimated_lbs": 500}, self.config)
        self.assertEqual(intake.packaging_type_id, self.bales)
        self.assertEqual(intake.form_id, self.form_other)

    def test_other_forms_keep_their_form_and_no_packaging(self):
        lead = self._lead("bales-regrind", "HDPE scrap")
        intake = lead._create_intake({"form": "REGRIND", "polymer": "HDPE", "estimated_lbs": 500}, self.config)
        self.assertEqual(intake.form_id, self.form_regrind)
        self.assertFalse(intake.packaging_type_id)
