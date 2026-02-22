from odoo import fields
from odoo.tests.common import TransactionCase


class TestInjection(TransactionCase):
    """Test the injection pipeline writes to material.profile."""

    def setUp(self):
        super().setUp()
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
                        "form": "bale",
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
                ("polymer_id.code", "=", "hdpe"),
            ]
        )
        self.assertTrue(profile)
        self.assertEqual(profile.form, "bales")
        self.assertEqual(profile.source_type, "post_industrial")
        self.assertEqual(profile.monthly_volume_lbs, 100000.0)
        self.assertTrue(profile.food_grade)
        self.assertEqual(run.state, "injected")
        self.assertEqual(run.profiles_created, 1)

    def test_merge_not_overwrite(self):
        """Injection does not overwrite existing field values."""
        # Get the polymer and form records
        pp_polymer = self.env["plasticos.polymer"].search([("code", "=", "pp")], limit=1)
        pellets_form = self.env["plasticos.material.form"].search([("code", "=", "pellets")], limit=1)
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
        run.action_inject()

        profile = self.env["plasticos.material.profile"].search(
            [
                ("partner_id", "=", self.partner.id),
                ("polymer_id.code", "=", "pp"),
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
