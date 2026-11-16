"""A closed offer admits ``transaction_id`` only as the first link of an accepted offer.

PR #516 review: ``_plasticos_post_close_fields`` admitted ``transaction_id`` on every
closed offer, so an ordinary write could overwrite or clear the link. Only the
compiler's first link (``_plasticos_link_transaction``) may set it.
"""

from datetime import timedelta

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_offer.tests.test_manual_send import send_offer_email
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "transaction", "offer")
class TestOfferTransactionLinkFreeze(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls._create_partner("Link Freeze Supplier", supplier_rank=1)
        cls.buyer = cls._create_partner("Link Freeze Buyer", customer_rank=1)
        cls.intake = cls._create_intake(partner=cls.supplier, polymer=cls.default_polymer, form=cls.default_form)
        cls.product = cls.env["product.product"].create({"name": "Link Freeze Goods", "type": "consu"})

    def _offer(self):
        offer = self.env["plasticos.offer"].create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "price_per_lb": 0.25,
                "quantity_lbs": 40000,
                "valid_until": fields.Date.today() + timedelta(days=30),
            }
        )
        return send_offer_email(offer)

    def _accepted_offer(self):
        offer = self._offer()
        offer.action_accept()
        self.assertEqual(offer.state, "accepted")
        return offer

    def _transaction_for(self, origin):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.buyer.id,
                "origin": origin,
                "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1, "price_unit": 1.0})],
            }
        )
        return self.env["plasticos.transaction"].create({"sale_order_id": order.id})

    def test_first_link_of_accepted_offer_is_admitted(self):
        offer = self._accepted_offer()
        tx = self._transaction_for(offer.name)
        offer.write({"transaction_id": tx.id})
        self.assertEqual(offer.transaction_id, tx)

    def test_compiler_link_path_still_links(self):
        offer = self._accepted_offer()
        tx = self._transaction_for(offer.name)
        offer._plasticos_link_transaction(tx)
        self.assertEqual(offer.transaction_id, tx)

    def test_same_value_again_is_a_no_op(self):
        offer = self._accepted_offer()
        tx = self._transaction_for(offer.name)
        offer.write({"transaction_id": tx.id})
        offer.write({"transaction_id": tx.id})
        self.assertEqual(offer.transaction_id, tx)

    def test_overwrite_is_refused(self):
        offer = self._accepted_offer()
        tx = self._transaction_for(offer.name)
        offer.write({"transaction_id": tx.id})
        other = self._transaction_for(offer.name)
        with self.assertRaises(UserError):
            offer.write({"transaction_id": other.id})
        self.assertEqual(offer.transaction_id, tx)

    def test_clear_is_refused(self):
        offer = self._accepted_offer()
        tx = self._transaction_for(offer.name)
        offer.write({"transaction_id": tx.id})
        with self.assertRaises(UserError):
            offer.write({"transaction_id": False})
        self.assertEqual(offer.transaction_id, tx)

    def test_transaction_of_another_offer_is_refused(self):
        offer = self._accepted_offer()
        tx = self._transaction_for("SOME-OTHER-OFFER")
        with self.assertRaises(UserError):
            offer.write({"transaction_id": tx.id})
        self.assertFalse(offer.transaction_id)

    def test_link_on_rejected_or_cancelled_offer_is_refused(self):
        for action in ("action_reject", "action_cancel"):
            offer = self._offer()
            getattr(offer, action)()
            tx = self._transaction_for(offer.name)
            with self.assertRaises(UserError):
                offer.write({"transaction_id": tx.id})
            self.assertFalse(offer.transaction_id)

    def test_link_cannot_be_cleared_while_the_state_changes(self):
        offer = self._accepted_offer()
        tx = self._transaction_for(offer.name)
        offer.write({"transaction_id": tx.id})
        with self.assertRaises(UserError):
            offer.write({"state": "cancelled", "transaction_id": False})
        self.assertEqual(offer.transaction_id, tx)
        self.assertEqual(offer.state, "accepted")

    def test_link_cannot_be_set_on_a_closed_to_closed_transition(self):
        # expired → cancelled is a transition the base validator admits, so only this guard refuses the link.
        offer = self._offer()
        offer.write({"state": "expired"})
        tx = self._transaction_for(offer.name)
        with self.assertRaises(UserError):
            offer.write({"state": "cancelled", "transaction_id": tx.id})
        self.assertFalse(offer.transaction_id)
        self.assertEqual(offer.state, "expired")
