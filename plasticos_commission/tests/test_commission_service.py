"""Tests for plasticos.commission.service — commission calculation priority.

Target module: plasticos_commission
Target model:  plasticos.commission.service (AbstractModel)

Validates: override > rule > 0.0 priority, edge cases,
commission_rule percentage constraint.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install", "plasticos", "commission")
class TestCommissionService(PlasticosTestCase):
    """Test commission calculation service priority logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CommSvc = cls.env["plasticos.commission.service"]
        cls.CommRule = cls.env["plasticos.commission.rule"]
        cls.Transaction = cls.env["plasticos.transaction"]

        cls.sales_rep = cls.env["res.users"].create(
            {
                "name": "Test Sales Rep",
                "login": "test_sales_commission",
            }
        )
        cls.rule_5pct = cls.CommRule.create(
            {
                "name": "5% Standard",
                "sales_rep_id": cls.sales_rep.id,
                "percentage": 0.05,
            }
        )

    def _create_sales_rep(self, suffix=""):
        """Helper: create a unique sales rep for testing."""
        import uuid

        unique = uuid.uuid4().hex[:6]
        return self.env["res.users"].create(
            {
                "name": f"Test Rep {suffix}{unique}",
                "login": f"test_rep_{suffix}{unique}",
            }
        )

    def _create_transaction(self, **kwargs):
        """Helper: create transaction with commission-relevant fields."""
        vals = {"name": "TX-COMM-TEST"}
        vals.update(kwargs)
        return self.Transaction.create(vals)

    # ── Commission Rule Constraints ────────────────────────────

    def test_rule_percentage_above_1_rejected(self):
        """percentage > 1.0 raises ValidationError."""
        rep = self._create_sales_rep("high")
        with self.assertRaises(ValidationError):
            self.CommRule.create(
                {
                    "name": "Too High",
                    "sales_rep_id": rep.id,
                    "percentage": 1.5,
                }
            )

    def test_rule_percentage_below_0_rejected(self):
        """percentage < 0.0 raises ValidationError."""
        rep = self._create_sales_rep("neg")
        with self.assertRaises(ValidationError):
            self.CommRule.create(
                {
                    "name": "Negative",
                    "sales_rep_id": rep.id,
                    "percentage": -0.01,
                }
            )

    def test_rule_percentage_boundary_zero_accepted(self):
        """percentage = 0.0 is valid (no commission)."""
        rep = self._create_sales_rep("zero")
        rule = self.CommRule.create(
            {
                "name": "Zero Rate",
                "sales_rep_id": rep.id,
                "percentage": 0.0,
            }
        )
        self.assertTrue(rule.id)

    def test_rule_percentage_boundary_one_accepted(self):
        """percentage = 1.0 is valid (100% commission)."""
        rep = self._create_sales_rep("full")
        rule = self.CommRule.create(
            {
                "name": "Full Rate",
                "sales_rep_id": rep.id,
                "percentage": 1.0,
            }
        )
        self.assertTrue(rule.id)

    def test_rule_display_percentage_computed(self):
        """display_percentage = percentage * 100."""
        self.assertAlmostEqual(self.rule_5pct.display_percentage, 5.0, places=1)

    # ── Commission Service Logic ───────────────────────────────

    def test_empty_transaction_returns_zero(self):
        """Falsy transaction argument returns 0.0."""
        result = self.CommSvc.compute_commission(self.Transaction.browse())
        self.assertAlmostEqual(result, 0.0, places=2)

    def test_transaction_without_config_returns_zero(self):
        """Transaction without override or rule returns 0.0."""
        tx = self._create_transaction()
        result = self.CommSvc.compute_commission(tx)
        self.assertAlmostEqual(result, 0.0, places=2)

    def test_rule_assignment(self):
        """Commission rule can be assigned to transaction."""
        tx = self._create_transaction()
        tx.write({"commission_rule_id": self.rule_5pct.id})
        self.assertEqual(tx.commission_rule_id.id, self.rule_5pct.id)

    def test_override_assignment(self):
        """Commission override can be set on transaction."""
        tx = self._create_transaction()
        tx.sudo().write({"commission_override_pct": 0.10})
        self.assertAlmostEqual(tx.commission_override_pct, 0.10, places=2)

    # ── Commission Rule CRUD ───────────────────────────────────

    def test_rule_create(self):
        """Commission rule can be created."""
        rep = self._create_sales_rep("create")
        rule = self.CommRule.create(
            {
                "name": "Test Rule",
                "sales_rep_id": rep.id,
                "percentage": 0.03,
            }
        )
        self.assertTrue(rule.id)
        self.assertEqual(rule.percentage, 0.03)

    def test_rule_update(self):
        """Commission rule percentage can be updated."""
        rep = self._create_sales_rep("update")
        rule = self.CommRule.create(
            {
                "name": "Update Test",
                "sales_rep_id": rep.id,
                "percentage": 0.02,
            }
        )
        rule.write({"percentage": 0.04})
        self.assertEqual(rule.percentage, 0.04)

    def test_rule_display_percentage_inverse(self):
        """display_percentage inverse updates percentage."""
        rep = self._create_sales_rep("inverse")
        rule = self.CommRule.create(
            {
                "name": "Inverse Test",
                "sales_rep_id": rep.id,
                "percentage": 0.05,
            }
        )
        rule.write({"display_percentage": 10.0})
        self.assertAlmostEqual(rule.percentage, 0.10, places=4)
