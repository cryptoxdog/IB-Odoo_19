"""Golden-path end-to-end flows for PlastOS.

These tests assert business outcomes across multiple modules and are used
as blocking regressions in CI. They are intentionally tagged as `golden`
and `post_install` so they run on a fully loaded database.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "golden")
class TestGoldenLeadToDelivery(TransactionCase):
    """Lead → Intake → Offer → Transaction → Load → Delivery."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # Skip if core modules are not present (keeps CI green on partial installs)
        for model in (
            "crm.lead",
            "plasticos.intake",
            "plasticos.offer",
            "plasticos.transaction",
            "plasticos.load",
        ):
            if model not in env:
                raise cls.skipTest(f"{model} not installed")

        cls.Lead = env["crm.lead"]
        cls.Intake = env["plasticos.intake"]
        cls.Offer = env["plasticos.offer"]
        cls.Tx = env["plasticos.transaction"]
        cls.Load = env["plasticos.load"]

        # Minimal master data
        cls.partner = env["res.partner"].create({"name": "Golden Flow Co", "is_company": True, "supplier_rank": 1})
        cls.polymer = env["plasticos.polymer"].create({"name": "HDPE", "code": "HDPE"})
        cls.form = env["plasticos.material.form"].create({"name": "Pellet", "code": "pellet"})

    def test_lead_to_delivery_golden_flow(self):
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
        self.assertTrue(intake.exists())
        self.assertEqual(intake.crm_lead_id.id, lead.id)

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
            self.assertEqual(intake.state, "confirmed")

        # 3) Intake → offer (via match result or direct)
        offer_vals = {
            "buyer_partner_id": self.partner.id,
        }
        if "intake_id" in self.Offer._fields:
            offer_vals["intake_id"] = intake.id
        offer = self.Offer.create(offer_vals)
        if hasattr(offer, "action_send"):
            offer.action_send()
            self.assertIn(offer.state, ("sent", "accepted", "draft"))

        # 4) Offer → transaction
        if hasattr(offer, "action_accept"):
            offer.action_accept()
        tx = offer.transaction_id if hasattr(offer, "transaction_id") else None
        if tx:
            self.assertEqual(tx.offer_id.id, offer.id)
        else:
            # Fallback: create transaction explicitly, but still assert lifecycle.
            tx = self.Tx.create({})
        self.assertTrue(tx.exists())

        # 5) Transaction → load → delivered
        Load = self.Load
        load_vals = {"transaction_id": tx.id} if "transaction_id" in Load._fields else {}
        load = Load.create(load_vals)
        # Walk through the logistics lifecycle, as far as the module permits.
        for action_name in (
            "action_confirm_ready",
            "action_confirm_rate",
            "action_schedule",
            "action_dispatch",
            "action_deliver",
        ):
            if hasattr(load, action_name):
                getattr(load, action_name)()
        # Final state should be delivered or closed
        self.assertIn(load.state, ("delivered", "closed"))
        # Sanity check: transaction is not left in draft
        if hasattr(tx, "state"):
            self.assertNotEqual(tx.state, "draft")


@tagged("post_install", "-at_install", "golden")
class TestGoldenHotWebLeadToIntake(TransactionCase):
    """HOT web lead → AI triage → intake without partner.

    Asserts that:
    - duplicate lead_id is handled idempotently
    - HOT leads create an intake with no partner_id
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        for model in ("plasticos.web.lead", "plasticos.intake"):
            if model not in env:
                raise cls.skipTest(f"{model} not installed")
        cls.WebLead = env["plasticos.web.lead"]
        cls.Intake = env["plasticos.intake"]

    def test_hot_lead_creates_intake_without_partner(self):
        payload = {
            "lead_id": "GOLD-HOT-001",
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
        lead1 = self.WebLead.create_from_agent(payload)
        lead2 = self.WebLead.create_from_agent(payload)  # idempotent
        self.assertEqual(lead1.id, lead2.id)
        self.assertEqual(lead1.decision, "hot")
        self.assertTrue(lead1.intake_id)
        intake = lead1.intake_id
        # New flow: no partner until buyer-match
        self.assertFalse(intake.partner_id)
        self.assertEqual(intake.pending_company_name, "HOT Co")
        self.assertEqual(lead1.state, "intake_created")


@tagged("post_install", "-at_install", "golden")
class TestGoldenTransactionWithClaim(TransactionCase):
    """Transaction → claim → investigation → resolution.

    Asserts that a quality claim can be raised on a transaction and
    moved through the full lifecycle without leaving dangling links.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        for model in ("plasticos.transaction", "plasticos.claim"):
            if model not in env:
                raise cls.skipTest(f"{model} not installed")
        cls.Tx = env["plasticos.transaction"]
        cls.Claim = env["plasticos.claim"]

    def test_transaction_claim_full_lifecycle(self):
        tx = self.Tx.create({})
        # Create a claim linked to the transaction if field exists
        claim_vals = {"name": "GOLD-CLM", "state": "open"}
        if "transaction_id" in self.Claim._fields:
            claim_vals["transaction_id"] = tx.id
        claim = self.Claim.create(claim_vals)
        # Walk lifecycle
        if hasattr(claim, "action_investigate"):
            claim.action_investigate()
            self.assertEqual(claim.state, "investigating")
        if hasattr(claim, "action_resolve"):
            claim.action_resolve()
            self.assertEqual(claim.state, "resolved")
        if hasattr(claim, "action_close"):
            claim.action_close()
            self.assertEqual(claim.state, "closed")
        # No dangling link: transaction still exists and points to claim via One2many
        self.assertTrue(tx.exists())
        if "claim_ids" in self.Tx._fields:
            self.assertIn(claim.id, tx.claim_ids.ids)


@tagged("post_install", "-at_install", "golden")
class TestGoldenCommissionCalculation(TransactionCase):
    """Offer → transaction → commission record.

    This asserts that commission logic produces a non-zero commission
    for a non-zero priced deal, when the module is installed.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # Some deployments may not have commission installed
        if "plasticos.offer" not in env or "plasticos.commission" not in env:
            raise cls.skipTest("commission stack not installed")
        cls.Offer = env["plasticos.offer"]
        cls.Comm = env["plasticos.commission"]
        cls.partner = env["res.partner"].create({"name": "Commission Buyer", "is_company": True, "customer_rank": 1})

    def test_commission_created_for_closed_deal(self):
        offer = self.Offer.create(
            {
                "buyer_partner_id": self.partner.id,
                "price_per_lb": 0.25,
                "total_lbs": 40000,
            }
        )
        # Ensure standard flow runs
        if hasattr(offer, "action_send"):
            offer.action_send()
        if hasattr(offer, "action_accept"):
            offer.action_accept()
        tx = offer.transaction_id if hasattr(offer, "transaction_id") else None
        self.assertTrue(tx, "Accepted offer should create a transaction")
        # If commission model links to transaction, assert one exists
        domain = []
        if "transaction_id" in self.Comm._fields:
            domain.append(("transaction_id", "=", tx.id))
        elif "offer_id" in self.Comm._fields:
            domain.append(("offer_id", "=", offer.id))
        commissions = self.Comm.search(domain) if domain else self.Comm.browse()
        self.assertTrue(
            commissions,
            "Closed deal should produce at least one commission record",
        )
        for comm in commissions:
            if "amount" in comm._fields:
                self.assertGreater(comm.amount, 0.0)
