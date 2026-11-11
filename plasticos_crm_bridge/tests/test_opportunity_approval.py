"""Partners-first native Opportunity matching: lot, Gate run, results, offers, sale order.

Runs against the real ORM under ``odoo --test-enable`` on the Enterprise
fixture clone. Gate transport is patched exactly as the matching suite does;
no external provider is called and no local scoring exists to fall back on.

Proves (plan V1–V4 properties, CRM Bridge owns the lineage):
  * manual and HOT routes converge on ``action_match_opportunity`` with a
    verified Partner and Material Profile, no synthetic intake, no facility;
  * two commands on one partner and profile are two independent lots;
  * the Gate request is built from the frozen lot and omits facility evidence
    when none is linked; a later profile edit does not rewrite the lot;
  * reviewed results create idempotent unsent drafts with typed lineage;
  * terms freeze once sent; exactly one commercial winner per opportunity;
  * acceptance marks the native Won stage and creates no purchase order,
    sale order, or transaction. Admin submit creates the drafts.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

from lxml import etree

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_crm_bridge.models.opportunity_approval import APPROVAL_MINT_CONTEXT
from odoo.addons.plasticos_gate.services.gate_config import (
    GateAvailability,
    GateAvailabilityVerdict,
    GateCapability,
)
from odoo.addons.plasticos_offer.tests.test_manual_send import send_offer_email
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged

_SEND = "odoo.addons.plasticos_gate.services.gate_client.send_match_action"
_ENABLED = "odoo.addons.plasticos_gate.services.gate_config.gate_matching_enabled"
_CLASSIFY = "odoo.addons.plasticos_gate.services.gate_config.classify_gate_availability"


def _available_verdict() -> GateAvailabilityVerdict:
    return GateAvailabilityVerdict(
        status=GateAvailability.AVAILABLE,
        available=True,
        capability=GateCapability.MATCHING,
        reasons=[],
        gate_url_configured=True,
    )


def _fake_gate_result(candidates, packet_id="pkt-opp-1", correlation_id="corr-opp-1"):
    packet = SimpleNamespace(header=SimpleNamespace(packet_id=packet_id, correlation_id=correlation_id))
    payload = {
        "status": "ok",
        "direction": "supply_opportunity_to_buyer_facility",
        "top_n": 20,
        "candidates": list(candidates),
        "query_id": "query-opp-1",
        "contract_version": "contract-1",
        "domain_spec_version": "domain-1",
        "model_version": "model-1",
    }
    return {"packet": packet, "payload": payload}


def _eligible(buyer, score=0.85, rank=1):
    return {
        "entity_ref": f"res.partner:{buyer.id}",
        "eligible": True,
        "score": score,
        "score_scale": "0_to_1",
        "rank": rank,
        "explanation": "Eligible Gate candidate",
        "failed_gates": [],
    }


@tagged("post_install", "-at_install", "plasticos", "crm_bridge", "opportunity")
class TestOpportunityApproval(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior_gate_url = os.environ.get("GATE_URL")
        super().setUpClass()
        cls._skip_if_model_missing(
            "plasticos.opportunity.approval",
            "plasticos.match.orchestrator",
            "plasticos.match.run",
            "plasticos.offer",
            "sale.order",
        )
        os.environ["GATE_URL"] = "https://gate.example.internal"
        cls.Lead = cls.env["crm.lead"]
        cls.Approval = cls.env["plasticos.opportunity.approval"]
        cls.Run = cls.env["plasticos.match.run"]
        cls.Result = cls.env["plasticos.match.result"]
        cls.Offer = cls.env["plasticos.offer"]
        cls.Intake = cls.env["plasticos.intake"]
        cls.Facility = cls.env["plasticos.facility.profile"]
        # The orchestrator's durable failure write opens registry.cursor(); in
        # test mode that is a TestCursor over this test's connection.
        cls.registry_enter_test_mode_cls()
        cls.supplier = cls._create_partner("Opportunity Supplier Co", supplier_rank=1)
        cls.buyer_a = cls._create_partner("Opportunity Buyer A", customer_rank=1)
        cls.buyer_b = cls._create_partner("Opportunity Buyer B", customer_rank=1)
        cls.polymer = cls._get_or_create_polymer()
        cls.form = cls._get_or_create_form()
        cls.profile = cls.env["plasticos.material.profile"].create(
            {
                "partner_id": cls.supplier.id,
                "polymer_id": cls.polymer.id,
                "form_id": cls.form.id,
                "quantity_per_load_lbs": 40000,
                "contamination_percent": 2.5,
            }
        )

    @classmethod
    def tearDownClass(cls):
        if cls._prior_gate_url is None:
            os.environ.pop("GATE_URL", None)
        else:
            os.environ["GATE_URL"] = cls._prior_gate_url
        super().tearDownClass()

    # ── helpers ───────────────────────────────────────────────

    def _opportunity(self, **extra):
        vals = {
            "name": "Manual Opportunity",
            "type": "opportunity",
            "partner_id": self.supplier.id,
            "material_profile_id": self.profile.id,
        }
        vals.update(extra)
        return self.Lead.create(vals)

    def _lot_commit_stand_in(self, holder):
        """Stand in for the lot's durability commit with a savepoint taken at that exact point.

        ``TransactionCase`` never lets a test commit, so the command's
        ``_plasticos_ensure_lot_durable`` is replaced by a savepoint; a later
        ambient rollback routed to that savepoint discards exactly what a real
        rollback after the commit would, and keeps exactly what the commit kept.
        """

        def fake_commit(lead):
            holder.savepoint = self.env.cr.savepoint(flush=True)

        return patch.object(type(self.Lead), "_plasticos_ensure_lot_durable", fake_commit)

    def _match(self, opportunity, candidates=None):
        """Run the one Opportunity matching command against a patched Gate; return (run, sent payload)."""
        sent = {}
        holder = SimpleNamespace(savepoint=None)

        def fake_send(env, *, payload, correlation_id=None, idempotency_key=None):
            sent["payload"] = payload
            sent["idempotency_key"] = idempotency_key
            return _fake_gate_result(candidates if candidates is not None else [_eligible(self.buyer_a)])

        try:
            with (
                self._lot_commit_stand_in(holder),
                patch(_CLASSIFY, return_value=_available_verdict()),
                patch(_ENABLED, return_value=True),
                patch(_SEND, side_effect=fake_send),
            ):
                opportunity.action_match_opportunity()
        finally:
            if holder.savepoint is not None:
                holder.savepoint.close(rollback=False)
        run = self.Run.search([("opportunity_id", "=", opportunity.id)], order="id desc", limit=1)
        return run, sent

    # ── V1: manual and HOT routes, verified partner + profile, independent lots ──

    def test_manual_route_mints_lot_and_runs_gate_without_intake_or_facility(self):
        intakes_before = self.Intake.search_count([])
        facilities_before = self.Facility.search_count([])
        opportunity = self._opportunity()

        run, sent = self._match(opportunity)

        self.assertEqual(run.state, "ok")
        self.assertEqual(run.opportunity_id, opportunity)
        self.assertEqual(run.supplier_partner_id, self.supplier)
        self.assertFalse(run.intake_id, "a manual lot run has no intake")
        approval = run.approval_id
        self.assertTrue(approval)
        self.assertEqual(approval.source, "manual")
        self.assertEqual(approval.partner_id, self.supplier)
        self.assertEqual(approval.material_profile_id, self.profile)
        self.assertFalse(approval.facility_profile_id)
        self.assertFalse(approval.source_intake_id)
        self.assertEqual(self.Intake.search_count([]), intakes_before, "no synthetic intake")
        self.assertEqual(self.Facility.search_count([]), facilities_before, "no synthetic facility")

        query = sent["payload"]["query"]
        self.assertEqual(sent["payload"]["match_direction"], "supply_opportunity_to_buyer_facility")
        self.assertEqual(query["supplier_partner_id"], self.supplier.id)
        self.assertEqual(query["quantity_per_load_lbs"], 40000)
        self.assertNotIn("facility_profile_id", query, "absent facility evidence is omitted, not fabricated")
        self.assertNotIn("facility_partner_id", query)
        self.assertNotIn("intake_id", query)
        self.assertEqual(sent["idempotency_key"], run.operation_id)
        self.assertEqual(run.match_count, 1)
        result = run.result_ids
        self.assertEqual(len(result), 1)
        self.assertFalse(result.intake_id)
        self.assertEqual(result.buyer_partner_id, self.buyer_a)
        self.assertEqual(result.score, 85.0)

    def test_two_commands_on_one_partner_and_profile_are_two_lots(self):
        opportunity = self._opportunity()
        run_one, _sent = self._match(opportunity)
        run_two, _sent = self._match(opportunity)
        self.assertNotEqual(run_one, run_two)
        self.assertNotEqual(run_one.approval_id, run_two.approval_id)
        self.assertEqual(len(opportunity.approval_ids), 2)
        self.assertEqual(run_one.approval_id.snapshot_digest, run_two.approval_id.snapshot_digest)

    def test_facility_evidence_sent_only_when_linked(self):
        facility = self.Facility.create({"partner_id": self.supplier.id})
        opportunity = self._opportunity(facility_profile_id=facility.id)
        run, sent = self._match(opportunity)
        self.assertEqual(run.approval_id.facility_profile_id, facility)
        self.assertEqual(sent["payload"]["query"]["facility_profile_id"], facility.id)
        self.assertEqual(sent["payload"]["query"]["facility_partner_id"], self.supplier.id)

    def test_hot_route_keeps_source_intake_as_optional_evidence(self):
        intake = self._create_intake(partner=self.supplier, polymer=self.polymer, form=self.form)
        intake.material_profile_id = self.profile
        opportunity = self._opportunity(name="HOT Opportunity", source_intake_id=intake.id)
        intakes_before = self.Intake.search_count([])

        run, sent = self._match(opportunity)

        self.assertEqual(run.intake_id, intake)
        self.assertEqual(run.approval_id.source_intake_id, intake)
        self.assertEqual(sent["payload"]["query"]["intake_id"], intake.id)
        self.assertEqual(self.Intake.search_count([]), intakes_before)
        self.assertEqual(run.result_ids.intake_id, intake)

    def test_command_requires_verified_partner_and_profile_and_creates_neither(self):
        partners_before = self.env["res.partner"].search_count([])
        no_partner = self.Lead.create({"name": "Unverified", "type": "opportunity", "partner_name": "Ghost Co"})
        with self.assertRaisesRegex(UserError, "verified Partner"):
            no_partner.action_match_opportunity()
        self.assertEqual(self.env["res.partner"].search_count([]), partners_before)
        no_profile = self.Lead.create({"name": "No Profile", "type": "opportunity", "partner_id": self.supplier.id})
        with self.assertRaisesRegex(UserError, "Material Profile"):
            no_profile.action_match_opportunity()
        self.assertFalse(self.Approval.search([("opportunity_id", "in", (no_partner | no_profile).ids)]))

    def test_foreign_profile_is_refused(self):
        other = self._create_partner("Other Supplier", supplier_rank=1)
        foreign = self.env["plasticos.material.profile"].create(
            {"partner_id": other.id, "polymer_id": self.polymer.id, "form_id": self.form.id}
        )
        opportunity = self._opportunity(material_profile_id=foreign.id)
        with self.assertRaises(ValidationError):
            opportunity.action_approve_lot()
        self.assertFalse(opportunity.approval_ids)

    # ── Lot immutability ──────────────────────────────────────

    def test_lot_is_server_minted_and_immutable(self):
        opportunity = self._opportunity()
        with self.assertRaises(AccessError):
            self.Approval.create(
                {
                    "opportunity_id": opportunity.id,
                    "partner_id": self.supplier.id,
                    "material_profile_id": self.profile.id,
                    "source": "manual",
                }
            )
        approval = opportunity.action_approve_lot()
        self.assertEqual(approval.approved_by, self.env.user)
        digest = approval.snapshot_digest
        self.assertTrue(digest)
        with self.assertRaises(AccessError):
            approval.write({"source": "hot"})
        with self.assertRaises(AccessError):
            approval.with_context(**{APPROVAL_MINT_CONTEXT: True}).write({"snapshot": {}})
        with self.assertRaises(AccessError):
            approval.unlink()
        # A later profile edit does not rewrite the approved lot.
        self.profile.contamination_percent = 9.0
        self.env.invalidate_all()
        self.assertEqual(approval.snapshot["contamination_pct"], 2.5)
        self.assertEqual(approval.snapshot_digest, digest)

    # ── Silent evidence: lots are recorded by matching, never shown or asked for ──

    def test_ordinary_opportunity_edit_mints_no_lot(self):
        opportunity = self._opportunity()
        opportunity.write({"name": "Renamed Opportunity", "description": "Seller confirmed the weight."})
        self.assertFalse(opportunity.approval_ids, "only a matching command records a lot")

    def test_new_match_after_a_profile_change_keeps_the_earlier_lot(self):
        opportunity = self._opportunity()
        first_run, _sent = self._match(opportunity)
        first_lot = first_run.approval_id
        first_digest = first_lot.snapshot_digest
        self.profile.contamination_percent = 4.0
        second_run, _sent = self._match(opportunity)
        self.env.invalidate_all()
        self.assertNotEqual(second_run.approval_id, first_lot)
        self.assertEqual(first_lot.snapshot_digest, first_digest, "the historical lot is unchanged")
        self.assertEqual(first_lot.snapshot["contamination_pct"], 2.5)
        self.assertEqual(second_run.approval_id.snapshot["contamination_pct"], 4.0)
        self.assertEqual(first_run.approval_id, first_lot, "the earlier run keeps its own lot")

    def test_matching_chatter_carries_no_lot_or_snapshot_terms(self):
        opportunity = self._opportunity()
        messages_before = opportunity.message_ids
        run, _sent = self._match(opportunity)
        posted = opportunity.message_ids - messages_before
        bodies = " ".join(message.body or "" for message in posted)
        self.assertIn("Matching completed: 1 eligible buyer(s) found.", bodies)
        for term in ("lot", "Lot", "snapshot", "Snapshot", run.approval_id.snapshot_digest[:12]):
            self.assertNotIn(term, bodies, f"chatter exposes technical evidence term {term!r}")
        self.assertTrue(run.approval_id, "the lot is still recorded as backend evidence")

    def test_commercial_views_show_no_lot_interaction(self):
        opportunity_form = self.Lead.get_views([(False, "form")])["views"]["form"]["arch"]
        self.assertNotIn("approval_ids", opportunity_form)
        self.assertNotIn("approval_id", opportunity_form)
        self.assertNotIn("snapshot_digest", opportunity_form)
        self.assertNotIn("Approved Lots", opportunity_form)
        self.assertIn("match_run_ids", opportunity_form, "Gate match runs stay visible")
        form = etree.fromstring(opportunity_form)
        for name in ("action_match_opportunity", "action_create_offers_from_results", "action_view_match_runs"):
            for button in form.xpath(f"//button[@name='{name}']"):
                title = button.get("title") or ""
                self.assertNotRegex(title, r"(?i)\blots?\b|snapshot", f"{name} tooltip names a lot or snapshot")
        run_views = self.Run.get_views([(False, "list"), (False, "form")])["views"]
        for view_type in ("list", "form"):
            arch = run_views[view_type]["arch"]
            self.assertNotIn("approval_id", arch, f"no technical lot reference on the match run {view_type}")
            self.assertIn("opportunity_id", arch)

    # ── V3: reviewed results → idempotent unsent drafts, frozen terms, one winner ──

    def _reviewed_run(self):
        opportunity = self._opportunity()
        run, _sent = self._match(opportunity, [_eligible(self.buyer_a, 0.9, 1), _eligible(self.buyer_b, 0.7, 2)])
        self.assertEqual(len(run.result_ids), 2)
        run.result_ids.action_accept()
        return opportunity, run

    def test_reviewed_results_create_idempotent_unsent_drafts(self):
        opportunity, run = self._reviewed_run()
        opportunity.action_create_offers_from_results()
        offers = self.Offer.search([("match_result_id", "in", run.result_ids.ids)])
        self.assertEqual(len(offers), 2)
        self.assertEqual(set(offers.mapped("state")), {"draft"})
        self.assertEqual(set(offers.mapped("buyer_id").ids), {self.buyer_a.id, self.buyer_b.id})
        self.assertEqual(set(offers.mapped("supplier_id").ids), {self.supplier.id})
        self.assertFalse(any(offers.mapped("intake_id")))
        self.assertEqual(set(offers.mapped("price_per_lb")), {0.0}, "a Gate match carries no price authority")
        opportunity.action_create_offers_from_results()
        self.assertEqual(self.Offer.search_count([("match_result_id", "in", run.result_ids.ids)]), 2)
        for offer in offers:
            self.assertEqual(offer._plasticos_opportunity(), opportunity)

    def test_unreviewed_results_create_no_offer(self):
        opportunity = self._opportunity()
        self._match(opportunity)
        with self.assertRaisesRegex(UserError, "reviewed"):
            opportunity.action_create_offers_from_results()
        self.assertFalse(self.Offer.search([("match_result_id.match_run_id.opportunity_id", "=", opportunity.id)]))

    def test_sent_offer_terms_are_immutable(self):
        opportunity, _run = self._reviewed_run()
        opportunity.action_create_offers_from_results()
        offer = self.Offer.search([("match_result_id.match_run_id.opportunity_id", "=", opportunity.id)])[:1]
        offer.write({"price_per_lb": 0.12, "quantity_lbs": 40000})
        send_offer_email(offer)
        with self.assertRaisesRegex(UserError, "immutable"):
            offer.write({"price_per_lb": 0.20})
        offer.write({"response_notes": "buyer replied"})
        self.assertEqual(offer.price_per_lb, 0.12)

    def test_lot_survives_a_gate_failure_and_the_failed_run_keeps_its_lineage(self):
        """The lot is durable before Gate; a transport failure leaves a retryable run naming that lot.

        Odoo's ``assertRaises`` wraps its block in a savepoint that would undo the
        durable run written on the owned cursor, so the failure is caught by hand.
        """
        from odoo.addons.plasticos_gate.services.gate_config import GateIntegrationError  # noqa: PLC0415

        opportunity = self._opportunity()
        lots_before = len(opportunity.approval_ids)
        holder = SimpleNamespace(savepoint=None)

        def ambient_rollback():
            holder.savepoint.rollback()

        raised = None
        try:
            with (
                self._lot_commit_stand_in(holder),
                patch.object(self.env.cr, "rollback", ambient_rollback),
                patch(_CLASSIFY, return_value=_available_verdict()),
                patch(_ENABLED, return_value=True),
                patch(_SEND, side_effect=GateIntegrationError("gate unreachable", failure_class="retryable")),
            ):
                try:
                    opportunity.action_match_opportunity()
                except UserError as exc:
                    raised = exc
        finally:
            if holder.savepoint is not None:
                holder.savepoint.close(rollback=False)
        self.assertIsNotNone(raised, "a Gate transport failure must surface as UserError")
        self.assertIn("Gate match failed", str(raised))
        self.env.invalidate_all()
        self.assertEqual(len(opportunity.approval_ids), lots_before + 1, "the minted lot survived the rollback")
        failed = self.Run.search([("opportunity_id", "=", opportunity.id), ("state", "=", "retryable")])
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed.approval_id, opportunity.approval_ids.sorted("id")[-1])
        self.assertTrue(failed._plasticos_lot_retry_subject(), "the retry is built from the surviving lot")

    def test_exactly_one_commercial_winner_per_opportunity(self):
        opportunity, _run = self._reviewed_run()
        opportunity.action_create_offers_from_results()
        offers = self.Offer.search([("match_result_id.match_run_id.opportunity_id", "=", opportunity.id)], order="id")
        offers.write({"price_per_lb": 0.12, "quantity_lbs": 40000})
        send_offer_email(offers)
        first, second = offers[0], offers[1]
        first.action_accept()
        self.assertEqual(first.state, "accepted")
        with self.assertRaisesRegex(UserError, "commercial winner"):
            second.action_accept()
        self.assertEqual(second.state, "sent")

    # ── V4: native sale.order via opportunity_id → existing transaction compiler ──

    def test_acceptance_marks_won_and_creates_no_orders(self):
        SaleOrder = self.env["sale.order"]
        opportunity, _run = self._reviewed_run()
        opportunity.action_create_offers_from_results()
        offer = self.Offer.search([("match_result_id.match_run_id.opportunity_id", "=", opportunity.id)], order="id")[
            :1
        ]
        offer.write({"price_per_lb": 0.12, "quantity_lbs": 40000})
        send_offer_email(offer)
        orders_before = SaleOrder.search_count([("opportunity_id", "=", opportunity.id)])
        purchases_before = self.env["purchase.order"].search_count([("origin", "=", offer.name)])
        transactions_before = self.env["plasticos.transaction"].search_count(
            [("sale_order_id.opportunity_id", "=", opportunity.id)]
        )

        offer.action_accept()

        self.assertEqual(SaleOrder.search_count([("opportunity_id", "=", opportunity.id)]), orders_before)
        self.assertEqual(self.env["purchase.order"].search_count([("origin", "=", offer.name)]), purchases_before)
        self.assertEqual(
            self.env["plasticos.transaction"].search_count([("sale_order_id.opportunity_id", "=", opportunity.id)]),
            transactions_before,
        )
        self.assertEqual(opportunity.stage_id, self.env.ref("crm.stage_lead4"))
        self.assertTrue(opportunity.stage_id.is_won)
