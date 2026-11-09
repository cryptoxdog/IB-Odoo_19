"""Admin submit creates one draft purchase order, one draft sale order, and one transaction."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

from odoo import Command
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_crm_bridge.tests.test_opportunity_approval import (
    _CLASSIFY,
    _ENABLED,
    _SEND,
    _available_verdict,
    _eligible,
    _fake_gate_result,
)
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "plasticos", "crm_bridge", "opportunity")
class TestOpportunityRelease(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior_gate_url = os.environ.get("GATE_URL")
        super().setUpClass()
        os.environ["GATE_URL"] = "https://gate.example.internal"
        cls.registry_enter_test_mode_cls()
        cls.supplier = cls._create_partner("Release Supplier Co", supplier_rank=1)
        cls.buyer = cls._create_partner("Release Buyer Co", customer_rank=1)
        cls.facility = cls.env["res.partner"].create(
            {
                "name": "Release Buyer Facility",
                "is_company": True,
                "parent_id": cls.buyer.id,
                "customer_rank": 1,
            }
        )
        cls.polymer = cls._get_or_create_polymer()
        cls.form = cls._get_or_create_form()
        cls.profile = cls.env["plasticos.material.profile"].create(
            {
                "partner_id": cls.supplier.id,
                "polymer_id": cls.polymer.id,
                "form_id": cls.form.id,
                "quantity_per_load_lbs": 40000,
            }
        )

    @classmethod
    def tearDownClass(cls):
        if cls._prior_gate_url is None:
            os.environ.pop("GATE_URL", None)
        else:
            os.environ["GATE_URL"] = cls._prior_gate_url
        super().tearDownClass()

    def _accepted_offer(self):
        opportunity = self.env["crm.lead"].create(
            {
                "name": "Release Opportunity",
                "type": "opportunity",
                "partner_id": self.supplier.id,
                "material_profile_id": self.profile.id,
            }
        )
        holder = SimpleNamespace(savepoint=None)

        def fake_commit(lead):
            holder.savepoint = self.env.cr.savepoint(flush=True)

        def fake_send(env, *, payload, correlation_id=None, idempotency_key=None):
            return _fake_gate_result([_eligible(self.buyer)])

        try:
            with (
                patch.object(type(opportunity), "_plasticos_ensure_lot_durable", fake_commit),
                patch(_CLASSIFY, return_value=_available_verdict()),
                patch(_ENABLED, return_value=True),
                patch(_SEND, side_effect=fake_send),
            ):
                opportunity.action_match_opportunity()
        finally:
            if holder.savepoint is not None:
                holder.savepoint.close(rollback=False)
        run = self.env["plasticos.match.run"].search(
            [("opportunity_id", "=", opportunity.id)], order="id desc", limit=1
        )
        run.result_ids.action_accept()
        opportunity.action_create_offers_from_results()
        offer = self.env["plasticos.offer"].search(
            [("match_result_id.match_run_id.opportunity_id", "=", opportunity.id)],
            limit=1,
        )
        offer.write({"price_per_lb": 0.12, "quantity_lbs": 40000})
        offer.action_send()
        offer.action_accept()
        return opportunity, offer

    def test_submit_creates_one_draft_pair_and_confirm_does_not_compile_another(self):
        opportunity, offer = self._accepted_offer()
        self.assertTrue(opportunity.stage_id.is_won)
        self.assertFalse(self.env["sale.order"].search([("opportunity_id", "=", opportunity.id)]))
        self.assertFalse(self.env["purchase.order"].search([("origin", "=", offer.name)]))

        opportunity.write(
            {
                "release_buyer_company_id": self.buyer.id,
                "release_buyer_facility_id": self.facility.id,
                "release_buyer_price": 0.20,
            }
        )
        opportunity.action_submit_release()
        purchase = opportunity.release_purchase_order_id
        sale = opportunity.release_sale_order_id
        transaction = opportunity.release_transaction_id
        self.assertEqual(purchase.state, "draft")
        self.assertEqual(purchase.partner_id, self.supplier)
        self.assertEqual(purchase.order_line.price_unit, 0.12)
        self.assertEqual(purchase.order_line.product_qty, 40000)
        self.assertFalse(purchase.order_line.material_profile_id)
        self.assertEqual(purchase.order_line.form_id, self.form)
        self.assertEqual(sale.state, "draft")
        self.assertEqual(sale.partner_id, self.facility)
        self.assertEqual(sale.opportunity_id, opportunity)
        self.assertEqual(sale.order_line.price_unit, 0.20)
        self.assertFalse(sale.order_line.material_profile_id)
        self.assertEqual(sale.order_line.form_id, self.form)
        self.assertEqual(transaction.state, "draft")
        self.assertEqual(sale.transaction_id, transaction)
        self.assertEqual(transaction.sale_order_id, sale)
        self.assertIn(purchase, transaction.purchase_order_ids)

        opportunity.action_submit_release()
        self.assertEqual(opportunity.release_purchase_order_id, purchase)
        self.assertEqual(opportunity.release_sale_order_id, sale)
        self.assertEqual(opportunity.release_transaction_id, transaction)

        sale.action_confirm()
        self.assertEqual(self.env["plasticos.transaction"].search_count([("sale_order_id", "=", sale.id)]), 1)
        self.assertEqual(sale.transaction_id, transaction)

    def test_submit_refuses_a_partial_release_instead_of_duplicating_it(self):
        opportunity, offer = self._accepted_offer()
        opportunity.write(
            {
                "release_buyer_company_id": self.buyer.id,
                "release_buyer_facility_id": self.facility.id,
                "release_buyer_price": 0.20,
            }
        )
        opportunity.action_submit_release()
        purchase = opportunity.release_purchase_order_id
        opportunity.write({"release_sale_order_id": False, "release_transaction_id": False})

        with self.assertRaises(UserError):
            opportunity.action_submit_release()
        self.assertEqual(opportunity.release_purchase_order_id, purchase)
        self.assertEqual(self.env["purchase.order"].search_count([("origin", "=", offer.name)]), 1)

    def test_submit_requires_an_operations_manager(self):
        opportunity, _offer = self._accepted_offer()
        opportunity.write(
            {
                "release_buyer_company_id": self.buyer.id,
                "release_buyer_facility_id": self.facility.id,
                "release_buyer_price": 0.20,
            }
        )
        sales_user = self.env["res.users"].create(
            {
                "name": "Release Sales Rep",
                "login": "release_sales_rep",
                "group_ids": [Command.link(self.env.ref("sales_team.group_sale_salesman").id)],
            }
        )

        with self.assertRaises(AccessError):
            opportunity.with_user(sales_user).action_submit_release()
        self.assertFalse(opportunity.release_purchase_order_id)
