from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestTransactionComputesDepends(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Transaction = cls.env["plasticos.transaction"]
        cls.partner = cls.env["res.partner"].create({"name": "Tx Buyer"})

    def _tx(self, **vals):
        base = {
            "name": "TX-DEPS",
            "partner_id": self.partner.id,
            "expected_weight_lbs": 1000.0,
            "actual_weight_lbs": 900.0,
            "revenue_total": 1000.0,
            "cost_total": 800.0,
        }
        base.update(vals)
        return self.Transaction.create(base)

    def test_margin_computes_from_revenue_and_cost(self):
        tx = self._tx()
        self.assertAlmostEqual(tx.gross_margin, 200.0)
        tx.write({"cost_total": 500.0})
        self.assertAlmostEqual(tx.gross_margin, 500.0)

    def test_weight_discrepancy_flag_threshold(self):
        tx = self._tx(expected_weight_lbs=1000.0, actual_weight_lbs=940.0)
        self.assertFalse(tx.weight_discrepancy_flagged)
        tx.write({"actual_weight_lbs": 900.0})
        self.assertTrue(tx.weight_discrepancy_flagged)
