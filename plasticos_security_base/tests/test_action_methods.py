"""Action/Button method tests for all PlastOS models.

Covers 67+ action methods across 9 models:
    plasticos.intake (14), plasticos.load (10), plasticos.offer (9),
    plasticos.claim (7), plasticos.web.lead (6), crm.lead (6),
    plasticos.enrichment.run (5), plasticos.material.profile (6),
    plasticos.transaction (4)

Each test class validates:
- Action methods execute without error
- State transitions are correct
- Chatter messages are posted where expected
- Return values (action dicts) are properly formed
- Error conditions raise appropriate exceptions
"""

import os
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged


# ═══════════════════════════════════════════════════════════════
# 1. plasticos.intake — 14 action methods
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "action", "intake")
class TestIntakeActions(PlasticosTestCase):
    """Tests for plasticos.intake action/button methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.intake")
        cls.Intake = cls.env["plasticos.intake"]
        cls.partner = cls._create_partner("Intake Supplier")

    def _make_intake(self, **kw):
        vals = {
            "partner_id": self.partner.id,
            "polymer_id": self.default_polymer.id,
            "form_id": self.default_form.id,
            "quantity_per_load_lbs": 40000,
        }
        vals.update(kw)
        return self.Intake.create(vals)

    # The intake lifecycle is ``status`` (draft → matched → offer_sent → processing →
    # won/lost/expired), not a draft/confirmed/cancelled ``state``, and the model has
    # no ``active`` field (plasticos_intake/models/intake.py:365). The guarded
    # forward transition is action_mark_processing; the close-outs are
    # action_mark_lost / action_mark_expired (intake.py:736-762).

    # action_mark_processing (guarded forward transition; formerly action_confirm)
    def test_action_mark_processing_offer_sent_to_processing(self):
        intake = self._make_intake(status="offer_sent")
        intake.action_mark_processing()
        self.assertEqual(intake.status, "processing")

    def test_action_mark_processing_posts_message(self):
        intake = self._make_intake(status="offer_sent")
        intake.action_mark_processing()
        messages = intake.message_ids.filtered(lambda m: "processing" in (m.body or "").lower())
        self.assertTrue(messages)

    def test_action_mark_processing_twice_raises(self):
        intake = self._make_intake(status="offer_sent")
        intake.action_mark_processing()
        with self.assertRaises(UserError):
            intake.action_mark_processing()

    # action_mark_lost (close-out; formerly action_cancel)
    def test_action_mark_lost_sets_lost(self):
        intake = self._make_intake()
        intake.action_mark_lost()
        self.assertEqual(intake.status, "lost")

    def test_action_mark_lost_posts_message(self):
        intake = self._make_intake()
        intake.action_mark_lost()
        messages = intake.message_ids.filtered(lambda m: "lost" in (m.body or "").lower())
        self.assertTrue(messages)

    # action_mark_expired (retires an idle intake; the model has no archive/active)
    def test_action_mark_expired_closes_intake(self):
        intake = self._make_intake()
        intake.action_mark_expired()
        self.assertEqual(intake.status, "expired")
        messages = intake.message_ids.filtered(lambda m: "expired" in (m.body or "").lower())
        self.assertTrue(messages)

    # action_reset_to_draft
    def test_action_reset_to_draft(self):
        intake = self._make_intake()
        intake.action_mark_lost()
        intake.action_reset_to_draft()
        self.assertEqual(intake.status, "draft")

    # action_normalize
    def test_action_normalize(self):
        intake = self._make_intake()
        if hasattr(intake, "action_normalize"):
            intake.action_normalize()
            self.assertTrue(intake.normalized)

    # action_match_to_buyers — Gate-only (plasticos_matching/models/intake_extension.py:19).
    # Gate availability is checked first and fails closed; no local matching and no
    # pending-company partner creation happens on that path.
    def test_action_match_to_buyers_without_gate_refuses(self):
        intake = self._make_intake(partner_id=False, pending_company_name="Match Test")
        with patch.dict(os.environ, {"GATE_URL": ""}):
            with self.assertRaises(UserError):
                intake.action_match_to_buyers()
        self.assertFalse(intake.partner_id)
        self.assertEqual(intake.status, "draft")

    # action_view_matches (the intake's match navigation; intake.py:709)
    def test_action_view_matches_returns_action(self):
        intake = self._make_intake()
        result = intake.action_view_matches()
        self.assertEqual(result["res_model"], "plasticos.intake.match")
        self.assertEqual(result["domain"], [("intake_id", "=", intake.id)])

    # action_view_offers
    def test_action_view_offers_returns_action(self):
        intake = self._make_intake()
        if hasattr(intake, "action_view_offers"):
            result = intake.action_view_offers()
            self.assertEqual(result["type"], "ir.actions.act_window")

    # action_view_transactions
    def test_action_view_transactions_returns_action(self):
        intake = self._make_intake()
        if hasattr(intake, "action_view_transactions"):
            result = intake.action_view_transactions()
            self.assertEqual(result["type"], "ir.actions.act_window")

    # action_view_loads
    def test_action_view_loads_returns_action(self):
        intake = self._make_intake()
        if hasattr(intake, "action_view_loads"):
            result = intake.action_view_loads()
            self.assertEqual(result["type"], "ir.actions.act_window")

    # action_open_partner
    def test_action_open_partner_returns_action(self):
        intake = self._make_intake()
        if hasattr(intake, "action_open_partner"):
            result = intake.action_open_partner()
            self.assertEqual(result["res_model"], "res.partner")


# ═══════════════════════════════════════════════════════════════
# 2. plasticos.load — 10 action methods
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "action", "load")
class TestLoadActions(PlasticosTestCase):
    """Tests for plasticos.load action/button methods."""

    # Loads are created in Draft and move only through VALID_TRANSITIONS
    # (plasticos_logistics/services/state_machine.py:9; create/write guards at
    # plasticos_logistics/models/load.py:270-274 and :347-349). There is no
    # ``cancelled`` state and no action_deliver / action_cancel: picked_up → delivered
    # and the ``exception`` off-ramp are workflow transitions, and ``closed`` is terminal.
    # Fixtures place a load in a mid-workflow state through the narrow internal freight
    # capability (load.py:330), as the logistics suite does (test_load_cardinality.py:45).

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.load")
        cls.Load = cls.env["plasticos.load"]
        cls.origin = cls._create_partner("Load Action Origin", supplier_rank=1)
        cls.destination = cls._create_partner("Load Action Destination", customer_rank=1)
        cls.carrier = cls._create_partner("Load Action Carrier", supplier_rank=1)

    def _make_load(self, **kw):
        vals = {
            "pickup_partner_id": self.origin.id,
            "delivery_partner_id": self.destination.id,
        }
        vals.update(kw)
        return self.Load.create(vals)

    def _put_in_state(self, load, state):
        load._freight_write({"state": state})
        self.assertEqual(load.state, state)

    def _make_priced_load(self):
        """A load with a complete freight context (plasticos_logistics/services/freight_context.py:51)."""
        intake = self._create_intake(partner=self.origin)
        sale = self.env["sale.order"].create({"partner_id": self.destination.id})
        load = self._make_load(
            sale_order_id=sale.id,
            reference_weight=40000,
            carrier_id=self.carrier.id,
        )
        self.env["plasticos.transaction"].create(
            {
                "sale_order_id": sale.id,
                "supplier_id": self.origin.id,
                "buyer_id": self.destination.id,
                "intake_id": intake.id,
            }
        )
        load.invalidate_recordset()
        return load

    def test_action_confirm_ready(self):
        load = self._make_load()
        load._transition("awaiting_ready")
        load.action_confirm_ready()
        self.assertEqual(load.state, "ready_confirmed")
        self.assertTrue(load.ready_confirmed_at)

    def test_action_dispatch(self):
        load = self._make_load(carrier_id=self.carrier.id, pickup_datetime=fields.Datetime.now())
        self._put_in_state(load, "scheduled")
        load.action_dispatch()
        self.assertEqual(load.state, "dispatched")
        self.assertTrue(load.dispatched_at)

    def test_transition_picked_up_to_delivered(self):
        load = self._make_load()
        self._put_in_state(load, "picked_up")
        load._transition("delivered")
        self.assertEqual(load.state, "delivered")
        self.assertTrue(load.delivered_at)

    def test_transition_awaiting_ready_to_exception(self):
        load = self._make_load()
        load._transition("awaiting_ready")
        load._transition("exception")
        self.assertEqual(load.state, "exception")

    def test_transition_from_closed_raises(self):
        load = self._make_load()
        self._put_in_state(load, "closed")
        with self.assertRaises(UserError):
            load._transition("exception")

    def test_action_schedule(self):
        load = self._make_load()
        self._put_in_state(load, "rate_confirmed")
        pickup = fields.Datetime.now()
        delivery = pickup + timedelta(days=1)
        load.action_schedule(pickup, delivery)
        self.assertEqual(load.state, "scheduled")
        self.assertEqual(load.pickup_datetime, pickup)

    def test_action_confirm_rate(self):
        load = self._make_priced_load()
        load._transition("awaiting_ready")
        load.action_confirm_ready()
        load.action_confirm_rate(1500.0)
        self.assertEqual(load.state, "rate_confirmed")
        self.assertEqual(load.rate_amount, 1500.0)
        self.assertEqual(load.rate_resolution_method, "manual")

    def test_action_close(self):
        load = self._make_load()
        self._put_in_state(load, "delivered")
        load.write({"bol_pickup_attached": True, "bol_delivery_attached": True})
        load.action_close()
        self.assertEqual(load.state, "closed")

    def test_state_posts_message(self):
        load = self._make_load()
        load._transition("awaiting_ready")
        self.env.cr.precommit.run()  # flush pending mail tracking
        initial_count = len(load.message_ids)
        load.action_confirm_ready()
        self.env.cr.precommit.run()
        load.invalidate_recordset(["message_ids"])
        self.assertGreater(len(load.message_ids), initial_count)

    def test_action_view_transaction(self):
        load = self._make_load()
        # Without a linked transaction the button returns False (load.py:1324-1329).
        self.assertFalse(load.action_view_transaction())
        # A load can only be assigned once supplier and buyer are set
        # (plasticos_logistics/models/transaction_inherit.py:52-61).
        order = self.env["sale.order"].create({"partner_id": self.destination.id})
        load.sale_order_id = order
        tx = self._create_transaction(supplier_id=self.origin.id, buyer_id=self.destination.id, sale_order_id=order.id)
        result = load.action_view_transaction()
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_id"], tx.id)


# ═══════════════════════════════════════════════════════════════
# 3. plasticos.offer — 9 action methods
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "action", "offer")
class TestOfferActions(PlasticosTestCase):
    """Tests for plasticos.offer action/button methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.offer")
        cls.Offer = cls.env["plasticos.offer"]
        cls.partner = cls._create_partner("Offer Buyer", customer_rank=1)
        cls.supplier = cls._create_partner("Offer Supplier", supplier_rank=1)
        cls.intake = cls._create_intake(partner=cls.supplier)

    def _make_offer(self, **kw):
        # intake_id, supplier_id and buyer_id are required (plasticos_offer/models/offer.py:48-77);
        # the buyer field is buyer_id (there is no buyer_partner_id).
        vals = {
            "intake_id": self.intake.id,
            "supplier_id": self.supplier.id,
            "buyer_id": self.partner.id,
        }
        vals.update(kw)
        return self.Offer.create(vals)

    def test_action_send_sets_sent(self):
        offer = self._make_offer()
        if hasattr(offer, "action_send"):
            offer.action_send()
            self.assertEqual(offer.state, "sent")

    def test_action_accept(self):
        offer = self._make_offer(state="sent")
        if hasattr(offer, "action_accept"):
            offer.action_accept()
            self.assertEqual(offer.state, "accepted")
            self.assertEqual(offer.accepted_by, self.env.user)

    def test_action_reject(self):
        offer = self._make_offer(state="sent")
        if hasattr(offer, "action_reject"):
            offer.action_reject()
            self.assertEqual(offer.state, "rejected")

    def test_action_accept_creates_transaction(self):
        offer = self._make_offer(state="sent")
        if hasattr(offer, "action_accept"):
            offer.action_accept()
            if hasattr(offer, "transaction_id"):
                self.assertTrue(offer.transaction_id)

    def test_cron_expire_offers_expires_sent_offer(self):
        # Expiry is the daily cron over valid_until, not a button (offer.py:483-504).
        offer = self._make_offer(state="sent", valid_until=fields.Date.today() - timedelta(days=1))
        self.Offer.cron_expire_offers()
        offer.invalidate_recordset(["state"])
        self.assertEqual(offer.state, "expired")

    def test_action_cancel(self):
        offer = self._make_offer()
        if hasattr(offer, "action_cancel"):
            offer.action_cancel()
            self.assertEqual(offer.state, "cancelled")

    def test_action_reset_to_draft_then_resend(self):
        # There is no action_resend: a rejected/cancelled offer is reset to draft and sent
        # again; an expired offer is closed and cannot be reset (offer.py:367-416).
        expired = self._make_offer(state="expired")
        with self.assertRaises(UserError):
            expired.action_reset_to_draft()
        offer = self._make_offer(state="rejected")
        offer.action_reset_to_draft()
        offer.action_send()
        self.assertEqual(offer.state, "sent")

    def test_action_view_intake(self):
        offer = self._make_offer()
        if hasattr(offer, "action_view_intake"):
            result = offer.action_view_intake()
            self.assertEqual(result["type"], "ir.actions.act_window")

    def test_action_view_transaction(self):
        offer = self._make_offer()
        # The button opens the linked transaction (plasticos_transaction/models/offer_bridge.py:18).
        tx = self._create_transaction()
        offer.transaction_id = tx
        result = offer.action_view_transaction()
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_id"], tx.id)


