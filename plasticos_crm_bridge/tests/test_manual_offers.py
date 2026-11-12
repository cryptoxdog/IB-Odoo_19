"""Manual buyer selection on a native Opportunity: drafts, email, winner, release — no Gate.

Runs under ``odoo --test-enable`` on the Enterprise fixture clone. Gate
transport and availability are patched to fail the test if anything reaches
them, so every assertion here also proves the manual path never calls Gate.
"""

from __future__ import annotations

import base64
import html
import re
from contextlib import contextmanager
from unittest.mock import patch

from psycopg2.errors import UniqueViolation

from odoo import Command
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_crm_bridge.tests.test_opportunity_approval import _CLASSIFY, _SEND
from odoo.addons.plasticos_offer.tests.test_manual_send import send_offer_email
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged
from odoo.tools import mute_logger

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nopportunity-material-picture")
SUPPLIER_COST = 0.0789


@tagged("post_install", "-at_install", "plasticos", "crm_bridge", "manual_offer")
class TestManualOffers(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.offer", "plasticos.opportunity.material", "plasticos.match.run")
        cls.Lead = cls.env["crm.lead"]
        cls.Offer = cls.env["plasticos.offer"]
        cls.Wizard = cls.env["plasticos.offer.buyer.selection.wizard"]
        cls.supplier = cls._create_partner("Manual Supplier Co", supplier_rank=1, email="ops@supplier.example.com")
        cls.buyer_a = cls._create_partner("Manual Buyer A", customer_rank=1)
        cls.alice = cls._contact(cls.buyer_a, "Alice A", "alice@buyer-a.example.com")
        cls.bob = cls._contact(cls.buyer_a, "Bob A", "bob@buyer-a.example.com")
        cls.buyer_b = cls._create_partner("Manual Buyer B", customer_rank=1)
        cls.carol = cls._contact(cls.buyer_b, "Carol B", "carol@buyer-b.example.com")
        # Same display name as Buyer A, distinct company record: never merged.
        cls.buyer_a_twin = cls._create_partner("Manual Buyer A", customer_rank=1, email="twin@buyer-twin.example")
        cls.polymer = cls._get_or_create_polymer()
        cls.form = cls._get_or_create_form()
        cls.profile = cls.env["plasticos.material.profile"].create(
            {
                "partner_id": cls.supplier.id,
                "polymer_id": cls.polymer.id,
                "form_id": cls.form.id,
                "quantity_per_load_lbs": 42000,
                "loads_per_month": 6,
                "contamination_percent": 1.5,
            }
        )

    @classmethod
    def _contact(cls, company, name, email):
        return cls.env["res.partner"].create({"name": name, "parent_id": company.id, "type": "contact", "email": email})

    @contextmanager
    def _no_gate(self):
        with (
            patch(_CLASSIFY, side_effect=AssertionError("manual offers must not consult Gate")),
            patch(_SEND, side_effect=AssertionError("manual offers must not call Gate")),
        ):
            yield

    def _opportunity(self, **vals):
        base = {
            "name": "Manual Opportunity",
            "type": "opportunity",
            "partner_id": self.supplier.id,
            "material_profile_id": self.profile.id,
        }
        base.update(vals)
        opportunity = self.Lead.create(base)
        material = opportunity.opportunity_material_ids[:1]
        if material:
            material.buy_price_per_lb = SUPPLIER_COST
        return opportunity

    def _generate(self, opportunity, contacts):
        with self._no_gate():
            action = opportunity.action_select_offer_buyers()
            wizard = self.Wizard.with_context(action["context"]).create({"contact_ids": [Command.set(contacts.ids)]})
            result = wizard.action_generate_draft_offers()
        return self.Offer.browse(result["domain"][0][2])

    # ── Entry point ─────────────────────────────────────────

    def test_select_buyers_needs_no_gate_and_no_match(self):
        opportunity = self._opportunity()
        self.assertFalse(opportunity.match_run_ids)
        with self._no_gate():
            action = opportunity.action_select_offer_buyers()
        self.assertEqual(action["res_model"], "plasticos.offer.buyer.selection.wizard")
        self.assertEqual(action["context"]["default_opportunity_id"], opportunity.id)
        self.assertFalse(self.Offer.search([("opportunity_id", "=", opportunity.id)]), "opening creates nothing")

    def test_select_buyers_explains_missing_inputs(self):
        partners_before = self.env["res.partner"].search_count([])
        lead = self.Lead.create({"name": "Plain Lead", "type": "lead", "partner_id": self.supplier.id})
        with self.assertRaisesRegex(UserError, "opportunity"):
            lead.action_select_offer_buyers()
        no_supplier = self.Lead.create({"name": "No Supplier", "type": "opportunity"})
        with self.assertRaisesRegex(UserError, "supplier"):
            no_supplier.action_select_offer_buyers()
        no_material = self.Lead.create({"name": "No Material", "type": "opportunity", "partner_id": self.supplier.id})
        with self.assertRaisesRegex(UserError, "material sheet"):
            no_material.action_select_offer_buyers()
        self.assertEqual(self.env["res.partner"].search_count([]), partners_before, "no partner is fabricated")

    def test_closed_opportunity_cannot_start_outreach(self):
        opportunity = self._opportunity()
        opportunity._plasticos_mark_won()
        with self.assertRaisesRegex(UserError, "closed"):
            opportunity.action_select_offer_buyers()
        lost = self._opportunity(name="Lost Opportunity")
        lost.action_archive()
        with self.assertRaisesRegex(UserError, "closed"):
            lost.action_select_offer_buyers()

    def test_contact_picker_domain_is_valid_and_hides_the_supplier(self):
        from odoo.tools.safe_eval import safe_eval  # noqa: PLC0415

        arch = self.env.ref("plasticos_crm_bridge.view_offer_buyer_selection_wizard_form").arch
        domain_text = re.search(r'name="contact_ids"[^>]*domain="([^"]+)"', arch, re.S).group(1)
        domain = safe_eval(html.unescape(domain_text), {"supplier_partner_id": self.supplier.id})
        supplier_contact = self._contact(self.supplier, "Supplier Desk Picker", "picker@supplier.example.com")
        found = self.env["res.partner"].search(domain)
        self.assertIn(self.alice, found)
        self.assertNotIn(self.supplier, found)
        self.assertNotIn(supplier_contact, found)

    def test_cancelled_selection_creates_nothing(self):
        opportunity = self._opportunity()
        action = opportunity.action_select_offer_buyers()
        wizard = self.Wizard.with_context(action["context"]).create({"contact_ids": [Command.set(self.alice.ids)]})
        wizard.unlink()
        self.assertFalse(self.Offer.search([("opportunity_id", "=", opportunity.id)]))

    # ── Grouping and validation ─────────────────────────────

    def test_contacts_group_into_one_draft_per_buyer_company(self):
        opportunity = self._opportunity()
        offers = self._generate(opportunity, self.alice | self.bob | self.carol | self.alice)
        self.assertEqual(len(offers), 2)
        offer_a = offers.filtered(lambda offer: offer.buyer_id == self.buyer_a)
        offer_b = offers.filtered(lambda offer: offer.buyer_id == self.buyer_b)
        self.assertEqual(offer_a.recipient_partner_ids, self.alice | self.bob)
        self.assertEqual(offer_b.recipient_partner_ids, self.carol)
        self.assertEqual(opportunity.offer_count, 2)

    def test_same_name_companies_are_not_merged(self):
        opportunity = self._opportunity()
        offers = self._generate(opportunity, self.alice | self.buyer_a_twin)
        self.assertEqual(set(offers.mapped("buyer_id").ids), {self.buyer_a.id, self.buyer_a_twin.id})
        twin_offer = offers.filtered(lambda offer: offer.buyer_id == self.buyer_a_twin)
        self.assertEqual(twin_offer.recipient_partner_ids, self.buyer_a_twin, "a company with an email is a recipient")

    def test_company_without_a_deliverable_contact_is_refused(self):
        opportunity = self._opportunity()
        silent = self._create_partner("Silent Buyer Co", customer_rank=1)
        with self.assertRaisesRegex(UserError, "Silent Buyer Co"):
            self._generate(opportunity, silent)
        self.assertFalse(self.Offer.search([("opportunity_id", "=", opportunity.id)]))

    def test_supplier_cannot_be_selected_as_buyer(self):
        opportunity = self._opportunity()
        supplier_contact = self._contact(self.supplier, "Supplier Desk", "desk@supplier.example.com")
        with self.assertRaisesRegex(UserError, "supplier"):
            self._generate(opportunity, supplier_contact)

    def test_archived_contact_is_refused(self):
        opportunity = self._opportunity()
        gone = self._contact(self.buyer_b, "Gone B", "gone@buyer-b.example.com")
        gone.action_archive()
        with self.assertRaisesRegex(UserError, "Archived"):
            self._generate(opportunity, gone)

    def test_mixed_active_and_archived_selection_is_refused(self):
        """An archived contact is refused, never silently dropped from a mixed selection."""
        opportunity = self._opportunity()
        gone = self._contact(self.buyer_b, "Gone Mixed B", "gone-mixed@buyer-b.example.com")
        gone.action_archive()
        with self.assertRaisesRegex(UserError, "Archived contacts cannot receive offers: Gone Mixed B"):
            self._generate(opportunity, self.alice | gone)
        self.assertFalse(self.Offer.search([("opportunity_id", "=", opportunity.id)]))

    def test_contact_of_another_company_is_refused(self):
        other_company = self.env["res.company"].create({"name": "Other Legal Company"})
        hidden = self.env["res.partner"].create(
            {"name": "Hidden Buyer", "is_company": True, "email": "hidden@example.com", "company_id": other_company.id}
        )
        rep = self.env["res.users"].create(
            {
                "name": "Manual Offer Rep",
                "login": "manual_offer_rep",
                "company_id": self.env.company.id,
                "company_ids": [Command.set(self.env.company.ids)],
                "group_ids": [Command.link(self.env.ref("sales_team.group_sale_salesman_all_leads").id)],
            }
        )
        opportunity = self._opportunity()
        # AccessError subclasses UserError in Odoo 19; the regex pins the
        # company refusal, not a generic access error.
        with self.assertRaisesRegex(UserError, "belong to a company you are not working in") as caught:
            wizard = self.Wizard.with_user(rep).create(
                {"opportunity_id": opportunity.id, "contact_ids": [Command.set(hidden.ids)]}
            )
            wizard.action_generate_draft_offers()
        self.assertNotIsInstance(caught.exception, AccessError)
        self.assertNotIn("Hidden Buyer", str(caught.exception), "a hidden contact is never named")
        self.assertFalse(self.Offer.search([("buyer_id", "=", hidden.id)]))

        # Mixed with a contact the rep may offer to: refused, not silently reduced.
        with self.assertRaisesRegex(UserError, "belong to a company you are not working in"):
            wizard = self.Wizard.with_user(rep).create(
                {"opportunity_id": opportunity.id, "contact_ids": [Command.set((self.alice | hidden).ids)]}
            )
            wizard.action_generate_draft_offers()
        self.assertFalse(self.Offer.search([("opportunity_id", "=", opportunity.id)]))

    # ── Draft content ───────────────────────────────────────

    def test_draft_is_built_from_the_opportunity_material_only(self):
        opportunity = self._opportunity()
        material = opportunity.opportunity_material_ids
        color = self.env["plasticos.material.color"].search([], limit=1)
        if color:
            material.color_id = color
        picture = self.env["ir.attachment"].create(
            {
                "name": "bale.png",
                "datas": PNG,
                "mimetype": "image/png",
                "res_model": "plasticos.opportunity.material",
                "res_id": material.id,
            }
        )
        material.image_attachment_ids = [Command.link(picture.id)]
        offer = self._generate(opportunity, self.alice)

        self.assertFalse(offer.match_result_id)
        self.assertEqual(offer.opportunity_id, opportunity)
        self.assertEqual(offer.material_source_id, material)
        self.assertEqual(offer.supplier_id, self.supplier)
        self.assertEqual(offer.buyer_id, self.buyer_a)
        self.assertEqual(offer.state, "draft")
        self.assertEqual(offer.quantity_lbs, 42000)
        self.assertEqual(offer.loads, 1, "monthly frequency is not a committed load count")
        self.assertEqual(offer.price_per_lb, 0.0, "the supplier cost is never the buyer price")
        self.assertNotIn(str(SUPPLIER_COST), offer.material_description)
        self.assertNotIn("0.08", offer.material_description)
        self.assertIn(self.polymer.name, offer.material_description)
        self.assertIn("Contamination: 1.5%", offer.material_description)
        if color:
            self.assertIn(color.display_name, offer.material_description, "the opportunity copy, not the profile")
        self.assertEqual(offer.material_image_ids, picture, "pictures are referenced, not copied")
        self.assertFalse(
            self.env["ir.attachment"].search_count([("res_model", "=", "plasticos.offer"), ("res_id", "=", offer.id)])
        )
        self.assertFalse(self.env["sale.order"].search_count([("opportunity_id", "=", opportunity.id)]))
        self.assertFalse(offer.sent_message_id, "generation sends nothing")
        self.assertFalse(opportunity.stage_id.is_won)

    # ── Idempotency ─────────────────────────────────────────

    def test_repeat_generation_reuses_the_draft_and_keeps_history(self):
        opportunity = self._opportunity()
        first = self._generate(opportunity, self.alice)
        again = self._generate(opportunity, self.alice | self.bob)
        self.assertEqual(again, first, "the active draft is reused")
        self.assertEqual(first.recipient_partner_ids, self.alice | self.bob)

        first.write({"price_per_lb": 0.21})
        send_offer_email(first)
        sent_terms = (first.price_per_lb, first.recipient_partner_ids.ids, first.material_description)
        proposal_two = self._generate(opportunity, self.alice)
        self.assertNotEqual(proposal_two, first, "a sent offer is history; a new proposal is a new draft")
        self.assertEqual(proposal_two.state, "draft")
        self.assertEqual((first.price_per_lb, first.recipient_partner_ids.ids, first.material_description), sent_terms)

    def test_database_refuses_a_second_active_manual_draft(self):
        opportunity = self._opportunity()
        offer = self._generate(opportunity, self.alice)
        with mute_logger("odoo.sql_db"), self.assertRaises(UniqueViolation):
            self.Offer.create(
                {
                    "supplier_id": self.supplier.id,
                    "buyer_id": self.buyer_a.id,
                    "opportunity_id": opportunity.id,
                    "material_source_id": offer.material_source_id.id,
                }
            )
            self.Offer.flush_model()

    def test_material_of_another_opportunity_is_refused(self):
        opportunity = self._opportunity()
        other = self._opportunity(name="Other Opportunity")
        with self.assertRaisesRegex(ValidationError, "material must belong"):
            self.Offer.create(
                {
                    "supplier_id": self.supplier.id,
                    "buyer_id": self.buyer_b.id,
                    "opportunity_id": opportunity.id,
                    "material_source_id": other.opportunity_material_ids.id,
                }
            )

    # ── Email, winner and release ───────────────────────────

    def test_manual_offer_email_goes_only_to_its_buyer(self):
        opportunity = self._opportunity()
        offers = self._generate(opportunity, self.alice | self.carol)
        offer_a = offers.filtered(lambda offer: offer.buyer_id == self.buyer_a)
        offer_a.write({"price_per_lb": 0.21})
        send_offer_email(offer_a)
        message = offer_a.sent_message_id
        self.assertEqual(message.partner_ids, self.alice)
        self.assertNotIn(self.carol, message.notification_ids.mapped("res_partner_id"))
        self.assertNotIn(str(SUPPLIER_COST), str(message.body))
        self.assertFalse(opportunity.stage_id.is_won, "sending selects no winner")
        self.assertTrue(offer_a.material_spec_key)

    def test_manual_offer_reaches_one_winner_and_release(self):
        opportunity = self._opportunity()
        offers = self._generate(opportunity, self.alice | self.carol)
        offers.write({"price_per_lb": 0.21})
        send_offer_email(offers)
        winner = offers.filtered(lambda offer: offer.buyer_id == self.buyer_a)
        loser = offers - winner
        with self._no_gate():
            winner.action_accept()
        self.assertTrue(opportunity.stage_id.is_won)
        with self.assertRaisesRegex(UserError, "commercial winner"):
            loser.action_accept()
        self.assertEqual(loser.state, "sent")
        self.assertFalse(self.env["sale.order"].search_count([("opportunity_id", "=", opportunity.id)]))

        final_supplier_price = 0.0815
        opportunity.offer_buy_price = final_supplier_price
        self.assertEqual(opportunity.opportunity_material_ids.buy_price_per_lb, final_supplier_price)
        plant = self.env["res.partner"].create(
            {"name": "Buyer A Plant", "is_company": True, "parent_id": self.buyer_a.id, "customer_rank": 1}
        )
        opportunity.write(
            {
                "release_buyer_company_id": self.buyer_a.id,
                "release_buyer_facility_id": plant.id,
                "release_buyer_price": 0.21,
            }
        )
        opportunity.action_submit_release()
        self.assertEqual(opportunity.release_purchase_order_id.order_line.price_unit, final_supplier_price)
        self.assertEqual(opportunity.release_sale_order_id.order_line.price_unit, winner.price_per_lb)
        self.assertEqual(opportunity.release_sale_order_id.partner_id, plant)
        self.assertTrue(opportunity.release_sale_order_id)
        self.assertEqual(opportunity.release_sale_order_id.order_line.product_uom_qty, winner.quantity_lbs)
        opportunity.action_submit_release()
        self.assertEqual(self.env["sale.order"].search_count([("opportunity_id", "=", opportunity.id)]), 1)

    def test_release_stops_when_the_material_drifted_after_send(self):
        opportunity = self._opportunity()
        offer = self._generate(opportunity, self.alice)
        offer.write({"price_per_lb": 0.21})
        send_offer_email(offer)
        offer.action_accept()
        other_form = self._get_or_create_form("flake_manual", "Flake Manual")
        opportunity.opportunity_material_ids.form_id = other_form
        opportunity.write(
            {
                "release_buyer_company_id": self.buyer_a.id,
                "release_buyer_facility_id": self.buyer_a.id,
                "release_buyer_price": 0.21,
            }
        )
        with self.assertRaisesRegex(UserError, "material changed"):
            opportunity.action_submit_release()
        self.assertFalse(opportunity.release_purchase_order_id)
        self.assertFalse(opportunity.release_sale_order_id)

    # ── Release sells exactly what the buyer accepted (R1) ──

    def _accepted_manual_offer(self):
        opportunity = self._opportunity()
        offer = self._generate(opportunity, self.alice)
        offer.write({"price_per_lb": 0.21})
        send_offer_email(offer)
        offer.action_accept()
        return opportunity, offer

    def _assert_release_refused(self, opportunity, offer, vals, pattern):
        opportunity.write(vals)
        with self.assertRaisesRegex(UserError, pattern):
            opportunity.action_submit_release()
        self.assertFalse(opportunity.release_purchase_order_id)
        self.assertFalse(opportunity.release_sale_order_id)
        self.assertFalse(opportunity.release_transaction_id)
        self.assertFalse(self.env["sale.order"].search_count([("opportunity_id", "=", opportunity.id)]))
        self.assertFalse(self.env["purchase.order"].search_count([("origin", "=", offer.name)]))

    def test_accepted_offer_email_and_material_evidence_cannot_be_cleared(self):
        opportunity, offer = self._accepted_manual_offer()
        message, sent_date, spec_key = offer.sent_message_id, offer.sent_date, offer.material_spec_key
        self.assertTrue(message and sent_date and spec_key)
        attempts = (
            {"state": "accepted", "sent_message_id": False, "material_spec_key": False},
            {"state": "accepted", "sent_message_id": False},
            {"state": "accepted", "material_spec_key": False},
            {"state": "accepted", "sent_date": False},
            {"sent_message_id": False},
            {"material_spec_key": "forged"},
        )
        for vals in attempts:
            with self.assertRaises(UserError, msg=f"refused: {vals}"):
                offer.write(vals)
        with self.assertRaisesRegex(UserError, "Closed offers are immutable"):
            offer.write({"state": "accepted", "price_per_lb": 0.5})
        self.assertEqual(
            (offer.state, offer.sent_message_id, offer.sent_date, offer.material_spec_key),
            ("accepted", message, sent_date, spec_key),
        )
        # Release still compares the frozen specification and the transaction back-link still lands.
        opportunity.write(
            {
                "release_buyer_company_id": self.buyer_a.id,
                "release_buyer_facility_id": self.buyer_a.id,
                "release_buyer_price": 0.21,
            }
        )
        opportunity.action_submit_release()
        offer._plasticos_link_transaction(opportunity.release_transaction_id)
        self.assertEqual(offer.transaction_id, opportunity.release_transaction_id)

    def test_release_refuses_a_buyer_other_than_the_accepted_one(self):
        opportunity, offer = self._accepted_manual_offer()
        self._assert_release_refused(
            opportunity,
            offer,
            {
                "release_buyer_company_id": self.buyer_b.id,
                "release_buyer_facility_id": self.buyer_b.id,
                "release_buyer_price": 0.21,
            },
            "was accepted by",
        )

    def test_release_refuses_a_facility_outside_the_accepted_buyer(self):
        opportunity, offer = self._accepted_manual_offer()
        self._assert_release_refused(
            opportunity,
            offer,
            {
                "release_buyer_company_id": self.buyer_a.id,
                "release_buyer_facility_id": self.buyer_b.id,
                "release_buyer_price": 0.21,
            },
            "does not belong to",
        )

    def test_release_refuses_a_price_other_than_the_accepted_one(self):
        opportunity, offer = self._accepted_manual_offer()
        self._assert_release_refused(
            opportunity,
            offer,
            {
                "release_buyer_company_id": self.buyer_a.id,
                "release_buyer_facility_id": self.buyer_a.id,
                "release_buyer_price": 0.2101,
            },
            "differs from",
        )

    # ── Communicated history is kept (R3) ───────────────────

    def test_emailed_manual_offer_cannot_be_rewritten_through_reset(self):
        opportunity = self._opportunity()
        first = self._generate(opportunity, self.alice)
        first.write({"price_per_lb": 0.21})
        send_offer_email(first)
        message = first.sent_message_id
        sent = (first.price_per_lb, first.recipient_partner_ids, first.material_description, message.attachment_ids)
        first.action_reject()
        with self.assertRaisesRegex(UserError, "was emailed to the buyer"):
            first.action_reset_to_draft()
        with self.assertRaisesRegex(UserError, "was emailed to the buyer"):
            first.write({"state": "draft"})
        self.assertEqual(first.state, "rejected")
        self.assertEqual(first.sent_message_id, message)
        self.assertEqual(
            (first.price_per_lb, first.recipient_partner_ids, first.material_description, message.attachment_ids),
            sent,
        )
        revised = self._generate(opportunity, self.alice)
        self.assertNotEqual(revised, first, "a revised proposal is a new offer")
        self.assertEqual(revised.state, "draft")

    def test_unsent_manual_offer_reset_cannot_duplicate_an_active_draft(self):
        opportunity = self._opportunity()
        first = self._generate(opportunity, self.alice)
        first.action_cancel()
        self._generate(opportunity, self.alice)
        with self.assertRaisesRegex(UserError, "already has a draft offer"):
            first.action_reset_to_draft()
