"""Offer-owned intake actions. Base intake installs without this module."""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "contract")
class TestIntakeOfferContract(PlasticosTestCase):
    def test_action_send_offer_exists(self):
        self.assertTrue(callable(getattr(self.env["plasticos.intake"], "action_send_offers", None)))
        intake = self._create_intake()
        self.assertEqual(intake.status, "draft")
        with self.assertRaises(UserError):
            intake.action_send_offers()
        self.assertEqual(intake.status, "draft")

    def test_action_send_offers_exists(self):
        self.assertTrue(callable(getattr(self.env["plasticos.intake"], "action_send_offers", None)))