# ═══════════════════════════════════════════════════════════════
# 4. plasticos.claim — 7 action methods
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "action", "claim")
class TestClaimActions(PlasticosTestCase):
    """Tests for plasticos.claim action/button methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.claim", "plasticos.transaction")
        cls.Claim = cls.env["plasticos.claim"]
        cls.tx = cls._create_transaction(name="TX-CLM-ACTION")

    def _make_claim(self, **kw):
        vals = {
            "transaction_id": self.tx.id,
            "case_type": "buyer_claim",
            "severity": "medium",
            "state": "pending",
        }
        vals.update(kw)
        return self.Claim.create(vals)

    # Claim states are pending → in_progress → escalated → resolved → archived
    # (plasticos_claims/models/claim.py:73-80). action_start/action_resolve/action_archive/
    # action_reopen/action_escalate are at claim.py:266-317; a resolved claim must carry a
    # resolution_note (claim.py:224-228) and escalation_level is a counter (claim.py:180).

    def test_action_start(self):
        claim = self._make_claim()
        claim.action_start()
        self.assertEqual(claim.state, "in_progress")

    def test_action_resolve(self):
        claim = self._make_claim(state="in_progress", resolution_note="Credit issued.")
        claim.action_resolve()
        self.assertEqual(claim.state, "resolved")
        self.assertTrue(claim.resolved_at)

    def test_action_archive(self):
        claim = self._make_claim(state="resolved", resolution_note="Credit issued.")
        claim.action_archive()
        self.assertEqual(claim.state, "archived")

    def test_action_reopen(self):
        claim = self._make_claim(state="resolved", resolution_note="Credit issued.")
        claim.action_reopen()
        self.assertEqual(claim.state, "in_progress")
        self.assertFalse(claim.resolved_at)

    def test_action_escalate(self):
        claim = self._make_claim()
        claim.action_escalate()
        self.assertEqual(claim.state, "escalated")
        self.assertEqual(claim.escalation_level, 1)

    def test_action_archive_from_in_progress_is_noop(self):
        # Only a resolved claim can be archived; any other state is left untouched.
        claim = self._make_claim(state="in_progress")
        claim.action_archive()
        self.assertEqual(claim.state, "in_progress")

    def test_resolve_posts_message(self):
        claim = self._make_claim(state="in_progress", resolution_note="Credit issued.")
        self.env.cr.precommit.run()  # flush pending mail tracking
        initial_count = len(claim.message_ids)
        claim.action_resolve()
        self.env.cr.precommit.run()
        claim.invalidate_recordset(["message_ids"])
        self.assertGreater(len(claim.message_ids), initial_count)


# ═══════════════════════════════════════════════════════════════
# 5. plasticos.web.lead — 6 action methods
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "action", "web_lead")
class TestWebLeadActions(PlasticosTestCase):
    """Tests for plasticos.web.lead action/button methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.web.lead")
        cls.WebLead = cls.env["plasticos.web.lead"]

    def _make_web_lead(self, **kw):
        import uuid

        vals = {
            "lead_id": f"WL-{uuid.uuid4().hex[:8]}",
            "decision": "cold",
            "company_name": "Test Co",
            "state": "received",
        }
        vals.update(kw)
        return self.WebLead.create(vals)

    def test_action_retry_processing_only_error(self):
        lead = self._make_web_lead(state="received")
        with self.assertRaises(UserError):
            lead.action_retry_processing()

    def test_action_retry_processing_from_error(self):
        lead = self._make_web_lead(state="error", decision="hot")
        lead.action_retry_processing()
        self.assertNotEqual(lead.state, "error")

    def test_action_force_create_intake(self):
        lead = self._make_web_lead(decision="cold")
        lead.action_force_create_intake()
        self.assertTrue(lead.intake_id)
        self.assertEqual(lead.state, "intake_created")

    def test_action_force_create_intake_already_exists_raises(self):
        lead = self._make_web_lead(decision="cold")
        lead.action_force_create_intake()
        with self.assertRaises(UserError):
            lead.action_force_create_intake()

    def test_action_retry_triage(self):
        lead = self._make_web_lead(state="error")
        with patch.object(type(lead), "_run_triage_pipeline") as m_triage:
            lead.action_retry_triage()
            m_triage.assert_called()

    def test_action_retry_triage_wrong_state_raises(self):
        lead = self._make_web_lead(state="intake_created")
        with self.assertRaises(UserError):
            lead.action_retry_triage()

    def test_action_force_hot(self):
        lead = self._make_web_lead(decision="cold")
        lead.action_force_hot()
        self.assertEqual(lead.decision, "hot")
        self.assertTrue(lead.intake_id)

    def test_action_view_intake(self):
        lead = self._make_web_lead(decision="cold")
        lead.action_force_create_intake()
        result = lead.action_view_intake()
        self.assertEqual(result["res_model"], "plasticos.intake")

    def test_action_view_partner_no_partner(self):
        lead = self._make_web_lead()
        result = lead.action_view_partner()
        self.assertFalse(result)


