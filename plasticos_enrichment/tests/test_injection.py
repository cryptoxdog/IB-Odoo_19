from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase


class TestInjection(PlasticosTestCase):
    """Test the injection pipeline writes to material.profile."""

    def setUp(self):
        super().setUp()
        # Ensure canonical forms exist (in case data load order differs in full suite)
        Form = self.env["plasticos.material.form"]
        for code, name in (("BALES", "Bales"), ("OTHER", "Other")):
            if not Form.search([("code", "=", code)], limit=1):
                Form.create({"name": name, "code": code, "description": f"Test {name} form."})
        # Create a parent company (required for facility-level partners)
        self.company = self.env["res.partner"].create(
            {
                "name": "Test Buyer Inc",
                "is_company": True,
            }
        )
        # Create facility-level partner (has parent_id, required for material profiles)
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Buyer Facility",
                "parent_id": self.company.id,
            }
        )
        self.source = self.env["plasticos.enrichment.source"].create(
            {
                "partner_id": self.partner.id,
                "url": "https://example.com/about",
                "source_type": "website",
            }
        )

    def test_create_new_profile(self):
        """Injection creates a new material.profile when none
        exists for the polymer."""
        run = self.env["plasticos.enrichment.run"].create(
            {
                "partner_id": self.partner.id,
                "source_ids": [(6, 0, [self.source.id])],
            }
        )
        self.env["plasticos.enrichment.extraction"].create(
            {
                "run_id": run.id,
                "source_id": self.source.id,
                "material_json": [
                    {
                        "polymer": "hdpe",
                        "form": "bales",
                        "source_type": "post-industrial",
                        "monthly_volume_lbs": 100000,
                        "food_grade": True,
                        "confidence": 0.92,
                        "inference_type": "explicit",
                        "source_sentence": "We buy HDPE bales.",
                    }
                ],
                "confidence": 0.92,
                "governance_passed": True,
                "governance_flags": [],
                "extracted_at": fields.Datetime.now(),
            }
        )
        run.write({"state": "validated"})
        run.action_inject()

        profile = self.env["plasticos.material.profile"].search(
            [
                ("partner_id", "=", self.partner.id),
                ("polymer_id.code", "=", "HDPE"),
            ]
        )
        self.assertTrue(profile)
        self.assertEqual(profile.form, "BALES")
        self.assertEqual(profile.source_type, "POST_INDUSTRIAL")
        self.assertEqual(profile.monthly_volume_lbs, 100000.0)
        self.assertTrue(profile.food_grade)
        self.assertEqual(run.state, "injected")
        self.assertEqual(run.profiles_created, 1)

    def test_merge_not_overwrite(self):
        """Injection does not overwrite existing field values."""
        # Get the polymer and form records (ensure they exist from seed data)
        # Note: _resolve_polymer_id converts to uppercase, so use "PP" not "pp"
        pp_polymer = self.env["plasticos.polymer"].search([("code", "=", "PP")], limit=1)
        if not pp_polymer:
            pp_polymer = self.env["plasticos.polymer"].create(
                {"name": "PP", "code": "PP", "description": "Polypropylene"}
            )
        pellets_form = self.env["plasticos.material.form"].search([("code", "=", "PELLETS")], limit=1)
        if not pellets_form:
            pellets_form = self.env["plasticos.material.form"].create(
                {"name": "Pellets", "code": "PELLETS", "description": "Test pellets form"}
            )
        self.env["plasticos.material.profile"].create(
            {
                "partner_id": self.partner.id,
                "polymer_id": pp_polymer.id,
                "form_id": pellets_form.id,
                "monthly_volume_lbs": 50000,
            }
        )

        run = self.env["plasticos.enrichment.run"].create(
            {
                "partner_id": self.partner.id,
                "source_ids": [(6, 0, [self.source.id])],
            }
        )
        self.env["plasticos.enrichment.extraction"].create(
            {
                "run_id": run.id,
                "source_id": self.source.id,
                "material_json": [
                    {
                        "polymer": "pp",
                        "form": "pellet",
                        "monthly_volume_lbs": 999999,
                        "melt_flow_index": 12.0,
                        "confidence": 0.90,
                        "inference_type": "explicit",
                        "source_sentence": "PP pellets.",
                    }
                ],
                "confidence": 0.90,
                "governance_passed": True,
                "governance_flags": [],
                "extracted_at": fields.Datetime.now(),
            }
        )
        run.write({"state": "validated"})
        # Mock message_post to avoid mail alias domain issues in test environment
        with patch.object(type(self.env["plasticos.material.profile"]), "message_post", return_value=True):
            run.action_inject()

        profile = self.env["plasticos.material.profile"].search(
            [
                ("partner_id", "=", self.partner.id),
                ("polymer_id.code", "=", "PP"),
            ]
        )
        # Existing values NOT overwritten
        self.assertEqual(profile.monthly_volume_lbs, 50000)
        # Empty field WAS populated
        self.assertAlmostEqual(profile.melt_flow_index, 12.0)

        prov_skip = self.env["plasticos.enrichment.provenance"].search(
            [
                ("run_id", "=", run.id),
                ("target_field", "=", "monthly_volume_lbs"),
                ("status", "=", "skipped_immutable"),
            ]
        )
        self.assertTrue(prov_skip)
