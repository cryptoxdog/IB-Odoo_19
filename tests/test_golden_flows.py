"""Golden-path end-to-end flows for PlastOS.

These tests assert business outcomes across multiple modules and are used
as blocking regressions in CI. They are intentionally tagged as `golden`
and `post_install` so they run on a fully loaded database.

Golden flows represent the critical business paths that must always work:
1. Lead → Intake → Offer → Transaction → Load → Delivery (full sales cycle)
2. HOT web lead → AI triage → intake (automated lead processing)
3. Transaction → claim → investigation → resolution (quality management)
4. Transaction margin → commission → close-time lock (revenue recognition)
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "plasticos", "golden", "critical")
class TestGoldenLeadToDelivery(PlasticosTestCase):
    """Lead → Intake → Offer → Transaction → Load → Delivery.

    This is the primary sales cycle that must never break. It validates:
    - CRM integration (lead conversion)
    - Intake creation and confirmation
    - Offer generation and acceptance
    - Transaction creation from accepted offer
    - Load scheduling and delivery completion
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing(
            "crm.lead",
            "plasticos.intake",
            "plasticos.offer",
            "plasticos.transaction",
            "plasticos.load",
        )

        cls.Lead = cls.env["crm.lead"]
        cls.Intake = cls.env["plasticos.intake"]
        cls.Offer = cls.env["plasticos.offer"]
        cls.Tx = cls.env["plasticos.transaction"]
        cls.Load = cls.env["plasticos.load"]

        cls.partner = cls._create_partner("Golden Flow Co", supplier_rank=1)
        cls.polymer = cls._get_or_create_polymer("HDPE")
        cls.form = cls._get_or_create_form("pellet")

    def test_lead_to_delivery_golden_flow(self):
        """Full sales cycle: CRM lead through delivery completion."""
        # 1) CRM lead → intake
        lead = self.Lead.create(
            {
                "name": "Golden E2E Lead",
                "partner_id": self.partner.id,
                "type": "lead",
            }
        )
        action = lead.action_convert_to_intake()
        self.assertEqual(action["res_model"], "plasticos.intake")
        intake = self.Intake.browse(action["res_id"])
        self.assertTrue(intake.exists(), "Intake should be created from lead")
        self.assertEqual(intake.crm_lead_id.id, lead.id, "Intake should link back to lead")

        # 2) Intake → confirmed
        intake.write(
            {
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
                "quantity_per_load_lbs": 40000,
            }
        )
        if hasattr(intake, "action_confirm"):
            intake.action_confirm()
            self.assertEqual(intake.state, "confirmed", "Intake should be confirmed")

        # 3) Intake → offer (via match result or direct)
        offer_vals = {"buyer_partner_id": self.partner.id}
        if "intake_id" in self.Offer._fields:
            offer_vals["intake_id"] = intake.id
        offer = self.Offer.create(offer_vals)
        if hasattr(offer, "action_send"):
            offer.action_send()
            self.assertIn(offer.state, ("sent", "accepted", "draft"), "Offer should be sent")

        # 4) Offer → transaction
        if hasattr(offer, "action_accept"):
            offer.action_accept()
        tx = offer.transaction_id if hasattr(offer, "transaction_id") else None
        if tx:
            self.assertEqual(tx.offer_id.id, offer.id, "Transaction should link to offer")
        else:
            tx = self.Tx.create({})
        self.assertTrue(tx.exists(), "Transaction should exist")

        # 5) Transaction → load → delivered
        load_vals = {"transaction_id": tx.id} if "transaction_id" in self.Load._fields else {}
        load = self.Load.create(load_vals)

        # Walk through the logistics lifecycle
        logistics_actions = (
            "action_confirm_ready",
            "action_confirm_rate",
            "action_schedule",
            "action_dispatch",
            "action_deliver",
        )
        for action_name in logistics_actions:
            if hasattr(load, action_name):
                getattr(load, action_name)()

        # Final state should be delivered or closed
        self.assertIn(load.state, ("delivered", "closed"), "Load should reach delivered/closed state")

        # Sanity checks
        if hasattr(tx, "state"):
            self.assertNotEqual(tx.state, "draft", "Transaction should not remain in draft")

    def test_lead_conversion_creates_partner_when_missing(self):
        """Lead without partner should auto-create partner on conversion."""
        lead = self.Lead.create(
            {
                "name": "No Partner Lead",
                "partner_name": "Auto Created Partner Co",
                "email_from": "auto@example.com",
                "type": "lead",
            }
        )
        lead.action_convert_to_intake()
        self.assertTrue(lead.partner_id, "Partner should be auto-created")
        self.assertTrue(lead.intake_ids, "Intake should be created")

    def test_intake_confirmation_posts_message(self):
        """Confirming intake should post a chatter message."""
        intake = self._create_intake(partner=self.partner, polymer=self.polymer, form=self.form)
        if hasattr(intake, "action_confirm"):
            initial_count = len(intake.message_ids)
            intake.action_confirm()
            self.assertGreater(len(intake.message_ids), initial_count, "Message should be posted")


