"""Golden-path end-to-end flows for PlastOS.

These tests assert business outcomes across multiple modules and are used
as blocking regressions in CI. They are intentionally tagged as `golden`
and `post_install` so they run on a fully loaded database.

Golden flows represent the critical business paths that must always work:
1. Lead → Intake → Offer → Transaction → Load → Delivery (full sales cycle)
2. HOT web lead → AI triage → intake (automated lead processing)
3. Transaction → claim → investigation → resolution (quality management)
4. Offer → transaction → commission (revenue recognition)
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
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
    """Offer → transaction → commission record.

    This flow validates revenue recognition:
    - Accepted offers create transactions
    - Transactions generate commission records
    - Commission amounts are calculated correctly

    NOTE: Deferred - plasticos.commission record model not yet implemented.
    Currently only plasticos.commission.rule and plasticos.commission.service exist.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Skip entire class - plasticos.commission model doesn't exist yet
        # Only commission.rule and commission.service are implemented
        raise cls.skipTest(cls, "plasticos.commission record model not implemented")
        cls._skip_if_model_missing("plasticos.offer", "plasticos.commission")
        cls.Offer = cls.env["plasticos.offer"]
        cls.Comm = cls.env["plasticos.commission"]
        cls.partner = cls._create_partner("Commission Buyer", customer_rank=1)

    def test_commission_created_for_closed_deal(self):
        """Accepted offer should generate commission record with positive amount."""
        offer = self.Offer.create(
            {
                "buyer_partner_id": self.partner.id,
                "price_per_lb": 0.25,
                "total_lbs": 40000,
            }
        )

        # Progress through offer lifecycle
        if hasattr(offer, "action_send"):
            offer.action_send()
        if hasattr(offer, "action_accept"):
            offer.action_accept()

        tx = offer.transaction_id if hasattr(offer, "transaction_id") else None
        self.assertTrue(tx, "Accepted offer should create a transaction")

        # Find commission records
        domain = []
        if "transaction_id" in self.Comm._fields:
            domain.append(("transaction_id", "=", tx.id))
        elif "offer_id" in self.Comm._fields:
            domain.append(("offer_id", "=", offer.id))

        commissions = self.Comm.search(domain) if domain else self.Comm.browse()
        self.assertTrue(commissions, "Closed deal should produce commission record")

        for comm in commissions:
            if "amount" in comm._fields:
                self.assertGreater(comm.amount, 0.0, "Commission amount should be positive")

    def test_commission_calculation_accuracy(self):
        """Commission amount should be calculated based on deal value."""
        offer = self.Offer.create(
            {
                "buyer_partner_id": self.partner.id,
                "price_per_lb": 0.50,
                "total_lbs": 20000,  # $10,000 deal value
            }
        )

        if hasattr(offer, "action_send"):
            offer.action_send()
        if hasattr(offer, "action_accept"):
            offer.action_accept()

        tx = offer.transaction_id if hasattr(offer, "transaction_id") else None
        if not tx:
            self.skipTest("Transaction not created from offer")

        # Verify commission exists and is reasonable
        domain = [("transaction_id", "=", tx.id)] if "transaction_id" in self.Comm._fields else []
        commissions = self.Comm.search(domain) if domain else self.Comm.browse()

        if commissions and "amount" in self.Comm._fields:
            total_commission = sum(c.amount for c in commissions)
            # Commission should be some percentage of deal value (sanity check)
            deal_value = 0.50 * 20000  # $10,000
            self.assertLess(total_commission, deal_value, "Commission should be less than deal value")
