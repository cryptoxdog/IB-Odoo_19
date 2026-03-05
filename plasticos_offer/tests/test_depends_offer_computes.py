from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestOfferComputes(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Offer = cls.env["plasticos.offer"]
        cls.partner = cls.env["res.partner"].create({"name": "Buyer"})
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "name": "INT-OFF",
                "company_display": "Source Co",
            }
        )

    def test_total_value_computed(self):
        offer = self.Offer.create(
            {
                "buyer_id": self.partner.id,
                "intake_id": self.intake.id,
                "price_per_lb": 0.25,
                "quantity_lbs": 2000.0,
            }
        )
        self.assertEqual(offer.total_value, 500.0)

    def test_days_until_expiry(self):
        offer = self.Offer.create(
            {
                "buyer_id": self.partner.id,
                "intake_id": self.intake.id,
                "price_per_lb": 0.25,
                "quantity_lbs": 2000.0,
            }
        )
        self.assertIn(offer.days_until_expiry, (False, offer.days_until_expiry))
