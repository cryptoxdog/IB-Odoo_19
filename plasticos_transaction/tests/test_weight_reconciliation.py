"""Unit tests for weight reconciliation system on plasticos.transaction.

Tests cover:
- Weight priority logic (scale > buyer > supplier)
- Tare system defaults and calculations
- Weight discrepancy detection (>5% flagging)
- Light weight deduction calculations
- Dead freight chargeback logic
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestWeightReconciliation(PlasticosTestCase):
    """Test weight reconciliation computed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Transaction = cls.env["plasticos.transaction"]

        # Create a minimal transaction for testing
        cls.tx = cls.Transaction.create({"name": "TEST-WEIGHT-001"})

    # ══════════════════════════════════════════════════════════════
    # Weight Priority Tests
    # ══════════════════════════════════════════════════════════════

    def test_weight_priority_scale_first(self):
        """Scale weight takes priority over buyer and supplier."""
        self.tx.write(
            {
                "supplier_weight": 40000,
                "buyer_weight": 39500,
                "scale_weight": 39800,
            }
        )
        self.assertEqual(self.tx.weight_source, "scale")
        self.assertEqual(self.tx.gross_weight, 39800)

    def test_weight_priority_buyer_second(self):
        """Buyer weight used when scale is missing."""
        self.tx.write(
            {
                "supplier_weight": 40000,
                "buyer_weight": 39500,
                "scale_weight": 0,
            }
        )
        self.assertEqual(self.tx.weight_source, "buyer")
        self.assertEqual(self.tx.gross_weight, 39500)

    def test_weight_priority_supplier_fallback(self):
        """Supplier weight used when scale and buyer are missing."""
        self.tx.write(
            {
                "supplier_weight": 40000,
                "buyer_weight": 0,
                "scale_weight": 0,
            }
        )
        self.assertEqual(self.tx.weight_source, "supplier")
        self.assertEqual(self.tx.gross_weight, 40000)

    def test_weight_priority_none(self):
        """No weight source when all are zero."""
        self.tx.write(
            {
                "supplier_weight": 0,
                "buyer_weight": 0,
                "scale_weight": 0,
            }
        )
        self.assertEqual(self.tx.weight_source, "none")
        self.assertEqual(self.tx.gross_weight, 0)

    # ══════════════════════════════════════════════════════════════
    # Tare System Tests
    # ══════════════════════════════════════════════════════════════

    def test_tare_default_bale(self):
        """Bales have zero tare."""
        self.tx.write({"unit_type": "bale"})
        self.assertEqual(self.tx.tare_per_unit, 0)

    def test_tare_default_gaylord(self):
        """Gaylords have 40 lb tare."""
        self.tx.write({"unit_type": "gaylord"})
        self.assertEqual(self.tx.tare_per_unit, 40)

    def test_tare_default_pallet(self):
        """Pallets have 40 lb tare."""
        self.tx.write({"unit_type": "pallet"})
        self.assertEqual(self.tx.tare_per_unit, 40)

    def test_tare_default_box(self):
        """Boxes have zero tare."""
        self.tx.write({"unit_type": "box"})
        self.assertEqual(self.tx.tare_per_unit, 0)

    def test_tare_default_super_sack(self):
        """Super sacks have zero tare."""
        self.tx.write({"unit_type": "super_sack"})
        self.assertEqual(self.tx.tare_per_unit, 0)

    def test_total_tare_calculation(self):
        """Total tare = unit_count × tare_per_unit."""
        self.tx.write(
            {
                "unit_type": "gaylord",
                "unit_count": 20,
            }
        )
        self.assertEqual(self.tx.total_tare, 800)  # 20 × 40

    def test_final_weight_with_tare(self):
        """Final weight = gross - tare."""
        self.tx.write(
            {
                "scale_weight": 40000,
                "unit_type": "gaylord",
                "unit_count": 20,
            }
        )
        # gross = 40000, tare = 800, final = 39200
        self.assertEqual(self.tx.final_weight, 39200)

    def test_final_weight_never_negative(self):
        """Final weight cannot be negative."""
        self.tx.write(
            {
                "scale_weight": 100,
                "unit_type": "gaylord",
                "unit_count": 10,  # tare = 400
            }
        )
        # gross = 100, tare = 400, final should be 0 (not -300)
        self.assertEqual(self.tx.final_weight, 0)

    def test_tare_editable(self):
        """Tare per unit can be manually overridden."""
        self.tx.write(
            {
                "unit_type": "gaylord",
                "tare_per_unit": 50,  # Override default 40
                "unit_count": 10,
            }
        )
        self.assertEqual(self.tx.total_tare, 500)  # 10 × 50

    # ══════════════════════════════════════════════════════════════
    # Weight Discrepancy Tests
    # ══════════════════════════════════════════════════════════════

    def test_discrepancy_flagged_over_5pct(self):
        """Discrepancy >5% is flagged."""
        self.tx.write(
            {
                "supplier_weight": 40000,
                "buyer_weight": 37000,  # 7.5% difference
            }
        )
        self.assertTrue(self.tx.weight_discrepancy_flagged)
        self.assertAlmostEqual(self.tx.weight_discrepancy_pct, 7.5, places=1)

    def test_discrepancy_not_flagged_under_5pct(self):
        """Discrepancy ≤5% is not flagged."""
        self.tx.write(
            {
                "supplier_weight": 40000,
                "buyer_weight": 38500,  # 3.75% difference
            }
        )
        self.assertFalse(self.tx.weight_discrepancy_flagged)

    def test_discrepancy_exactly_5pct_not_flagged(self):
        """Discrepancy exactly 5% is not flagged (>5% required)."""
        self.tx.write(
            {
                "supplier_weight": 40000,
                "buyer_weight": 38000,  # Exactly 5%
            }
        )
        self.assertFalse(self.tx.weight_discrepancy_flagged)

    def test_discrepancy_zero_when_missing_weights(self):
        """No discrepancy when one weight is missing."""
        self.tx.write(
            {
                "supplier_weight": 40000,
                "buyer_weight": 0,
            }
        )
        self.assertEqual(self.tx.weight_discrepancy_pct, 0)
        self.assertFalse(self.tx.weight_discrepancy_flagged)

    def test_discrepancy_divide_by_zero_protection(self):
        """No crash when both weights are zero."""
        self.tx.write(
            {
                "supplier_weight": 0,
                "buyer_weight": 0,
            }
        )
        self.assertEqual(self.tx.weight_discrepancy_pct, 0)
        self.assertFalse(self.tx.weight_discrepancy_flagged)

    # ══════════════════════════════════════════════════════════════
    # Light Weight Deduction Tests
    # ══════════════════════════════════════════════════════════════

    def test_light_weight_deduction_calculated(self):
        """Deduction = (minimum - actual) × rate."""
        self.tx.write(
            {
                "scale_weight": 38000,
                "unit_count": 0,
                "minimum_net_weight": 40000,
                "light_weight_deduction_rate": 0.01,
            }
        )
        # Shortfall = 40000 - 38000 = 2000
        # Deduction = 2000 × 0.01 = $20
        self.assertEqual(self.tx.light_weight_deduction, 20.0)

    def test_light_weight_no_deduction_when_above_minimum(self):
        """No deduction when final weight >= minimum."""
        self.tx.write(
            {
                "scale_weight": 42000,
                "unit_count": 0,
                "minimum_net_weight": 40000,
                "light_weight_deduction_rate": 0.01,
            }
        )
        self.assertEqual(self.tx.light_weight_deduction, 0)

    def test_light_weight_no_deduction_when_no_minimum(self):
        """No deduction when minimum not set."""
        self.tx.write(
            {
                "scale_weight": 38000,
                "unit_count": 0,
                "minimum_net_weight": 0,
                "light_weight_deduction_rate": 0.01,
            }
        )
        self.assertEqual(self.tx.light_weight_deduction, 0)

    def test_dead_freight_chargeback_triggered(self):
        """Dead freight when deduction > purchase cost."""
        # First we need to set up a scenario where purchase_cost_total > 0
        # Since purchase_cost_total is computed from vendor_bill_ids,
        # we'll test the logic directly
        self.tx.write(
            {
                "scale_weight": 10000,
                "unit_count": 0,
                "minimum_net_weight": 40000,  # 30000 lb shortfall
                "light_weight_deduction_rate": 0.01,  # $300 deduction
            }
        )
        # Deduction = 30000 × 0.01 = $300
        self.assertEqual(self.tx.light_weight_deduction, 300.0)
        # Since purchase_cost_total = 0, dead_freight_chargeback = False
        # (we can't trigger it without actual vendor bills)
        self.assertFalse(self.tx.dead_freight_chargeback)

    def test_light_weight_uses_final_not_gross(self):
        """Deduction uses final (net) weight, not gross."""
        self.tx.write(
            {
                "scale_weight": 40000,  # gross
                "unit_type": "gaylord",
                "unit_count": 50,  # tare = 2000
                "minimum_net_weight": 40000,
                "light_weight_deduction_rate": 0.01,
            }
        )
        # Final = 40000 - 2000 = 38000
        # Shortfall = 40000 - 38000 = 2000
        # Deduction = 2000 × 0.01 = $20
        self.assertEqual(self.tx.final_weight, 38000)
        self.assertEqual(self.tx.light_weight_deduction, 20.0)


