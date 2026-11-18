"""A bale word is packaging Bales on the web-lead intake, never the retired Bales form.

Operator decision 2026-11-12 (coordinator ruling OP7-E09 option a): the Bales form
was retired on 2026-11-10 and bales are packaging.

Staging #492 rebuilt the merge on the live material catalog (operator 2026-11-13: Staging
wins outside the Export lane). Packaging is its own catalog slot. It is filled from the
seller's text, the text AI's ``packaging_type`` and a photo's ``observed_packaging``,
and a bale word in any of them resolves to the Bales packaging type. A form the catalog
does not hold, the retired Bales form included, leaves the intake form empty.

These tests use the real merge and intake paths. Only the economic assessment is fixed,
as in the other web-lead material tests.
"""

from __future__ import annotations

from odoo.tests import TransactionCase, tagged

from .test_broker_one_pass import economic_assessment_patch
from .test_web_lead_material_grade import _ASSESSED, _payload


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
        cls.form_regrind = cls.env.ref("plasticos_material_profile.form_regrind")
        cls.form_bale = cls.env.ref("plasticos_material_profile.form_bale").with_context(active_test=False)
        cls.bales = cls.env.ref("plasticos_material_profile.packaging_bales")

    def _lead(self, external_id, description, weight="500 lbs"):
        with economic_assessment_patch(return_value=dict(_ASSESSED)):
            return self.WebLead.create_from_cognito(_payload(external_id, description, weight))

    def _intake(self, lead, merged):
        merged["estimated_lbs"] = 40000
        return lead._create_intake(merged, self.config)

    def test_bales_in_the_seller_text_are_packaging(self):
        lead = self._lead("bales-seller", "HDPE bales")
        merged = lead._merge_ai_and_vision({}, [])
        self.assertEqual(merged["packaging_type"], self.bales.code)
        self.assertNotEqual(merged["form"], self.form_bale.code)
        intake = self._intake(lead, merged)
        self.assertEqual(intake.packaging_type_id, self.bales)
        self.assertNotEqual(intake.form_id, self.form_bale)

    def test_bale_words_from_the_text_ai_are_packaging(self):
        lead = self._lead("bales-ai", "HDPE scrap")
        for word in ("bales", "Bales", " bale "):
            merged = lead._merge_ai_and_vision({"polymer": "HDPE", "packaging_type": word}, [])
            self.assertEqual(merged["packaging_type"], self.bales.code, word)

    def test_photo_of_bales_sets_packaging_on_the_intake(self):
        """Codex review on PR #482: bales seen only in a photo still record packaging Bales."""
        lead = self._lead("bales-vision", "HDPE scrap")
        merged = lead._merge_ai_and_vision({"polymer": "HDPE"}, [{"observed_packaging": "bales", "confidence": 0.9}])
        self.assertEqual(merged["packaging_type"], self.bales.code)
        intake = self._intake(lead, merged)
        self.assertEqual(intake.packaging_type_id, self.bales)

    def test_the_retired_bales_form_never_reaches_the_intake(self):
        lead = self._lead("bales-form", "HDPE scrap")
        merged = lead._merge_ai_and_vision({"form": "bales", "polymer": "HDPE"}, [])
        self.assertNotEqual(merged["form"], self.form_bale.code)
        intake = self._intake(lead, merged)
        self.assertNotEqual(intake.form_id, self.form_bale)

    def test_other_forms_keep_their_form_and_no_packaging(self):
        lead = self._lead("bales-regrind", "HDPE scrap")
        merged = lead._merge_ai_and_vision({"form": "regrind", "polymer": "HDPE"}, [])
        intake = self._intake(lead, merged)
        self.assertEqual(intake.form_id, self.form_regrind)
        self.assertFalse(intake.packaging_type_id)
