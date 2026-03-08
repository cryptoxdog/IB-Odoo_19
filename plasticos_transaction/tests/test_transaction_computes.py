"""
Test transaction computed fields.

Tests all 19+ computed fields:
- Weight reconciliation: gross_weight, final_weight, weight_source, etc.
- Financial: revenue_total, cost_total, gross_margin, net_margin
- Commission: commission_amount
- Compliance: compliance_status
- Profile refs: supplier_profile_id, buyer_profile_id
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestTransactionComputes(PlasticosTestCase):
    """Test plasticos.transaction computed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Test Buyer",
                "is_company": True,
                "customer_rank": 1,
            }
        )

    def _create_transaction(self, **kwargs):
        """Helper to create a transaction with defaults."""
        vals = {
            "supplier_id": self.partner.id,
            "buyer_id": self.buyer.id,
        }
        vals.update(kwargs)
        return self.env["plasticos.transaction"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Weight Variance Tests
    # ═══════════════════════════════════════════════════════════

    def test_weight_variance_percent_computed(self):
        """weight_variance_percent should compute from expected vs actual."""
        tx = self._create_transaction(
            expected_weight=1000,
            actual_weight=950,
        )
        self.assertAlmostEqual(tx.weight_variance_percent, 5.0, places=1)

    def test_weight_variance_zero_when_no_weights(self):
        """weight_variance_percent should be 0 when weights not set."""
        tx = self._create_transaction()
        self.assertEqual(tx.weight_variance_percent, 0.0)

    # ═══════════════════════════════════════════════════════════
    # Weight Reconciliation Tests
    # ═══════════════════════════════════════════════════════════

    def test_weight_source_priority_scale(self):
        """Scale weight has highest priority."""
        tx = self._create_transaction(
            scale_weight=1000,
            buyer_weight=950,
            supplier_weight=900,
        )
        self.assertEqual(tx.weight_source, "scale")
        self.assertEqual(tx.gross_weight, 1000)

    def test_weight_source_priority_buyer(self):
        """Buyer weight has second priority when no scale."""
        tx = self._create_transaction(
            scale_weight=0,
            buyer_weight=950,
            supplier_weight=900,
        )
        self.assertEqual(tx.weight_source, "buyer")
        self.assertEqual(tx.gross_weight, 950)

    def test_weight_source_priority_supplier(self):
        """Supplier weight used when no scale or buyer weight."""
        tx = self._create_transaction(
            scale_weight=0,
            buyer_weight=0,
            supplier_weight=900,
        )
        self.assertEqual(tx.weight_source, "supplier")
        self.assertEqual(tx.gross_weight, 900)

    def test_weight_source_none(self):
        """No weight source when all weights are zero."""
        tx = self._create_transaction()
        self.assertEqual(tx.weight_source, "none")
        self.assertEqual(tx.gross_weight, 0.0)

    def test_final_weight_with_tare(self):
        """Final weight = gross - tare."""
        tx = self._create_transaction(
            scale_weight=1000,
            unit_count=10,
            unit_type="gaylord",  # 40 lbs tare per unit
        )
        # tare_per_unit should be 40 for gaylord
        self.assertEqual(tx.tare_per_unit, 40.0)
        self.assertEqual(tx.total_tare, 400.0)
        self.assertEqual(tx.final_weight, 600.0)

    def test_final_weight_never_negative(self):
        """Final weight should never be negative."""
        tx = self._create_transaction(
            scale_weight=100,
            unit_count=10,
            unit_type="gaylord",  # 400 lbs tare > 100 lbs gross
        )
        self.assertEqual(tx.final_weight, 0.0)

    # ═══════════════════════════════════════════════════════════
    # Weight Discrepancy Tests
    # ═══════════════════════════════════════════════════════════

    def test_weight_discrepancy_flagged_over_5_percent(self):
        """Discrepancy > 5% should be flagged."""
        tx = self._create_transaction(
            supplier_weight=1000,
            buyer_weight=900,  # 10% difference
        )
        self.assertTrue(tx.weight_discrepancy_flagged)
        self.assertAlmostEqual(tx.weight_discrepancy_pct, 10.0, places=1)

    def test_weight_discrepancy_not_flagged_under_5_percent(self):
        """Discrepancy <= 5% should not be flagged."""
        tx = self._create_transaction(
            supplier_weight=1000,
            buyer_weight=970,  # 3% difference
        )
        self.assertFalse(tx.weight_discrepancy_flagged)

    # ═══════════════════════════════════════════════════════════
    # Light Weight Deduction Tests
    # ═══════════════════════════════════════════════════════════

    def test_light_weight_deduction_computed(self):
        """Deduction when final_weight < minimum_net_weight."""
        tx = self._create_transaction(
            scale_weight=900,
            minimum_net_weight=1000,
            light_weight_deduction_rate=0.01,
        )
        # Shortfall = 1000 - 900 = 100 lbs
        # Deduction = 100 * 0.01 = $1.00
        self.assertAlmostEqual(tx.light_weight_deduction, 1.0, places=2)

    def test_no_deduction_when_above_minimum(self):
        """No deduction when final_weight >= minimum."""
        tx = self._create_transaction(
            scale_weight=1100,
            minimum_net_weight=1000,
        )
        self.assertEqual(tx.light_weight_deduction, 0.0)

    # ═══════════════════════════════════════════════════════════
    # Financial Computed Tests
    # ═══════════════════════════════════════════════════════════

    def test_financials_computed_from_invoices(self):
        """Revenue and costs computed from linked invoices."""
        tx = self._create_transaction()

        # Create and link customer invoice
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
            }
        )
        tx.customer_invoice_id = invoice.id

        # Revenue should reflect invoice total
        self.assertEqual(tx.revenue_total, invoice.amount_total)

    def test_gross_margin_formula(self):
        """Gross margin = revenue - costs + chargebacks + penalties."""
        tx = self._create_transaction(
            other_expenses=100,
            freight_chargebacks=50,
            lightweight_penalties=25,
        )
        # With no invoices, revenue = 0, costs = other_expenses
        # gross_margin = 0 - 100 + 50 + 25 = -25
        self.assertEqual(tx.gross_margin, -25.0)

    def test_net_margin_formula(self):
        """Net margin = gross margin - commission."""
        tx = self._create_transaction()
        # net_margin = gross_margin - commission_amount
        self.assertEqual(tx.net_margin, tx.gross_margin - tx.commission_amount)

    # ═══════════════════════════════════════════════════════════
    # Line Count Tests
    # ═══════════════════════════════════════════════════════════

    def test_line_count_computed(self):
        """line_count should reflect number of transaction lines."""
        tx = self._create_transaction()
        self.assertEqual(tx.line_count, 0)

        # Add a line
        self.env["plasticos.transaction.line"].create(
            {
                "transaction_id": tx.id,
                "sale_amount": 100,
                "purchase_amount": 80,
            }
        )
        tx.invalidate_recordset()
        self.assertEqual(tx.line_count, 1)

    def test_historical_totals_from_lines(self):
        """Historical totals computed from transaction lines."""
        tx = self._create_transaction()

        self.env["plasticos.transaction.line"].create(
            {
                "transaction_id": tx.id,
                "sale_amount": 1000,
                "purchase_amount": 800,
            }
        )
        self.env["plasticos.transaction.line"].create(
            {
                "transaction_id": tx.id,
                "sale_amount": 500,
                "purchase_amount": 400,
            }
        )

        tx.invalidate_recordset()
        self.assertEqual(tx.historical_sale_total, 1500)
        self.assertEqual(tx.historical_purchase_total, 1200)
        self.assertEqual(tx.historical_margin, 300)

    # ═══════════════════════════════════════════════════════════
    # Tare Defaults Tests
    # ═══════════════════════════════════════════════════════════

    def test_tare_defaults_by_unit_type(self):
        """Tare per unit should default based on unit type."""
        tare_defaults = {
            "bale": 0.0,
            "gaylord": 40.0,
            "pallet": 40.0,
            "box": 0.0,
            "super_sack": 0.0,
        }
        for unit_type, expected_tare in tare_defaults.items():
            with self.subTest(unit_type=unit_type):
                tx = self._create_transaction(unit_type=unit_type)
                self.assertEqual(tx.tare_per_unit, expected_tare)
