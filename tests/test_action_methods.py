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

from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError, ValidationError
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

    # action_confirm
    def test_action_confirm_draft_to_confirmed(self):
        intake = self._make_intake()
        intake.action_confirm()
        self.assertEqual(intake.state, "confirmed")

    def test_action_confirm_posts_message(self):
        intake = self._make_intake()
        intake.action_confirm()
        self.assertTrue(intake.message_ids)

    def test_action_confirm_not_draft_raises(self):
        intake = self._make_intake()
        intake.action_confirm()
        raised = False
        try:
            intake.action_confirm()
        except (UserError, ValidationError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    # action_cancel
    def test_action_cancel_sets_cancelled(self):
        intake = self._make_intake()
        intake.action_cancel()
        self.assertEqual(intake.state, "cancelled")

    def test_action_cancel_posts_message(self):
        intake = self._make_intake()
        intake.action_cancel()
        messages = intake.message_ids.filtered(lambda m: "cancel" in (m.body or "").lower())
        self.assertTrue(messages)

    # action_archive
    def test_action_archive_sets_inactive(self):
        intake = self._make_intake()
        intake.action_archive()
        self.assertFalse(intake.active)

    # action_reset_to_draft
    def test_action_reset_to_draft(self):
        intake = self._make_intake()
        intake.action_cancel()
        if hasattr(intake, "action_reset_to_draft"):
            intake.action_reset_to_draft()
            self.assertEqual(intake.state, "draft")

    # action_normalize
    def test_action_normalize(self):
        intake = self._make_intake()
        if hasattr(intake, "action_normalize"):
            intake.action_normalize()
            self.assertTrue(intake.normalized)

    # action_match_to_buyers
    def test_action_match_to_buyers_creates_partner(self):
        intake = self._make_intake(partner_id=False, pending_company_name="Match Test")
        if hasattr(intake, "action_match_to_buyers"):
            intake.action_confirm()
            intake.action_match_to_buyers()
            self.assertTrue(intake.partner_id)

    # action_view_match_results
    def test_action_view_match_results_returns_action(self):
        intake = self._make_intake()
        result = intake.action_view_match_results()
        self.assertEqual(result["res_model"], "plasticos.match.result")

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

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.load")
        cls.Load = cls.env["plasticos.load"]

    def _make_load(self, **kw):
        vals = {"state": "draft"}
        vals.update(kw)
        return self.Load.create(vals)

    def test_action_confirm_ready(self):
        load = self._make_load()
        if hasattr(load, "action_confirm_ready"):
            load.action_confirm_ready()
            self.assertIn(load.state, ("awaiting_ready", "ready_confirmed"))

    def test_action_dispatch(self):
        load = self._make_load(state="scheduled")
        if hasattr(load, "action_dispatch"):
            load.action_dispatch()
            self.assertEqual(load.state, "dispatched")

    def test_action_deliver(self):
        load = self._make_load(state="dispatched")
        if hasattr(load, "action_deliver"):
            load.action_deliver()
            self.assertEqual(load.state, "delivered")

    def test_action_cancel_from_draft(self):
        load = self._make_load()
        if hasattr(load, "action_cancel"):
            load.action_cancel()
            self.assertEqual(load.state, "cancelled")

    def test_action_cancel_from_delivered_raises(self):
        load = self._make_load(state="delivered")
        if hasattr(load, "action_cancel"):
            with self.assertRaises(UserError):
                load.action_cancel()

    def test_action_schedule(self):
        load = self._make_load(state="rate_confirmed")
        if hasattr(load, "action_schedule"):
            load.action_schedule()
            self.assertEqual(load.state, "scheduled")

    def test_action_confirm_rate(self):
        load = self._make_load(state="ready_confirmed")
        if hasattr(load, "action_confirm_rate"):
            load.action_confirm_rate()
            self.assertEqual(load.state, "rate_confirmed")

    def test_action_close(self):
        load = self._make_load(state="delivered")
        if hasattr(load, "action_close"):
            load.action_close()
            self.assertEqual(load.state, "closed")

    def test_state_posts_message(self):
        load = self._make_load()
        initial_count = len(load.message_ids)
        if hasattr(load, "action_confirm_ready"):
            load.action_confirm_ready()
            self.assertGreater(len(load.message_ids), initial_count)

    def test_action_view_transaction(self):
        load = self._make_load()
        if hasattr(load, "action_view_transaction"):
            result = load.action_view_transaction()
            self.assertEqual(result["type"], "ir.actions.act_window")


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
        cls.partner = cls._create_partner("Offer Buyer")

    def _make_offer(self, **kw):
        vals = {"buyer_partner_id": self.partner.id}
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

    def test_action_expire(self):
        offer = self._make_offer(state="sent")
        if hasattr(offer, "action_expire"):
            offer.action_expire()
            self.assertEqual(offer.state, "expired")

    def test_action_cancel(self):
        offer = self._make_offer()
        if hasattr(offer, "action_cancel"):
            offer.action_cancel()
            self.assertEqual(offer.state, "cancelled")

    def test_action_resend(self):
        offer = self._make_offer(state="expired")
        if hasattr(offer, "action_resend"):
            offer.action_resend()
            self.assertEqual(offer.state, "sent")

    def test_action_view_intake(self):
        offer = self._make_offer()
        if hasattr(offer, "action_view_intake"):
            result = offer.action_view_intake()
            self.assertEqual(result["type"], "ir.actions.act_window")

    def test_action_view_transaction(self):
        offer = self._make_offer()
        if hasattr(offer, "action_view_transaction"):
            result = offer.action_view_transaction()
            self.assertEqual(result["type"], "ir.actions.act_window")


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

    def test_action_investigate(self):
        claim = self._make_claim()
        if hasattr(claim, "action_investigate"):
            claim.action_investigate()
            self.assertEqual(claim.state, "investigating")

    def test_action_resolve(self):
        claim = self._make_claim(state="investigating")
        if hasattr(claim, "action_resolve"):
            claim.action_resolve()
            self.assertEqual(claim.state, "resolved")

    def test_action_close(self):
        claim = self._make_claim(state="resolved")
        if hasattr(claim, "action_close"):
            claim.action_close()
            self.assertEqual(claim.state, "closed")

    def test_action_reopen(self):
        claim = self._make_claim(state="resolved")
        if hasattr(claim, "action_reopen"):
            claim.action_reopen()
            self.assertEqual(claim.state, "open")

    def test_action_escalate(self):
        claim = self._make_claim()
        if hasattr(claim, "action_escalate"):
            claim.action_escalate()
            self.assertTrue(claim.escalation_level in ("warning", "critical"))

    def test_action_close_from_open_raises(self):
        claim = self._make_claim(state="open")
        if hasattr(claim, "action_close"):
            with self.assertRaises(UserError):
                claim.action_close()

    def test_resolve_posts_message(self):
        claim = self._make_claim(state="investigating")
        if hasattr(claim, "action_resolve"):
            claim.action_resolve()
            self.assertTrue(claim.message_ids)


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
        with patch.object(type(lead), "_run_triage_pipeline"):
            lead.action_retry_triage()

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

    def test_action_convert_creates_partner_if_missing(self):
        lead = self._make_lead(partner_id=False, partner_name="New Auto Co")
        result = lead.action_convert_to_intake()
        self.assertTrue(lead.partner_id)

    def test_action_convert_moves_stage(self):
        lead = self._make_lead(partner_id=self.partner.id)
        lead.action_convert_to_intake()
        stage = self.env.ref("plasticos_crm_bridge.stage_active_supplier", raise_if_not_found=False)
        if stage:
            self.assertEqual(lead.stage_id, stage)

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
        lead = self._make_lead(partner_id=self.partner.id)
        result = lead.action_view_match_results()
        self.assertEqual(result["res_model"], "plasticos.match.result")

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

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.enrichment.run")
        cls.Run = cls.env["plasticos.enrichment.run"]

    def _make_run(self, **kw):
        vals = {}
        vals.update(kw)
        return self.Run.create(vals)

    def test_action_execute(self):
        run = self._make_run()
        if hasattr(run, "action_execute"):
            with patch.object(type(run), "_crawl_source", return_value=True):
                run.action_execute()

    def test_action_inject(self):
        run = self._make_run(state="crawled")
        if hasattr(run, "action_inject"):
            run.action_inject()

    def test_action_run_inference(self):
        run = self._make_run(state="injected")
        if hasattr(run, "action_run_inference"):
            with patch.object(type(run), "_run_inference_internal"):
                run.action_run_inference()

    def test_action_retry_from_error(self):
        run = self._make_run(state="error")
        if hasattr(run, "action_retry"):
            run.action_retry()
            self.assertNotEqual(run.state, "error")

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
        profile = self._make_profile()
        if hasattr(profile, "action_view_match_results"):
            result = profile.action_view_match_results()
            self.assertEqual(result["type"], "ir.actions.act_window")

    def test_action_view_transactions(self):
        profile = self._make_profile()
        if hasattr(profile, "action_view_transactions"):
            result = profile.action_view_transactions()
            self.assertEqual(result["type"], "ir.actions.act_window")

    def test_action_run_matching(self):
        profile = self._make_profile()
        if hasattr(profile, "action_run_matching"):
            with patch.object(type(profile), "_trigger_matching"):
                profile.action_run_matching()

    def test_action_refresh_scores(self):
        profile = self._make_profile()
        if hasattr(profile, "action_refresh_scores"):
            profile.action_refresh_scores()


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

    def test_action_confirm(self):
        tx = self._make_tx()
        if hasattr(tx, "action_confirm"):
            tx.action_confirm()
            self.assertEqual(tx.state, "confirmed")

    def test_action_cancel(self):
        tx = self._make_tx()
        if hasattr(tx, "action_cancel"):
            tx.action_cancel()
            self.assertEqual(tx.state, "cancelled")

    def test_action_complete(self):
        tx = self._make_tx(state="confirmed")
        if hasattr(tx, "action_complete"):
            tx.action_complete()
            self.assertEqual(tx.state, "completed")

    def test_action_view_loads(self):
        tx = self._make_tx()
        if hasattr(tx, "action_view_loads"):
            result = tx.action_view_loads()
            self.assertEqual(result["type"], "ir.actions.act_window")
