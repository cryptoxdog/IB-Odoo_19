"""Web-lead merge puts one material code on the form or the material grade, and the intake keeps both."""

from __future__ import annotations

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

_WEB_LEAD = "odoo.addons.plasticos_web_leads.models.web_lead"
_ASSESSED = {"status": "assessed", "assessment": {"recommendation": "broker_review", "clarifications": []}}


def _payload(external_id, description, weight):
    return {
        "Entry": {"Number": external_id},
        "YourBusinessCompanyName": "Grade Co",
        "DescribeYourMaterial": description,
        "WhatIsTheSourceOfThisMaterial": "Manufacturing production scrap",
        "WhatIsTheQuantity": "2 loads per month",
        "WeightPerLoad": weight,
        "AreThereAnyContaminants": "none",
        "UploadPhotosOfYourScrapUpTo10": [],
    }


@tagged("post_install", "-at_install", "plasticos", "web_lead")
class TestWebLeadMaterialGrade(TransactionCase):
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
        cls.grade_pallets = cls.env.ref("plasticos_material_profile.material_grade_pallets")

    def _lead(self, external_id, description, weight):
        with patch(f"{_WEB_LEAD}.evaluate_economic_opportunity", return_value=dict(_ASSESSED)):
            return self.WebLead.create_from_cognito(_payload(external_id, description, weight))

    def test_pallet_lead_creates_an_intake_with_the_pallets_grade(self):
        lead = self._lead("grade-pallets", "HDPE plastic pallets", "40000 lbs")

        self.assertEqual(lead.decision, "hot")
        self.assertEqual(lead.ai_analysis["material_grade"], "PALLETS")
        self.assertFalse(lead.ai_analysis["form"])
        self.assertEqual(lead.intake_id.form_id, self.form_other)
        self.assertEqual(lead.intake_id.material_grade_id, self.grade_pallets)

    def test_stored_analysis_without_a_grade_key_is_split_when_forced(self):
        lead = self._lead("grade-forced", "HDPE scrap", "500 lbs")

        intake = lead._create_intake({"form": "PALLETS", "polymer": "HDPE", "estimated_lbs": 500}, self.config)

        self.assertEqual(intake.form_id, self.form_other)
        self.assertEqual(intake.material_grade_id, self.grade_pallets)

    def test_film_maps_to_the_film_form(self):
        lead = self._lead("grade-film", "LDPE scrap", "500 lbs")

        merged = lead._merge_ai_and_vision({"form": "film"}, [])

        self.assertEqual(merged["form"], "FILM")
        self.assertIsNone(merged["material_grade"])

    def test_drums_keep_the_vision_regrind_form(self):
        lead = self._lead("grade-drums", "HDPE drums", "500 lbs")

        merged = lead._merge_ai_and_vision({}, [{"observed_form": "regrind", "confidence": 0.9}])

        self.assertEqual(merged["material_grade"], "DRUMS")
        self.assertEqual(merged["form"], "REGRIND")
        intake = lead._create_intake(merged, self.config)
        self.assertEqual(intake.form_id.code, "REGRIND")
        self.assertNotEqual(intake.form_id, self.form_other)
        self.assertEqual(intake.material_grade_id.code, "DRUMS")

    def test_film_and_buckets_stay_on_separate_slots(self):
        lead = self._lead("grade-both", "buckets", "500 lbs")

        merged = lead._merge_ai_and_vision({"form": "film"}, [])

        self.assertEqual(merged["form"], "FILM")
        self.assertEqual(merged["material_grade"], "BUCKETS")

    def test_item_words_from_the_ai_are_grades(self):
        lead = self._lead("grade-items", "scrap", "500 lbs")

        pallet = lead._merge_ai_and_vision({"form": "pallet"}, [])
        drum = lead._merge_ai_and_vision({"form": "drum"}, [])
        bucket = lead._merge_ai_and_vision({"form": "bucket"}, [])

        self.assertEqual(pallet["material_grade"], "PALLETS")
        self.assertFalse(pallet["form"])
        self.assertEqual(drum["material_grade"], "DRUMS")
        self.assertFalse(drum["form"])
        self.assertEqual(bucket["material_grade"], "BUCKETS")
        self.assertFalse(bucket["form"])