# ═══════════════════════════════════════════════════════════════
# 6. crm.lead — 6 action methods (plasticos_crm_bridge)
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "action", "crm")
class TestCrmLeadActions(PlasticosTestCase):
    """Tests for crm.lead action methods added by plasticos_crm_bridge."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("crm.lead")
        cls.Lead = cls.env["crm.lead"]
        cls.partner = cls._create_partner("CRM Test Co")

    def _make_lead(self, **kw):
        vals = {
            "name": "Test CRM Lead",
            "partner_name": "CRM Test Co",
            "email_from": "test@example.com",
            "type": "lead",
        }
        vals.update(kw)
        return self.Lead.create(vals)

    def test_action_convert_to_intake_creates_intake(self):
        lead = self._make_lead(partner_id=self.partner.id)
        result = lead.action_convert_to_intake()
        self.assertEqual(result["res_model"], "plasticos.intake")
        self.assertTrue(lead.intake_ids)

    def test_action_convert_keeps_partner_missing(self):
        lead = self._make_lead(partner_id=False, partner_name="New Auto Co")
        result = lead.action_convert_to_intake()
        self.assertFalse(lead.partner_id)
        self.assertFalse(lead.source_intake_id.partner_id)
        self.assertEqual(lead.source_intake_id.id, result["res_id"])
        self.assertEqual(lead.source_intake_id.pending_company_name, "New Auto Co")

    def test_action_convert_moves_stage(self):
        stage = self.env.ref("plasticos_crm_bridge.stage_new")
        lead = self._make_lead(partner_id=self.partner.id, stage_id=stage.id)
        self.assertFalse(lead.stage_id.is_won)
        lead.action_convert_to_intake()
        self.assertEqual(lead.stage_id, stage)
        self.assertFalse(lead.stage_id.is_won)

    def test_action_convert_posts_message(self):
        lead = self._make_lead(partner_id=self.partner.id)
        lead.action_convert_to_intake()
        messages = lead.message_ids.filtered(lambda m: "intake created" in (m.body or "").lower())
        self.assertTrue(messages)

    def test_action_view_intakes(self):
        lead = self._make_lead(partner_id=self.partner.id)
        result = lead.action_view_intakes()
        self.assertEqual(result["res_model"], "plasticos.intake")

    def test_action_view_web_leads(self):
        lead = self._make_lead()
        result = lead.action_view_web_leads()
        self.assertEqual(result["res_model"], "plasticos.web.lead")

    def test_action_view_material_profiles(self):
        lead = self._make_lead(partner_id=self.partner.id)
        result = lead.action_view_material_profiles()
        self.assertEqual(result["res_model"], "plasticos.material.profile")

    def test_action_view_match_results(self):
        # Local match-result navigation was retired: the button now returns a
        # "Feature Disabled" notification (plasticos_crm_bridge/models/crm_lead.py:466-480).
        lead = self._make_lead(partner_id=self.partner.id)
        result = lead.action_view_match_results()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "warning")

    def test_action_view_transactions(self):
        lead = self._make_lead(partner_id=self.partner.id)
        result = lead.action_view_transactions()
        self.assertEqual(result["res_model"], "plasticos.transaction")

    def test_computed_fields(self):
        lead = self._make_lead(partner_id=self.partner.id)
        self.assertIsInstance(lead.web_lead_count, int)
        self.assertIsInstance(lead.intake_count, int)
        self.assertIsInstance(lead.material_profile_count, int)

    def test_profile_summary_no_partner(self):
        lead = self._make_lead(partner_id=False)
        self.assertEqual(lead.material_profile_count, 0)
        self.assertEqual(lead.total_match_count, 0)


# ═══════════════════════════════════════════════════════════════
# 7. plasticos.enrichment.run — 5 action methods
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "action", "enrichment")
class TestEnrichmentRunActions(PlasticosTestCase):
    """Tests for plasticos.enrichment.run action/button methods."""

    # Enrichment is Gate-only (M4): action_execute converges through Gate and never
    # crawls locally; on Gate failure it rolls the request back and persists the
    # classified state on an owned cursor (plasticos_enrichment/models/enrichment_run.py:317-441).
    # partner_id is required (enrichment_run.py:26). The Gate transport and availability
    # verdict are the external boundary and are patched; the run's own handling is not.

    _CLASSIFY = "odoo.addons.plasticos_gate.services.gate_config.classify_gate_availability"
    _ENABLED = "odoo.addons.plasticos_gate.services.gate_config.gate_enrichment_enabled"
    _SEND = "odoo.addons.plasticos_gate.services.gate_client.send_converge_action"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.enrichment.run")
        cls.Run = cls.env["plasticos.enrichment.run"]

    def _make_run(self, partner=None, **kw):
        partner = partner or self._create_partner("Enrichment Run Co", supplier_rank=1)
        vals = {"partner_id": partner.id}
        vals.update(kw)
        return self.Run.create(vals)

    def _verdict(self, available):
        from odoo.addons.plasticos_gate.services.gate_config import (
            GateAvailability,
            GateAvailabilityVerdict,
            GateCapability,
        )

        return GateAvailabilityVerdict(
            status=GateAvailability.AVAILABLE if available else GateAvailability.ENRICHMENT_DISABLED,
            available=available,
            capability=GateCapability.ENRICHMENT,
            reasons=[] if available else ["enrichment disabled"],
            gate_url_configured=True,
        )

    @staticmethod
    def _completed_converge_result():
        """EIE EnrichResponse shape relayed by Gate (mapped by gate_mappers.map_converge_response)."""
        packet = SimpleNamespace(header=SimpleNamespace(packet_id="pkt-act-1", correlation_id="corr-act-1"))
        payload = {
            "state": "completed",
            "failure_reason": None,
            "fields": {"website": "https://enriched.example"},
            "confidence": 0.9,
        }
        return {"packet": packet, "payload": payload}

    @contextmanager
    def _request_rollback(self):
        """Stand in for the RPC request rollback with a savepoint rollback (cr.rollback() is forbidden in tests)."""
        self.registry_enter_test_mode()
        savepoint = self.env.cr.savepoint(flush=True)
        try:
            with patch.object(self.env.cr, "rollback", savepoint.rollback):
                yield
        finally:
            savepoint.close(rollback=False)

    def test_action_execute(self):
        run = self._make_run()
        with (
            patch(self._CLASSIFY, return_value=self._verdict(False)),
            patch(self._ENABLED, return_value=False),
            patch(self._SEND, side_effect=AssertionError("Gate must not be called when disabled")),
            self._request_rollback(),
        ):
            # Not self.assertRaises: its savepoint would undo the durable failure write.
            try:
                run.action_execute()
            except UserError:
                pass
            else:
                self.fail("UserError not raised")
        run.invalidate_recordset()
        self.assertEqual(run.state, "failed")
        self.assertEqual(run.failure_class, "permanent")

    def test_action_inject(self):
        partner = self._create_partner("Enrichment Inject Co", supplier_rank=1)
        proposed = {"website": "https://enriched.example"}
        run = self._make_run(
            partner=partner,
            engine_used="gate",
            state="review",
            gate_proposal={"final_fields": proposed, "proposed_partner_fields": proposed},
            gate_packet_id="pkt-act-inject",
        )
        run.action_inject()
        self.assertEqual(run.state, "injected")
        self.assertEqual(run.fields_written, 1)
        self.assertEqual(partner.website, "https://enriched.example")

    def test_action_run_inference(self):
        # Local inference was retired in M4 and now refuses (enrichment_run.py:741-743).
        run = self._make_run(state="injected")
        with self.assertRaises(UserError):
            run.action_run_inference()

    def test_action_retry_from_error(self):
        run = self._make_run(state="failed")
        with (
            patch(self._CLASSIFY, return_value=self._verdict(True)),
            patch(self._ENABLED, return_value=True),
            patch(self._SEND, return_value=self._completed_converge_result()),
        ):
            run.action_retry_enrichment()
        self.assertNotIn(run.state, ("failed", "retryable", "degraded"))
        self.assertEqual(run.gate_attempt, 2)

    def test_action_cancel(self):
        run = self._make_run()
        if hasattr(run, "action_cancel"):
            run.action_cancel()
            self.assertEqual(run.state, "cancelled")


# ═══════════════════════════════════════════════════════════════
# 8. plasticos.material.profile — 6 action methods
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "action", "material_profile")
class TestMaterialProfileActions(PlasticosTestCase):
    """Tests for plasticos.material.profile action/button methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.material.profile")
        cls.Profile = cls.env["plasticos.material.profile"]
        cls.partner = cls._create_partner("Profile Facility")

    def _make_profile(self, **kw):
        vals = {"partner_id": self.partner.id, "polymer_id": self.default_polymer.id}
        vals.update(kw)
        return self.Profile.create(vals)

    def test_action_archive(self):
        profile = self._make_profile()
        profile.action_archive()
        self.assertFalse(profile.active)

    def test_action_unarchive(self):
        profile = self._make_profile(active=False)
        if hasattr(profile, "action_unarchive"):
            profile.action_unarchive()
            self.assertTrue(profile.active)

    def test_action_view_match_results(self):
        # Retired to a "Feature Disabled" notification
        # (plasticos_crm_bridge/models/material_profile.py:114-128).
        profile = self._make_profile()
        if hasattr(profile, "action_view_match_results"):
            result = profile.action_view_match_results()
            self.assertEqual(result["type"], "ir.actions.client")
            self.assertEqual(result["tag"], "display_notification")

    def test_action_view_transactions(self):
        profile = self._make_profile()
        if hasattr(profile, "action_view_transactions"):
            result = profile.action_view_transactions()
            self.assertEqual(result["type"], "ir.actions.act_window")

    def test_action_run_matching(self):
        profile = self._make_profile()
        if not hasattr(profile, "action_run_matching"):
            self.skipTest("action_run_matching not available")
        with patch.object(type(profile), "_trigger_matching") as m_match:
            profile.action_run_matching()
            m_match.assert_called()

    def test_action_refresh_scores(self):
        profile = self._make_profile()
        if not hasattr(profile, "action_refresh_scores"):
            self.skipTest("action_refresh_scores not available")
        profile.action_refresh_scores()
        self.assertTrue(profile.exists())