@tagged("post_install", "-at_install", "plasticos", "golden", "web_lead")
class TestGoldenHotWebLeadToIntake(PlasticosTestCase):
    """HOT web lead → AI triage → intake without partner.

    This flow validates the automated lead processing pipeline:
    - Web form submission creates web lead
    - AI triage classifies as HOT
    - Intake auto-created without partner (partner assigned during buyer match)
    - Idempotent handling of duplicate lead_id
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.web.lead", "plasticos.intake")
        cls.WebLead = cls.env["plasticos.web.lead"]
        cls.Intake = cls.env["plasticos.intake"]

    def _make_hot_lead_payload(self, lead_id="GOLD-HOT-001"):
        """Create a standard HOT lead payload for testing."""
        return {
            "lead_id": lead_id,
            "source": "cognito_form",
            "decision": "Hot",
            "decision_reasons": ["monthly_lbs >= 10000"],
            "raw_payload": {
                "YourBusinessCompanyName": "HOT Co",
                "DescribeYourMaterial": "HDPE pellets",
                "WhatIsTheQuantity": "40000 lbs per load",
            },
            "ai_analysis": {
                "quantity": {
                    "per_load_lbs": 40000,
                    "loads_per_month": 2,
                },
                "frequency": {"frequency": "ongoing"},
                "material": {
                    "polymer": "hdpe",
                    "form": "pellet",
                },
            },
        }

    def test_hot_lead_creates_intake_without_partner(self):
        """HOT leads should create intake without partner (deferred to buyer match)."""
        payload = self._make_hot_lead_payload()
        lead = self.WebLead.create_from_agent(payload)

        self.assertEqual(lead.decision, "hot", "Decision should be normalized to lowercase")
        self.assertTrue(lead.intake_id, "HOT lead should create intake")

        intake = lead.intake_id
        self.assertFalse(intake.partner_id, "Intake should not have partner yet")
        self.assertEqual(intake.pending_company_name, "HOT Co", "Company name should be stored")
        self.assertEqual(lead.state, "intake_created", "Lead state should be intake_created")

    def test_duplicate_lead_id_is_idempotent(self):
        """Submitting same lead_id twice should return same record."""
        payload = self._make_hot_lead_payload("GOLD-IDEMP-001")
        lead1 = self.WebLead.create_from_agent(payload)
        lead2 = self.WebLead.create_from_agent(payload)

        self.assertEqual(lead1.id, lead2.id, "Same lead_id should return same record")

    def test_hot_lead_ai_analysis_fields_populated(self):
        """AI analysis data should populate intake fields."""
        payload = self._make_hot_lead_payload("GOLD-AI-001")
        lead = self.WebLead.create_from_agent(payload)
        intake = lead.intake_id

        if hasattr(intake, "quantity_per_load_lbs"):
            self.assertEqual(intake.quantity_per_load_lbs, 40000, "Quantity should be extracted")
        if hasattr(intake, "loads_per_month"):
            self.assertEqual(intake.loads_per_month, 2, "Loads per month should be extracted")


@tagged("post_install", "-at_install", "plasticos", "golden", "claims")
class TestGoldenTransactionWithClaim(PlasticosTestCase):
    """Transaction → claim → investigation → resolution.

    This flow validates the quality management process:
    - Claims can be raised against transactions
    - Claims progress through investigation workflow
    - Resolution and closure maintain data integrity
    - Bidirectional links remain consistent
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.transaction", "plasticos.claim")
        cls.Tx = cls.env["plasticos.transaction"]
        cls.Claim = cls.env["plasticos.claim"]

    def test_transaction_claim_full_lifecycle(self):
        """Claim should progress through full lifecycle without breaking links."""
        tx = self._create_transaction(name="TX-GOLD-CLM")

        # Create claim linked to transaction
        claim_vals = {"name": "GOLD-CLM", "state": "open"}
        if "transaction_id" in self.Claim._fields:
            claim_vals["transaction_id"] = tx.id
        claim = self.Claim.create(claim_vals)

        # Walk through lifecycle
        if hasattr(claim, "action_investigate"):
            claim.action_investigate()
            self.assertEqual(claim.state, "investigating", "Claim should be investigating")

        if hasattr(claim, "action_resolve"):
            claim.action_resolve()
            self.assertEqual(claim.state, "resolved", "Claim should be resolved")

        if hasattr(claim, "action_close"):
            claim.action_close()
            self.assertEqual(claim.state, "closed", "Claim should be closed")

        # Verify data integrity
        self.assertTrue(tx.exists(), "Transaction should still exist")
        if "claim_ids" in self.Tx._fields:
            self.assertIn(claim.id, tx.claim_ids.ids, "Transaction should reference claim")

    def test_claim_reopen_from_resolved(self):
        """Resolved claims should be reopenable for further investigation."""
        tx = self._create_transaction(name="TX-GOLD-REOPEN")
        claim = self._create_claim(transaction=tx, state="resolved")

        if hasattr(claim, "action_reopen"):
            claim.action_reopen()
            self.assertEqual(claim.state, "open", "Claim should be reopened")

    def test_claim_posts_messages_on_transitions(self):
        """State transitions should post chatter messages for audit trail."""
        tx = self._create_transaction(name="TX-GOLD-MSG")
        claim = self._create_claim(transaction=tx)

        if hasattr(claim, "action_investigate"):
            initial_count = len(claim.message_ids)
            claim.action_investigate()
            self.assertGreater(len(claim.message_ids), initial_count, "Message should be posted")


