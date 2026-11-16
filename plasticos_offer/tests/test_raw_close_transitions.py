"""A raw ``write`` of ``state`` follows the same closing rules as ``action_cancel`` and ``action_reject``.

PR #517 review: ``action_cancel`` and ``action_reject`` refuse an accepted offer, but
the transition validator let ``write({"state": "cancelled"})`` move it.
"""

from datetime import timedelta

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_offer.tests.test_manual_send import send_offer_email
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "offer")
class TestRawCloseTransitions(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls._create_partner("Raw Close Supplier", supplier_rank=1)
        cls.buyer = cls._create_partner("Raw Close Buyer", customer_rank=1)
        cls.intake = cls._create_intake(partner=cls.supplier, polymer=cls.default_polymer, form=cls.default_form)

    def _offer(self):
        return self.env["plasticos.offer"].create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "price_per_lb": 0.2,
                "quantity_lbs": 40000,
                "valid_until": fields.Date.today() + timedelta(days=30),
            }
        )

    def _accepted(self):
        offer = send_offer_email(self._offer())
        offer.action_accept()
        return offer

    def test_accepted_offer_cannot_be_closed_by_raw_write(self):
        for target in ("cancelled", "rejected", "expired"):
            offer = self._accepted()
            with self.assertRaises(UserError):
                offer.write({"state": target})
            self.assertEqual(offer.state, "accepted")

    def test_cancelled_offer_cannot_be_rejected_by_raw_write(self):
        offer = self._offer()
        offer.action_cancel()
        with self.assertRaises(UserError):
            offer.write({"state": "rejected"})
        self.assertEqual(offer.state, "cancelled")

    def test_open_offers_still_close_by_raw_write(self):
        sent = send_offer_email(self._offer())
        sent.write({"state": "rejected"})
        self.assertEqual(sent.state, "rejected")
        draft = self._offer()
        draft.write({"state": "cancelled"})
        self.assertEqual(draft.state, "cancelled")
