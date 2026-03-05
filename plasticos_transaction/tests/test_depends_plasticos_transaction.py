from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestTransactionDepends(TransactionCase):
    """All key @api.depends fields on plasticos.transaction."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Transaction = cls.env["plasticos.transaction"]
        cls.partner = cls.env["res.partner"].create({"name": "Tx Partner"})

    def _tx(self, **vals):
        base = {
            "name": "TX-DEPS",
            "partner_id": self.partner.id,
            "expected_weight_lbs": 1000.0,
            "actual_weight_lbs": 900.0,
            "revenue_total": 1000.0,
            "purchase_cost_total": 600.0,
            "freight_cost_total": 100.0,
        }
        base.update(vals)
        return self.Transaction.create(base)

    def test_weight_variance_and_flags(self):
        tx = self._tx(expected_weight_lbs=1000.0, actual_weight_lbs=970.0)
        self.assertAlmostEqual(round(tx.weight_discrepancy_pct, 2), 3.0)
        self.assertFalse(tx.weight_discrepancy_flagged)
        tx.write({"actual_weight_lbs": 900.0})
        self.assertGreaterEqual(tx.weight_discrepancy_pct, 10.0)
        self.assertTrue(tx.weight_discrepancy_flagged)

    def test_gross_and_net_margin(self):
        tx = self._tx()
        self.assertAlmostEqual(tx.cost_total, 700.0)
        self.assertAlmostEqual(tx.gross_margin, 300.0)
        self.assertGreaterEqual(tx.net_margin, 0.0)
        tx.write({"freight_cost_total": 300.0})
        self.assertLess(tx.net_margin, tx.gross_margin)

    def test_commission_amount_respects_override(self):
        tx = self._tx()
        self.assertGreaterEqual(tx.commission_amount, 0.0)
        tx.write({"commission_override_pct": 0.10})
        self.assertAlmostEqual(tx.commission_amount, tx.net_margin * 0.10)

    def test_display_name_includes_partner_and_state(self):
        tx = self._tx()
        self.assertIn("Tx Partner", tx.display_name)
        self.assertIn(tx.state, tx.display_name)