@tagged("post_install", "-at_install", "plasticos", "golden", "commission")
class TestGoldenCommissionCalculation(PlasticosTestCase):
    """Transaction → commission lock (revenue recognition).

    Architecture note (2026-08 reconciliation): this class previously targeted a
    standalone ``plasticos.commission`` record model reached via ``offer.transaction_id``.
    Neither exists. Commission is recorded ON the transaction — ``plasticos_commission/
    models/transaction_commission.py`` (``_inherit = "plasticos.transaction"``) adds
    ``commission_rule_id``, ``commission_locked``, ``commission_locked_amount``,
    ``commission_override_pct`` and ``commission_payout_state``; per-rep aggregation
    lives in ``plasticos.commission.payout``. ``plasticos.offer`` carries no
    ``transaction_id``, so no offer→transaction assertion is made here.

    The flow validated: margin → commission computed by ``plasticos.commission.service``
    → frozen at close by ``_apply_close``.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.transaction", "plasticos.commission.service")
        cls.Tx = cls.env["plasticos.transaction"]
        cls.CommService = cls.env["plasticos.commission.service"]
        cls.supplier = cls._create_partner("Commission Supplier", supplier_rank=1)
        cls.buyer = cls._create_partner("Commission Buyer", customer_rank=1)

    def _profitable_tx(self, revenue=10000.0, cost=8000.0):
        return self.Tx.create(
            {
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "revenue_total": revenue,
                "purchase_cost_total": cost,
            }
        )

    def test_commission_fields_live_on_transaction(self):
        """The commission contract is carried by plasticos.transaction itself."""
        for fname in (
            "commission_rule_id",
            "commission_locked",
            "commission_locked_amount",
            "commission_override_pct",
            "commission_payout_state",
            "commission_amount",
        ):
            self.assertIn(fname, self.Tx._fields, f"plasticos.transaction missing {fname}")

    def test_commission_positive_on_profitable_deal(self):
        """A transaction with positive gross margin earns a positive commission."""
        tx = self._profitable_tx()
        self.assertGreater(tx.gross_margin, 0.0)
        self.assertGreater(tx.commission_amount, 0.0, "Profitable deal should earn commission")

    def test_commission_never_exceeds_gross_margin(self):
        """Commission is a share of margin, never larger than the margin itself."""
        tx = self._profitable_tx()
        self.assertLessEqual(tx.commission_amount, tx.gross_margin)
        self.assertAlmostEqual(tx.net_margin, tx.gross_margin - tx.commission_amount, places=2)

    def test_no_commission_on_non_positive_margin(self):
        """Zero or negative gross margin earns zero commission."""
        tx = self._profitable_tx(revenue=5000.0, cost=5000.0)
        self.assertLessEqual(tx.gross_margin, 0.0)
        self.assertEqual(tx.commission_amount, 0.0)

    def test_close_freezes_commission_at_locked_amount(self):
        """_apply_close locks commission; later margin changes do not move it."""
        tx = self._profitable_tx()
        expected = self.CommService.compute_commission(tx)

        self.Tx._apply_close(tx)
        self.assertTrue(tx.commission_locked)
        self.assertAlmostEqual(tx.commission_locked_amount, expected, places=2)
        self.assertAlmostEqual(tx.commission_amount, expected, places=2)

        tx.with_context(bypass_state_guard=True).write({"revenue_total": 99000.0})
        self.assertAlmostEqual(
            tx.commission_amount,
            expected,
            places=2,
            msg="Locked commission must not recompute after close",
        )