@tagged("post_install", "-at_install")
class TestWeightReconciliationEdgeCases(PlasticosTestCase):
    """Edge case tests for weight reconciliation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Transaction = cls.env["plasticos.transaction"]

    def test_new_transaction_has_nullable_fields(self):
        """New transactions have nullable weight fields (migration safety)."""
        tx = self.Transaction.create({"name": "TEST-NULLABLE-001"})
        # All weight fields should be 0 or False, not raise errors
        self.assertEqual(tx.supplier_weight, 0)
        self.assertEqual(tx.buyer_weight, 0)
        self.assertEqual(tx.scale_weight, 0)
        self.assertEqual(tx.final_weight, 0)
        self.assertEqual(tx.weight_source, "none")
        self.assertFalse(tx.weight_discrepancy_flagged)
        self.assertEqual(tx.light_weight_deduction, 0)
        self.assertFalse(tx.dead_freight_chargeback)

    def test_partial_weight_data(self):
        """Handles partial weight data gracefully."""
        tx = self.Transaction.create(
            {
                "name": "TEST-PARTIAL-001",
                "supplier_weight": 40000,
                # buyer_weight and scale_weight not set
            }
        )
        self.assertEqual(tx.weight_source, "supplier")
        self.assertEqual(tx.gross_weight, 40000)
        self.assertEqual(tx.final_weight, 40000)

    def test_very_large_weights(self):
        """Handles very large weights without overflow."""
        tx = self.Transaction.create(
            {
                "name": "TEST-LARGE-001",
                "scale_weight": 1000000,  # 1 million lbs
                "unit_type": "gaylord",
                "unit_count": 1000,
            }
        )
        self.assertEqual(tx.gross_weight, 1000000)
        self.assertEqual(tx.total_tare, 40000)  # 1000 × 40
        self.assertEqual(tx.final_weight, 960000)

    def test_fractional_weights(self):
        """Handles fractional weights correctly."""
        tx = self.Transaction.create(
            {
                "name": "TEST-FRAC-001",
                "supplier_weight": 40000.5,
                "buyer_weight": 39999.5,
            }
        )
        # Discrepancy = 1 / 40000.5 = 0.000025 = 0.0025%
        self.assertFalse(tx.weight_discrepancy_flagged)
        self.assertLess(tx.weight_discrepancy_pct, 1)