# ═══════════════════════════════════════════════════════════════
# 9. plasticos.transaction — 4 action methods
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "action", "transaction")
class TestTransactionActions(PlasticosTestCase):
    """Tests for plasticos.transaction action/button methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.transaction")
        cls.Tx = cls.env["plasticos.transaction"]

    def _make_tx(self, **kw):
        vals = {}
        vals.update(kw)
        return self.Tx.create(vals)

    # Transaction states and their action methods: plasticos_transaction/models/transaction.py:433-452
    # and :998-1147 (state writes outside those actions are refused, transaction.py:924-946).

    def test_action_activate(self):
        tx = self._make_tx()
        tx.action_activate()
        self.assertEqual(tx.state, "active")

    def test_action_cancel(self):
        tx = self._make_tx()
        if hasattr(tx, "action_cancel"):
            tx.action_cancel()
            self.assertEqual(tx.state, "cancelled")

    def test_action_mark_delivered(self):
        # The delivery completion step; there is no ``confirmed`` state or action_complete.
        tx = self._make_tx(state="in_transit")
        tx.action_mark_delivered()
        self.assertEqual(tx.state, "delivered")

    def test_action_view_loads(self):
        tx = self._make_tx()
        if hasattr(tx, "action_view_loads"):
            result = tx.action_view_loads()
            self.assertEqual(result["type"], "ir.actions.act_window")
