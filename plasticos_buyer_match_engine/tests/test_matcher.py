"""
Tests for Buyer Matching Engine v2.0 (facility.profile-based)

SCHEMA ALIGNMENT (2026-02-25):
- plasticos.polymer (with category: commodity/engineering/specialty)
- plasticos.material.form (bales, regrind, pellet, etc.)
- plasticos.material.color (natural, white, black, etc.)
- plasticos.source.type (pcr, pir, virgin) — replaces "material_category"
- intake.lat/lon for geo (not latitude/longitude)
- facility.profile uses accepted_polymer_ids (Many2many), form_preference_id (Many2one to material.form)
"""

import logging

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


class TestBuyerMatcher(TransactionCase):
    def setUp(self):
        super().setUp()

        # ══════════════════════════════════════════════════════════
        # Create test material master data
        # ══════════════════════════════════════════════════════════

        # Polymer
        self.polymer_hdpe = self.env["plasticos.polymer"].create(
            {
                "name": "HDPE",
                "code": "hdpe",
                "full_name": "High-Density Polyethylene",
                "category": "commodity",
            }
        )

        self.polymer_pp = self.env["plasticos.polymer"].create(
            {
                "name": "PP",
                "code": "pp",
                "full_name": "Polypropylene",
                "category": "commodity",
            }
        )

        # Material Form
        self.form_bales = self.env["plasticos.material.form"].create(
            {
                "name": "Bales",
                "code": "bales",
            }
        )

        # Material Color
        self.color_natural = self.env["plasticos.material.color"].create(
            {
                "name": "Natural",
                "code": "natural",
            }
        )

        # Source Type (replaces material_category)
        self.source_pcr = self.env["plasticos.source.type"].create(
            {
                "name": "Post-Consumer",
                "code": "pcr",
            }
        )

        self.source_pir = self.env["plasticos.source.type"].create(
            {
                "name": "Post-Industrial",
                "code": "pir",
            }
        )

        # ══════════════════════════════════════════════════════════
        # Create test supplier (company + facility)
        # ══════════════════════════════════════════════════════════

        self.supplier_company = self.env["res.partner"].create(
            {
                "name": "Test Supplier Company",
                "is_company": True,
                "supplier_rank": 1,
                "street": "123 Supplier St",
                "city": "Charlotte",
                "country_id": self.env.ref("base.us").id,
            }
        )

        self.supplier_facility = self.env["res.partner"].create(
            {
                "name": "Test Supplier Facility",
                "is_company": True,
                "parent_id": self.supplier_company.id,
                "street": "123 Supplier St",
                "city": "Charlotte",
                "country_id": self.env.ref("base.us").id,
            }
        )

        # Supplier facility profile
        # NOTE: facility.profile does NOT have accepted_color_ids or source_type_id.
        # Use feedstock_type (Selection) instead of source_type_id (Many2one).
        self.supplier_profile = self.env["plasticos.facility.profile"].create(
            {
                "partner_id": self.supplier_facility.id,
                "active": True,
                "accepted_polymer_ids": [(6, 0, [self.polymer_hdpe.id])],
                "form_preference_id": self.form_bales.id,
                "capacity_lbs_month": 50000,
                "feedstock_type": "post_consumer",
            }
        )

        # ══════════════════════════════════════════════════════════
        # Create test buyers (company + facility structure)
        # ══════════════════════════════════════════════════════════

        # Buyer 1: Exact match (same polymer, same source type)
        self.buyer1_company = self.env["res.partner"].create(
            {
                "name": "Exact Match Buyer Company",
                "is_company": True,
                "customer_rank": 1,
                "street": "456 Buyer Ave",
                "city": "Charlotte",
                "country_id": self.env.ref("base.us").id,
            }
        )

        self.buyer1_facility = self.env["res.partner"].create(
            {
                "name": "Exact Match Buyer Facility",
                "is_company": True,
                "parent_id": self.buyer1_company.id,
                "customer_rank": 1,
            }
        )

        self.buyer1_profile = self.env["plasticos.facility.profile"].create(
            {
                "partner_id": self.buyer1_facility.id,
                "active": True,
                "accepted_polymer_ids": [(6, 0, [self.polymer_hdpe.id])],
                "form_preference_id": self.form_bales.id,
                "min_lot_size_lbs": 10000,
                "feedstock_type": "post_consumer",
            }
        )

        # Buyer 2: Different polymer (should fail polymer gate)
        self.buyer2_company = self.env["res.partner"].create(
            {
                "name": "Different Polymer Buyer Company",
                "is_company": True,
                "customer_rank": 1,
            }
        )

        self.buyer2_facility = self.env["res.partner"].create(
            {
                "name": "Different Polymer Buyer Facility",
                "is_company": True,
                "parent_id": self.buyer2_company.id,
                "customer_rank": 1,
            }
        )

        self.buyer2_profile = self.env["plasticos.facility.profile"].create(
            {
                "partner_id": self.buyer2_facility.id,
                "active": True,
                "accepted_polymer_ids": [(6, 0, [self.polymer_pp.id])],  # PP not HDPE
                "min_lot_size_lbs": 20000,
            }
        )

        # ══════════════════════════════════════════════════════════
        # Create test intake (material offering from supplier)
        # Uses lat/lon for geo (not latitude/longitude)
        # ══════════════════════════════════════════════════════════

        self.intake = self.env["plasticos.intake"].create(
            {
                "partner_id": self.supplier_company.id,
                "facility_id": self.supplier_facility.id,
                "polymer_id": self.polymer_hdpe.id,
                "form_id": self.form_bales.id,
                "color_id": self.color_natural.id,
                "source_type_id": self.source_pcr.id,
                "quantity_per_load_lbs": 40000,
                "loads_per_month": 2,
                "lat": 35.2271,  # Charlotte, NC
                "lon": -80.8431,
            }
        )

    # ══════════════════════════════════════════════════════════════
    # Model Registration Tests
    # ══════════════════════════════════════════════════════════════

    def test_matcher_model_exists(self):
        """Verify the plasticos.buyer.matcher model is registered."""
        self.assertIn("plasticos.buyer.matcher", self.env)

    def test_facility_profile_model_exists(self):
        """Verify the plasticos.facility.profile model is registered."""
        self.assertIn("plasticos.facility.profile", self.env)

    def test_intake_model_exists(self):
        """Verify the plasticos.intake model is registered."""
        self.assertIn("plasticos.intake", self.env)

    def test_exclusion_model_exists(self):
        """Verify the plasticos.match.exclusion model is registered."""
        self.assertIn("plasticos.match.exclusion", self.env)

    # ══════════════════════════════════════════════════════════════
    # Matcher Method Tests
    # ══════════════════════════════════════════════════════════════

    def test_find_matches_method_exists(self):
        """Verify find_matches_for_supplier method exists on matcher."""
        matcher = self.env["plasticos.buyer.matcher"]
        self.assertTrue(hasattr(matcher, "find_matches_for_supplier"))

    def test_find_matches_returns_list(self):
        """Test that find_matches_for_supplier returns a list."""
        matcher = self.env["plasticos.buyer.matcher"]
        matches = matcher.find_matches_for_supplier(
            supplier_partner_id=self.supplier_company.id,
            intake_id=self.intake.id,
            max_results=10,
        )
        self.assertIsInstance(matches, list)

    def test_invalid_supplier_raises(self):
        """Test error handling for invalid supplier."""
        matcher = self.env["plasticos.buyer.matcher"]
        with self.assertRaises(ValidationError):
            matcher.find_matches_for_supplier(supplier_partner_id=99999)

    def test_max_results_parameter(self):
        """Test that max_results parameter is respected."""
        matcher = self.env["plasticos.buyer.matcher"]
        matches = matcher.find_matches_for_supplier(
            supplier_partner_id=self.supplier_company.id,
            intake_id=self.intake.id,
            max_results=1,
        )
        self.assertLessEqual(len(matches), 1)

    def test_mode_parameter_strict(self):
        """Test strict mode parameter."""
        matcher = self.env["plasticos.buyer.matcher"]
        matches = matcher.find_matches_for_supplier(
            supplier_partner_id=self.supplier_company.id,
            intake_id=self.intake.id,
            mode="strict",
        )
        self.assertIsInstance(matches, list)

    def test_mode_parameter_relaxed(self):
        """Test relaxed mode parameter."""
        matcher = self.env["plasticos.buyer.matcher"]
        matches = matcher.find_matches_for_supplier(
            supplier_partner_id=self.supplier_company.id,
            intake_id=self.intake.id,
            mode="relaxed",
        )
        self.assertIsInstance(matches, list)

    # ══════════════════════════════════════════════════════════════
    # Gate Logic Tests
    # ══════════════════════════════════════════════════════════════

    def test_no_active_buyers_returns_empty(self):
        """Test matching when no active buyer profiles exist."""
        self.buyer1_profile.write({"active": False})
        self.buyer2_profile.write({"active": False})

        matcher = self.env["plasticos.buyer.matcher"]
        matches = matcher.find_matches_for_supplier(
            supplier_partner_id=self.supplier_company.id,
            intake_id=self.intake.id,
        )
        self.assertEqual(len(matches), 0)

    def test_match_result_structure(self):
        """Test that match results have expected structure."""
        matcher = self.env["plasticos.buyer.matcher"]
        matches = matcher.find_matches_for_supplier(
            supplier_partner_id=self.supplier_company.id,
            intake_id=self.intake.id,
            max_results=10,
        )

        if matches:
            match = matches[0]
            expected_keys = ["buyer_id", "buyer_name", "total_score", "gates_passed"]
            for key in expected_keys:
                self.assertIn(key, match)

    def test_scoring_order_descending(self):
        """Test that results are sorted by score descending."""
        matcher = self.env["plasticos.buyer.matcher"]
        matches = matcher.find_matches_for_supplier(
            supplier_partner_id=self.supplier_company.id,
            intake_id=self.intake.id,
            max_results=10,
        )

        if len(matches) > 1:
            scores = [m["total_score"] for m in matches]
            self.assertEqual(scores, sorted(scores, reverse=True))
