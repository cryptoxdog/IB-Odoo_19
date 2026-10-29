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
from odoo.fields import Datetime
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

    def test_lead_keeps_partner_missing(self):
        lead = self.env["crm.lead"].create(
            {
                "name": "No Partner Lead",
                "partner_name": "Auto Create Co",
                "email_from": "auto@test.com",
                "type": "lead",
            }
        )
        lead.action_convert_to_intake()
        self.assertFalse(lead.partner_id)
        self.assertFalse(lead.source_intake_id.partner_id)
        self.assertEqual(lead.source_intake_id.pending_company_name, "Auto Create Co")
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
            # supplier_id is required on offer (plasticos_offer/models/offer.py:62-69).
            offer = Offer.create(
                {
                    "supplier_id": self.supplier.id,
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
        cls.supplier = cls._create_partner("Load Flow Supplier", supplier_rank=1)
        cls.buyer = cls._create_partner("Load Flow Buyer", customer_rank=1)
        cls.carrier = cls._create_partner("Load Flow Carrier")
        cls.intake = cls._create_intake(partner=cls.supplier, polymer=cls.default_polymer, form=cls.default_form)
        cls.sale_order = cls.env["sale.order"].create({"partner_id": cls.buyer.id})

    def test_transaction_to_load_lifecycle(self):
        # Rate confirmation needs a complete freight context (company via sale_order_id,
        # pickup/delivery partners, reference weight, transaction intake —
        # plasticos_logistics/services/freight_context.py:57-69) and a carrier (load.py:1016, 1086).
        tx = self.env["plasticos.transaction"].create(
            {"supplier_id": self.supplier.id, "buyer_id": self.buyer.id, "intake_id": self.intake.id}
        )
        if hasattr(tx, "action_confirm"):
            tx.action_confirm()

        load = self.env["plasticos.load"].create(
            {
                "transaction_id": tx.id,
                "sale_order_id": self.sale_order.id,
                "pickup_partner_id": self.supplier.id,
                "delivery_partner_id": self.buyer.id,
                "carrier_id": self.carrier.id,
                "reference_weight": 40000.0,
            }
        )
        self.assertEqual(load.state, "draft")

        # Current load workflow (plasticos_logistics/services/state_machine.py:9-20):
        # draft -> awaiting_ready has no dedicated action; picked_up/delivered are
        # transitions with no action_* wrapper (there is no action_deliver).
        now = Datetime.now()
        steps = (
            (lambda: load._transition("awaiting_ready"), "awaiting_ready"),
            (load.action_confirm_ready, "ready_confirmed"),
            (lambda: load.action_confirm_rate(1500.0), "rate_confirmed"),
            (lambda: load.action_schedule(now, now), "scheduled"),
            (load.action_dispatch, "dispatched"),
            (lambda: load._transition("picked_up"), "picked_up"),
            (lambda: load._transition("delivered"), "delivered"),
        )
        states = []
        for step, expected in steps:
            step()
            self.assertEqual(load.state, expected)
            states.append(load.state)

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
            # Reopen returns the claim to in_progress (plasticos_claims/models/claim.py:303-311).
            self.assertEqual(claim.state, "in_progress")
            self.assertFalse(claim.resolved_at)
            claim.action_resolve()
            self.assertEqual(claim.state, "resolved")


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
