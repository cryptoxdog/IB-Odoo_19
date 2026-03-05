from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestTransactionConstraintsValidation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Transaction = cls.env["plasticos.transaction"]
        cls.partner = cls.env["res.partner"].create({"name": "Tx Partner"})

    def _new_tx(self, **vals):
        base = {
            "name": "TX-CONSTRAINT",
            "partner_id": self.partner.id,
            "expected_weight_lbs": 1000.0,
            "actual_weight_lbs": 1000.0,
        }
        base.update(vals)
        return self.Transaction.create(base)

    def test_weight_variance_positive_ok(self):
        tx = self._new_tx(expected_weight_lbs=1000.0, actual_weight_lbs=900.0)
        self.assertLessEqual(tx.weight_variance_percent, 0.1)

    def test_negative_expected_weight_forbidden(self):
        with self.assertRaises(ValidationError):
            self._new_tx(expected_weight_lbs=-1.0)

    def test_margin_lower_than_floor_forbidden(self):
        tx = self._new_tx(revenue_total=1000.0, cost_total=999.0)
        tx.margin_floor_pct = 0.20
        with self.assertRaises(ValidationError):
            tx._check_margin_floor()

    def test_closed_transaction_cannot_change_partner(self):
        tx = self._new_tx(state="closed")
        with self.assertRaises(ValidationError):
            tx.write({"partner_id": self.partner.copy().id})
