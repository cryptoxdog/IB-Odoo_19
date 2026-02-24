"""
Tests for Buyer Matching Engine v2.0 (facility.profile-based)
"""

import logging

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


class TestBuyerMatcher(TransactionCase):
    def setUp(self):
        super().setUp()

        # Create test material master data
        self.mat_category = self.env["plasticos.material.category"].create({"name": "Post-Consumer", "code": "PC"})

        self.polymer_family = self.env["plasticos.polymer.family"].create({"name": "HDPE", "code": "HDPE"})

        self.form_factor = self.env["plasticos.form.factor"].create({"name": "Bales", "code": "BALE"})

        self.color_family = self.env["plasticos.color.family"].create({"name": "Natural", "code": "NAT"})

        self.quality_level = self.env["plasticos.quality.level"].create({"name": "Grade A", "code": "A"})

        # Create test supplier
        self.supplier = self.env["res.partner"].create(
            {
                "name": "Test Supplier",
                "supplier_rank": 1,
                "street": "123 Supplier St",
                "city": "Charlotte",
                "country_id": self.env.ref("base.us").id,
            }
        )

        # Create supplier profile
        self.supplier_profile = self.env["plasticos.facility.profile"].create(
            {
                "name": "Test Supplier Profile",
                "partner_id": self.supplier.id,
                "active": True,
                "material_category_id": self.mat_category.id,
                "polymer_family_id": self.polymer_family.id,
                "form_factor_ids": [(6, 0, [self.form_factor.id])],
                "color_family_ids": [(6, 0, [self.color_family.id])],
                "monthly_capacity": 50000.0,
                "quality_level_id": self.quality_level.id,
                "latitude": 35.2271,
                "longitude": -80.8431,
            }
        )

        # Create test buyers
        self.buyer1 = self.env["res.partner"].create(
            {
                "name": "Exact Match Buyer",
                "customer_rank": 1,
                "street": "456 Buyer Ave",
                "city": "Charlotte",
                "country_id": self.env.ref("base.us").id,
            }
        )

        self.buyer1_profile = self.env["plasticos.facility.profile"].create(
            {
                "name": "Exact Match Buyer Profile",
                "partner_id": self.buyer1.id,
                "active": True,
                "material_category_id": self.mat_category.id,
                "polymer_family_id": self.polymer_family.id,
                "form_factor_ids": [(6, 0, [self.form_factor.id])],
                "color_family_ids": [(6, 0, [self.color_family.id])],
                "min_order_quantity": 10000.0,
                "quality_level_id": self.quality_level.id,
                "latitude": 35.2271,
                "longitude": -80.8431,
            }
        )

        self.buyer2 = self.env["res.partner"].create(
            {
                "name": "Partial Match Buyer",
                "customer_rank": 1,
                "street": "789 Commerce Blvd",
                "city": "Atlanta",
                "country_id": self.env.ref("base.us").id,
            }
        )

        self.buyer2_profile = self.env["plasticos.facility.profile"].create(
            {
                "name": "Partial Match Buyer Profile",
                "partner_id": self.buyer2.id,
                "active": True,
                "material_category_id": self.mat_category.id,
                "polymer_family_id": None,
                "min_order_quantity": 20000.0,
                "latitude": 33.7490,
                "longitude": -84.3880,
            }
        )

    def test_find_matches_exact(self):
        """Test finding exact match buyer"""
        matcher = self.env["plasticos.buyer.matcher"]

        matches = matcher.find_matches_for_supplier(supplier_partner_id=self.supplier.id, max_results=10)

        self.assertTrue(len(matches) > 0, "Should find at least one match")

        # Verify exact match buyer is in results
        buyer_ids = [m["buyer_id"] for m in matches]
        self.assertIn(self.buyer1.id, buyer_ids, "Exact match buyer should be in results")

        # Check exact match has high score
        exact_match = next((m for m in matches if m["buyer_id"] == self.buyer1.id), None)
        self.assertIsNotNone(exact_match)
        self.assertEqual(exact_match["gates_passed"], 10, "Should pass all 10 gates")

    def test_find_matches_partial(self):
        """Test finding partial match buyer"""
        matcher = self.env["plasticos.buyer.matcher"]

        matches = matcher.find_matches_for_supplier(supplier_partner_id=self.supplier.id, max_results=10)

        # Verify partial match buyer might be in results (depends on gate strictness)
        buyer_ids = [m["buyer_id"] for m in matches]
        if self.buyer2.id in buyer_ids:
            partial_match = next((m for m in matches if m["buyer_id"] == self.buyer2.id), None)
            self.assertIsNotNone(partial_match)
            # Partial match should have lower score than exact
            exact_match = next((m for m in matches if m["buyer_id"] == self.buyer1.id), None)
            if exact_match:
                self.assertLess(
                    partial_match["total_score"],
                    exact_match["total_score"],
                    "Partial match should score lower than exact match",
                )

    def test_no_buyers(self):
        """Test matching when no buyers exist"""
        # Deactivate all buyer profiles
        self.buyer1_profile.write({"active": False})
        self.buyer2_profile.write({"active": False})

        matcher = self.env["plasticos.buyer.matcher"]
        matches = matcher.find_matches_for_supplier(supplier_partner_id=self.supplier.id)

        self.assertEqual(len(matches), 0, "Should return empty list when no buyers")

    def test_gate_filtering(self):
        """Test that gates filter out incompatible buyers"""
        # Create buyer with incompatible material
        incompatible_cat = self.env["plasticos.material.category"].create({"name": "Industrial", "code": "IND"})

        incompatible_buyer = self.env["res.partner"].create({"name": "Incompatible Buyer", "customer_rank": 1})

        self.env["plasticos.facility.profile"].create(
            {
                "name": "Incompatible Profile",
                "partner_id": incompatible_buyer.id,
                "active": True,
                "material_category_id": incompatible_cat.id,
                "polymer_family_id": self.polymer_family.id,
            }
        )

        matcher = self.env["plasticos.buyer.matcher"]
        matches = matcher.find_matches_for_supplier(supplier_partner_id=self.supplier.id)

        # Incompatible buyer should not be in results
        buyer_ids = [m["buyer_id"] for m in matches]
        self.assertNotIn(incompatible_buyer.id, buyer_ids, "Incompatible buyer should be filtered out by gates")

    def test_max_results_limit(self):
        """Test max_results parameter limits output"""
        # Create 5 additional buyers
        for i in range(5):
            buyer = self.env["res.partner"].create({"name": f"Bulk Buyer {i+1}", "customer_rank": 1})
            self.env["plasticos.facility.profile"].create(
                {
                    "name": f"Bulk Profile {i+1}",
                    "partner_id": buyer.id,
                    "active": True,
                    "material_category_id": self.mat_category.id,
                    "polymer_family_id": self.polymer_family.id,
                }
            )

        matcher = self.env["plasticos.buyer.matcher"]
        matches = matcher.find_matches_for_supplier(supplier_partner_id=self.supplier.id, max_results=3)

        self.assertLessEqual(len(matches), 3, "Should respect max_results limit")

    def test_invalid_supplier(self):
        """Test error handling for invalid supplier"""
        matcher = self.env["plasticos.buyer.matcher"]

        with self.assertRaises(ValidationError):
            matcher.find_matches_for_supplier(supplier_partner_id=99999)

    def test_scoring_order(self):
        """Test that results are sorted by score descending"""
        matcher = self.env["plasticos.buyer.matcher"]

        matches = matcher.find_matches_for_supplier(supplier_partner_id=self.supplier.id, max_results=10)

        if len(matches) > 1:
            # Verify descending score order
            scores = [m["total_score"] for m in matches]
            self.assertEqual(scores, sorted(scores, reverse=True), "Matches should be sorted by score descending")

    def test_matcher_model_exists(self):
        """Verify the plasticos.buyer.matcher model is registered."""
        self.assertIn(
            "plasticos.buyer.matcher",
            self.env,
        )

    def test_match_result_model_exists(self):
        """Verify the plasticos.match.result model is registered."""
        self.assertIn(
            "plasticos.match.result",
            self.env,
        )
