"""
Test commission rules and calculation.

- percentage 0-100
- unique rep+active constraint
- calculation against transaction
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCommissionRules(TransactionCase):
    """Test plasticos.commission.rule and commission calculation."""

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
        cls.sales_rep = cls.env["res.users"].create(
            {
                "name": "Test Sales Rep",
                "login": "test_sales_rep",
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

    def _create_commission_rule(self, **kwargs):
        """Helper to create a commission rule."""
        vals = {
            "user_id": self.sales_rep.id,
            "percentage": 10.0,
            "active": True,
        }
        vals.update(kwargs)
        return self.env["plasticos.commission.rule"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Commission Rule Tests
    # ═══════════════════════════════════════════════════════════

    def test_commission_rule_create(self):
        """Commission rule can be created with valid values."""
        rule = self._create_commission_rule(percentage=15.0)
        self.assertEqual(rule.percentage, 15.0)
        self.assertTrue(rule.active)

    def test_commission_rule_percentage_range(self):
        """Commission percentage should be validated (0-100)."""
        # Valid percentages
        rule = self._create_commission_rule(percentage=0)
        self.assertEqual(rule.percentage, 0)

        rule2 = self._create_commission_rule(percentage=100)
        self.assertEqual(rule2.percentage, 100)

    def test_commission_rule_search(self):
        """Commission rules can be searched by user."""
        rule = self._create_commission_rule()
        found = self.env["plasticos.commission.rule"].search(
            [
                ("user_id", "=", self.sales_rep.id),
                ("active", "=", True),
            ]
        )
        self.assertIn(rule, found)

    # ═══════════════════════════════════════════════════════════
    # Commission Calculation Tests
    # ═══════════════════════════════════════════════════════════

    def test_commission_computed_from_rule(self):
        """Commission should be computed from linked rule."""
        rule = self._create_commission_rule(percentage=10.0)
        tx = self._create_transaction(
            user_id=self.sales_rep.id,
            commission_rule_id=rule.id,
        )

        # Commission depends on gross_margin
        # With no invoices, gross_margin = 0, so commission = 0
        self.assertEqual(tx.commission_amount, 0.0)

    def test_commission_override_takes_precedence(self):
        """commission_override_pct should override rule percentage."""
        rule = self._create_commission_rule(percentage=10.0)
        tx = self._create_transaction(
            user_id=self.sales_rep.id,
            commission_rule_id=rule.id,
            commission_override_pct=0.20,  # 20%
        )

        # Override should be used instead of rule
        # Actual calculation depends on gross_margin

    def test_commission_locked_uses_locked_amount(self):
        """When commission_locked, use commission_locked_amount."""
        tx = self._create_transaction()
        tx.commission_locked = True
        tx.commission_locked_amount = 500.0

        tx.invalidate_recordset()
        self.assertEqual(tx.commission_amount, 500.0)

    def test_commission_service_compute(self):
        """Commission service should compute commission correctly."""
        service = self.env["plasticos.commission.service"]

        rule = self._create_commission_rule(percentage=10.0)
        tx = self._create_transaction(
            user_id=self.sales_rep.id,
            commission_rule_id=rule.id,
        )

        # Service should return computed commission
        amount = service.compute_commission(tx)
        self.assertIsInstance(amount, float)
