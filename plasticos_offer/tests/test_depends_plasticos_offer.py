from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestOfferDepends(TransactionCase):
    """Offer @api.depends computations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Offer = cls.env["plasticos.offer"]
        cls.partner = cls.env["res.partner"].create({"name": "Buyer"})
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": cls.partner.id,
                "quantity_per_load_lbs": 1000.0,
                "loads_per_month": 1,
            }
        )

    def _offer(self, **vals):
        base = {
            "buyer_id": self.partner.id,
            "intake_id": self.intake.id,
            "price_per_lb": 0.25,
            "quantity_lbs": 2000.0,
        }
        base.update(vals)
        return self.Offer.create(base)

    def test_total_value(self):
        offer = self._offer()
        self.assertEqual(offer.total_value, 500.0)
        offer.write({"price_per_lb": 0.5})
        self.assertEqual(offer.total_value, 1000.0)

    def test_days_until_expiry_non_negative(self):
        offer = self._offer()
        if offer.days_until_expiry is not False:
            self.assertGreaterEqual(offer.days_until_expiry, 0)

    def test_display_name_has_buyer_and_state(self):
        offer = self._offer()
        self.assertIn("Buyer", offer.display_name)
        self.assertIn(offer.state, offer.display_name)
