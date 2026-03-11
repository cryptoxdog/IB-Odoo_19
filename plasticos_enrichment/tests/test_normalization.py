from odoo.addons.plasticos_base.test_common import PlasticosTestCase


class TestNormalization(PlasticosTestCase):
    """Test the deterministic normalization maps."""

    def setUp(self):
        super().setUp()
        self.svc = self.env["plasticos.enrichment.service"]

    def test_polymer_normalize_hdpe(self):
        raw = {"polymer": "HDPE", "confidence": 0.95, "inference_type": "explicit", "source_sentence": "test"}
        vals, prov, unmapped = self.svc.normalize_material(raw)
        self.assertEqual(vals["polymer"], "HDPE")
        self.assertFalse(unmapped)

    def test_polymer_normalize_lowercase(self):
        raw = {"polymer": "polypropylene", "confidence": 0.9, "inference_type": "explicit", "source_sentence": "test"}
        vals, prov, unmapped = self.svc.normalize_material(raw)
        self.assertEqual(vals["polymer"], "PP")

    def test_form_normalize(self):
        raw = {
            "polymer": "HDPE",
            "form": "pellets",
            "confidence": 0.9,
            "inference_type": "explicit",
            "source_sentence": "test",
        }
        vals, prov, unmapped = self.svc.normalize_material(raw)
        self.assertEqual(vals["form"], "PELL")

    def test_source_type_normalize(self):
        raw = {
            "polymer": "PP",
            "source_type": "post-industrial",
            "confidence": 0.85,
            "inference_type": "explicit",
            "source_sentence": "test",
        }
        vals, prov, unmapped = self.svc.normalize_material(raw)
        self.assertEqual(vals["source_type"], "PI")

    def test_boolean_fields(self):
        raw = {
            "polymer": "PET",
            "previously_washed": True,
            "food_grade": True,
            "confidence": 0.9,
            "inference_type": "explicit",
            "source_sentence": "test",
        }
        vals, prov, unmapped = self.svc.normalize_material(raw)
        self.assertTrue(vals["previously_washed"])
        self.assertTrue(vals["food_grade"])

    def test_float_fields(self):
        raw = {
            "polymer": "HDPE",
            "melt_flow_index": 5.2,
            "density": 0.954,
            "monthly_volume_lbs": 200000,
            "confidence": 0.88,
            "inference_type": "explicit",
            "source_sentence": "test",
        }
        vals, prov, unmapped = self.svc.normalize_material(raw)
        self.assertAlmostEqual(vals["melt_flow_index"], 5.2)
        self.assertAlmostEqual(vals["density"], 0.954)
        self.assertEqual(vals["monthly_volume_lbs"], 200000.0)

    def test_unmapped_form(self):
        raw = {
            "polymer": "HDPE",
            "form": "unknown_form",
            "confidence": 0.9,
            "inference_type": "explicit",
            "source_sentence": "test",
        }
        vals, prov, unmapped = self.svc.normalize_material(raw)
        self.assertNotIn("form", vals)
        self.assertTrue(any(u[0] == "form" for u in unmapped))

    def test_provenance_generated(self):
        raw = {
            "polymer": "LDPE",
            "form": "bales",
            "contains_metal": False,
            "confidence": 0.92,
            "inference_type": "explicit",
            "source_sentence": "We process LDPE bales.",
        }
        vals, prov, unmapped = self.svc.normalize_material(raw)
        fields_in_prov = [p["target_field"] for p in prov]
        self.assertIn("polymer", fields_in_prov)
        self.assertIn("form", fields_in_prov)
