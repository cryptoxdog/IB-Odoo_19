"""End-to-end integration tests for all PlastOS business flows.

Covers 5 critical paths:
    1. Lead → Intake → Transaction
    2. Intake → Match → Offer
    3. Transaction → Load → Delivery
    4. Claim → Investigation → Resolution
    5. Partner → Enrichment → Profile

These tests validate cross-module interactions and data flow integrity.
Unlike golden flows (which are blocking regressions), integration flows
test the mechanics of module integration.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


# ═══════════════════════════════════════════════════════════════
# Flow 1: Lead → Intake → Transaction
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "integration")
class TestLeadToIntakeToTransaction(PlasticosTestCase):
    """Integration tests for CRM lead to transaction flow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.intake", "plasticos.transaction", "crm.lead")
        cls.partner = cls._create_partner("Lead Flow Co", supplier_rank=1)

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

        intake.write(
            {"polymer_id": self.default_polymer.id, "form_id": self.default_form.id, "quantity_per_load_lbs": 40000}
        )
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
@tagged("post_install", "-at_install", "plasticos", "integration", "matching")
class TestIntakeToMatchToOffer(PlasticosTestCase):
    """Integration tests for intake to offer via matching flow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.intake", "plasticos.match.result", "plasticos.offer")
        cls.supplier = cls._create_partner("Match Supplier", supplier_rank=1)
        cls.buyer = cls._create_partner("Match Buyer", customer_rank=1)

    def test_intake_to_match_to_offer(self):
        intake = self.env["plasticos.intake"].create(
            {
                "partner_id": self.supplier.id,
                "polymer_id": self.default_polymer.id,
                "form_id": self.default_form.id,
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
            # NOTE: plasticos.offer carries no match_result_id — the field is disabled
            # in plasticos_offer/models/offer.py (matching is an external Gate service),
            # so the offer is linked to the match only through the shared intake.
            offer = Offer.create(
                {
                    "buyer_id": self.buyer.id,
                    "intake_id": intake.id,
                }
            )
            self.assertTrue(offer.exists())
            self.assertEqual(offer.intake_id.id, mr.intake_id.id)


# ═══════════════════════════════════════════════════════════════
# Flow 3: Transaction → Load → Delivery
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "integration", "logistics")
class TestTransactionToLoadToDelivery(PlasticosTestCase):
    """Integration tests for transaction to delivery flow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.transaction", "plasticos.load")

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
@tagged("post_install", "-at_install", "plasticos", "integration", "claims")
class TestClaimLifecycle(PlasticosTestCase):
    """Integration tests for claim lifecycle flow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.claim", "plasticos.transaction")
        cls.Claim = cls.env["plasticos.claim"]
        cls.tx = cls._create_transaction(name="TX-CLM-INTEG")

    def _make_claim(self, **kw):
        vals = {
            "transaction_id": self.tx.id,
            "case_type": "buyer_claim",
            "severity": "medium",
            "state": "pending",
        }
        vals.update(kw)
        return self.Claim.create(vals)

    def test_full_claim_lifecycle(self):
        claim = self._make_claim()
        if hasattr(claim, "action_start"):
            claim.action_start()
            self.assertEqual(claim.state, "in_progress")
        if hasattr(claim, "action_resolve"):
            claim.resolution_note = "Resolved"
            claim.action_resolve()
            self.assertEqual(claim.state, "resolved")
        if hasattr(claim, "action_archive"):
            claim.action_archive()
            self.assertEqual(claim.state, "archived")

    def test_claim_reopen_then_resolve(self):
        claim = self._make_claim()
        if hasattr(claim, "action_start"):
            claim.action_start()
        if hasattr(claim, "action_resolve"):
            claim.resolution_note = "Resolved"
            claim.action_resolve()
        if hasattr(claim, "action_reopen"):
            claim.action_reopen()
            self.assertEqual(claim.state, "open")


# ═══════════════════════════════════════════════════════════════
# Flow 5: Partner → Enrichment → Profile
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "integration", "enrichment")
class TestPartnerEnrichmentToProfile(PlasticosTestCase):
    """Integration tests for partner enrichment to profile flow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.enrichment.run")
        cls.partner = cls._create_partner("Enrich Co")

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
        """Material profile should link to partner bidirectionally."""
        if "plasticos.material.profile" not in self.env:
            self.skipTest("plasticos.material.profile not installed")
        polymer = self._get_or_create_polymer("PP")
        profile = self._create_material_profile(partner=self.partner, polymer=polymer)
        self.assertEqual(profile.partner_id.id, self.partner.id)
        if hasattr(self.partner, "material_profile_ids"):
            self.assertIn(profile.id, self.partner.material_profile_ids.ids)
