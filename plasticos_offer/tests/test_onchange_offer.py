from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestOfferOnchange(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Offer = cls.env["plasticos.offer"]
        cls.buyer = cls.env["res.partner"].create({"name": "Buyer"})
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "name": "INT-ONCHANGE",
                "company_display": "Source Co",
            }
        )

    def test_onchange_pricing_updates_total(self):
        offer = self.Offer.new(
            {
                "buyer_id": self.buyer.id,
                "intake_id": self.intake.id,
                "price_per_lb": 0.50,
                "quantity_lbs": 1000.0,
            }
        )
        offer._onchange_pricing()
        self.assertEqual(offer.total_value, 500.0)

    def test_onchange_intake_sets_display_name(self):
        offer = self.Offer.new({"intake_id": self.intake.id, "buyer_id": self.buyer.id})
        offer._onchange_intake_id()
        self.assertIn("Offer:", offer.display_name or "")
