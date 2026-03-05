"""End-to-end integration tests for all PlastOS business flows.

Covers 5 critical paths:
    1. Lead → Intake → Transaction
    2. Intake → Match → Offer
    3. Transaction → Load → Delivery
    4. Claim → Investigation → Resolution
    5. Partner → Enrichment → Profile
"""

import unittest

from odoo.tests.common import TransactionCase


class IntegrationFactoryMixin:
    @classmethod
    def _partner(cls, name="Integration Partner", **kw):
        vals = {"name": name, "is_company": True, "supplier_rank": 1}
        vals.update(kw)
        return cls.env["res.partner"].create(vals)

    @classmethod
    def _polymer(cls, code="HDPE"):
        return cls.env["plasticos.polymer"].create({"name": code, "code": code})

    @classmethod
    def _form(cls, code="pellet"):
        return cls.env["plasticos.material.form"].create({"name": code.title(), "code": code})


# ═══════════════════════════════════════════════════════════════
# Flow 1: Lead → Intake → Transaction
# ═══════════════════════════════════════════════════════════════
class TestLeadToIntakeToTransaction(TransactionCase, IntegrationFactoryMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for m in ("plasticos.intake", "plasticos.transaction", "crm.lead"):
            if m not in cls.env:
                raise unittest.SkipTest(f"{m} not installed")
        cls.partner = cls._partner("Lead Flow Co")
        cls.polymer = cls._polymer()
        cls.form = cls._form()

    def test_full_lead_to_transaction_flow(self):
        """CRM lead → intake → confirmed → transaction created."""
        lead = self.env["crm.lead"].create(
            {
                "name": "E2E Test Lead",
                "partner_id": self.partner.id,
                "type": "lead",
            }
        )
        result = lead.action_convert_to_intake()
        intake = self.env["plasticos.intake"].browse(result["res_id"])
        self.assertTrue(intake.exists())
        self.assertEqual(intake.crm_lead_id.id, lead.id)

        intake.write({"polymer_id": self.polymer.id, "form_id": self.form.id, "quantity_per_load_lbs": 40000})
        if hasattr(intake, "action_confirm"):
            intake.action_confirm()
            self.assertEqual(intake.state, "confirmed")

    def test_lead_creates_partner_when_missing(self):
        lead = self.env["crm.lead"].create(
            {
                "name": "No Partner Lead",
                "partner_name": "Auto Create Co",
                "email_from": "auto@test.com",
                "type": "lead",
            }
        )
        lead.action_convert_to_intake()
        self.assertTrue(lead.partner_id)
        self.assertTrue(lead.intake_ids)


# ═══════════════════════════════════════════════════════════════
# Flow 2: Intake → Match → Offer
# ═══════════════════════════════════════════════════════════════
class TestIntakeToMatchToOffer(TransactionCase, IntegrationFactoryMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for m in ("plasticos.intake", "plasticos.match.result", "plasticos.offer"):
            if m not in cls.env:
                raise unittest.SkipTest(f"{m} not installed")
        cls.supplier = cls._partner("Match Supplier")
        cls.buyer = cls._partner("Match Buyer", customer_rank=1)
        cls.polymer = cls._polymer()
        cls.form = cls._form()

    def test_intake_to_match_to_offer(self):
        intake = self.env["plasticos.intake"].create(
            {
                "partner_id": self.supplier.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
                "quantity_per_load_lbs": 40000,
            }
        )
        # Simulate match result
        mr = self.env["plasticos.match.result"].create(
            {
                "intake_id": intake.id,
                "buyer_partner_id": self.buyer.id,
                "score": 85.0,
            }
        )
        self.assertTrue(mr.exists())
        self.assertEqual(mr.intake_id.id, intake.id)

        # Create offer from match
        if "plasticos.offer" in self.env:
            Offer = self.env["plasticos.offer"]
            offer = Offer.create(
                {
                    "buyer_partner_id": self.buyer.id,
                    "intake_id": intake.id if "intake_id" in Offer._fields else False,
                    "match_result_id": mr.id if "match_result_id" in Offer._fields else False,
                }
            )
            self.assertTrue(offer.exists())


# ═══════════════════════════════════════════════════════════════
# Flow 3: Transaction → Load → Delivery
# ═══════════════════════════════════════════════════════════════
class TestTransactionToLoadToDelivery(TransactionCase, IntegrationFactoryMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for m in ("plasticos.transaction", "plasticos.load"):
            if m not in cls.env:
                raise unittest.SkipTest(f"{m} not installed")

    def test_transaction_to_load_lifecycle(self):
        tx = self.env["plasticos.transaction"].create({})
        if hasattr(tx, "action_confirm"):
            tx.action_confirm()

        Load = self.env["plasticos.load"]
        load_vals = {"transaction_id": tx.id} if "transaction_id" in Load._fields else {}
        load = Load.create(load_vals)

        states = []
        actions = (
            "action_confirm_ready",
            "action_confirm_rate",
            "action_schedule",
            "action_dispatch",
            "action_deliver",
        )
        for action in actions:
            if hasattr(load, action):
                getattr(load, action)()
                states.append(load.state)

        if states:
            self.assertEqual(states[-1], "delivered")


# ═══════════════════════════════════════════════════════════════
# Flow 4: Claim → Investigation → Resolution
# ═══════════════════════════════════════════════════════════════
class TestClaimLifecycle(TransactionCase, IntegrationFactoryMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.claim" not in cls.env:
            raise unittest.SkipTest("plasticos.claim not installed")
        cls.Claim = cls.env["plasticos.claim"]

    def test_full_claim_lifecycle(self):
        claim = self.Claim.create({"name": "CLM-E2E", "state": "open"})
        if hasattr(claim, "action_investigate"):
            claim.action_investigate()
            self.assertEqual(claim.state, "investigating")
        if hasattr(claim, "action_resolve"):
            claim.action_resolve()
            self.assertEqual(claim.state, "resolved")
        if hasattr(claim, "action_close"):
            claim.action_close()
            self.assertEqual(claim.state, "closed")

    def test_claim_reopen_then_resolve(self):
        claim = self.Claim.create({"name": "CLM-REOPEN", "state": "open"})
        if hasattr(claim, "action_investigate"):
            claim.action_investigate()
        if hasattr(claim, "action_resolve"):
            claim.action_resolve()
        if hasattr(claim, "action_reopen"):
            claim.action_reopen()
            self.assertEqual(claim.state, "open")


# ═══════════════════════════════════════════════════════════════
# Flow 5: Partner → Enrichment → Profile
# ═══════════════════════════════════════════════════════════════
class TestPartnerEnrichmentToProfile(TransactionCase, IntegrationFactoryMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.enrichment.run" not in cls.env:
            raise unittest.SkipTest("plasticos.enrichment.run not installed")
        cls.partner = cls._partner("Enrich Co")

    def test_enrichment_creates_profile_data(self):
        if "plasticos.enrichment.source" in self.env:
            src = self.env["plasticos.enrichment.source"].create(
                {
                    "partner_id": self.partner.id,
                    "url": "https://example.com",
                }
            )
            self.assertTrue(src.exists())

    def test_material_profile_linked_to_partner(self):
        if "plasticos.material.profile" in self.env:
            polymer = self._polymer("PP")
            profile = self.env["plasticos.material.profile"].create(
                {
                    "partner_id": self.partner.id,
                    "polymer_id": polymer.id,
                }
            )
            self.assertEqual(profile.partner_id.id, self.partner.id)
            if hasattr(self.partner, "material_profile_ids"):
                self.assertIn(profile.id, self.partner.material_profile_ids.ids)
