"""The lead dock rule follows the side its partner plays (ADR-135 §3)."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDockRuleSide(TransactionCase):
    def _lead(self, partner, term="fcfs"):
        lead = self.env["crm.lead"].create(
            {"name": "Dock Side Pursuit", "type": "opportunity", "partner_id": partner.id}
        )
        lead.delivery_term = term
        return lead

    def test_supplier_and_both_ranks_are_pickup_and_a_buyer_is_delivery(self):
        supplier = self.env["res.partner"].create({"name": "Side Supplier Co", "is_company": True, "supplier_rank": 1})
        buyer = self.env["res.partner"].create({"name": "Side Buyer Co", "is_company": True, "customer_rank": 1})
        both = self.env["res.partner"].create(
            {"name": "Side Both Co", "is_company": True, "supplier_rank": 1, "customer_rank": 1}
        )
        neither = self.env["res.partner"].create({"name": "Side Neither Co", "is_company": True})
        self.assertEqual(self._lead(supplier)._plasticos_delivery_term_side(), "pickup")
        self.assertEqual(self._lead(both)._plasticos_delivery_term_side(), "pickup")
        self.assertEqual(self._lead(buyer)._plasticos_delivery_term_side(), "delivery")
        self.assertEqual(self._lead(neither)._plasticos_delivery_term_side(), "delivery")
        empty = self.env["crm.lead"].create({"name": "Dock Side Empty", "type": "opportunity"})
        self.assertEqual(empty._plasticos_delivery_term_side(), "delivery")
