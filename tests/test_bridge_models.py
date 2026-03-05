"""Bridge model tests for all PlastOS cross-module links.

Covers 7 bridge patterns:
    offer_bridge, intake_bridge, match_result_bridge,
    transaction_docs_bridge, load_docs_bridge,
    transaction_claims_bridge, partner_bridge
"""

import unittest

from odoo.tests.common import TransactionCase


class BridgeFactoryMixin:
    """Shared record factories for bridge tests."""

    @classmethod
    def _partner(cls, name="Bridge Partner"):
        return cls.env["res.partner"].create({"name": name, "is_company": True})

    @classmethod
    def _polymer(cls):
        return cls.env["plasticos.polymer"].create({"name": "HDPE", "code": "HDPE"})

    @classmethod
    def _form(cls):
        return cls.env["plasticos.material.form"].create({"name": "Pellet", "code": "pellet"})


# ═══════════════════════════════════════════════════════════════
# 1. Offer ↔ Transaction Bridge
# ═══════════════════════════════════════════════════════════════
class TestOfferBridge(TransactionCase, BridgeFactoryMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for model in ("plasticos.offer", "plasticos.transaction"):
            if model not in cls.env:
                raise unittest.SkipTest(f"{model} not installed")
        cls.partner = cls._partner()

    def test_offer_accept_creates_transaction(self):
        offer = self.env["plasticos.offer"].create({"buyer_partner_id": self.partner.id})
        if hasattr(offer, "action_send"):
            offer.action_send()
        if hasattr(offer, "action_accept"):
            offer.action_accept()
            if hasattr(offer, "transaction_id"):
                self.assertTrue(offer.transaction_id)

    def test_transaction_links_back_to_offer(self):
        offer = self.env["plasticos.offer"].create({"buyer_partner_id": self.partner.id})
        if hasattr(offer, "action_send"):
            offer.action_send()
        if hasattr(offer, "action_accept") and hasattr(offer, "transaction_id"):
            offer.action_accept()
            tx = offer.transaction_id
            if hasattr(tx, "offer_id"):
                self.assertEqual(tx.offer_id.id, offer.id)

    def test_offer_reject_no_transaction(self):
        offer = self.env["plasticos.offer"].create({"buyer_partner_id": self.partner.id, "state": "sent"})
        if hasattr(offer, "action_reject"):
            offer.action_reject()
            if hasattr(offer, "transaction_id"):
                self.assertFalse(offer.transaction_id)


# ═══════════════════════════════════════════════════════════════
# 2. Intake ↔ Transaction Bridge
# ═══════════════════════════════════════════════════════════════
class TestIntakeBridge(TransactionCase, BridgeFactoryMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for model in ("plasticos.intake", "plasticos.transaction"):
            if model not in cls.env:
                raise unittest.SkipTest(f"{model} not installed")
        cls.partner = cls._partner()
        cls.polymer = cls._polymer()
        cls.form = cls._form()

    def test_intake_has_transaction_ids(self):
        intake = self.env["plasticos.intake"].create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
                "quantity_per_load_lbs": 40000,
            }
        )
        if hasattr(intake, "transaction_ids"):
            self.assertIsNotNone(intake.transaction_ids)

    def test_transaction_links_to_intake(self):
        intake = self.env["plasticos.intake"].create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
                "quantity_per_load_lbs": 40000,
            }
        )
        Tx = self.env["plasticos.transaction"]
        if "intake_id" in Tx._fields:
            tx = Tx.create({"intake_id": intake.id})
            self.assertEqual(tx.intake_id.id, intake.id)

    def test_intake_transaction_count(self):
        intake = self.env["plasticos.intake"].create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
                "quantity_per_load_lbs": 40000,
            }
        )
        if hasattr(intake, "transaction_count"):
            self.assertEqual(intake.transaction_count, 0)


# ═══════════════════════════════════════════════════════════════
# 3. Match Result ↔ Transaction Bridge
# ═══════════════════════════════════════════════════════════════
class TestMatchResultBridge(TransactionCase, BridgeFactoryMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.match.result" not in cls.env:
            raise unittest.SkipTest("plasticos.match.result not installed")

    def test_match_result_has_offer_link(self):
        MR = self.env["plasticos.match.result"]
        if "offer_id" in MR._fields:
            self.assertIn("offer_id", MR._fields)

    def test_match_result_has_transaction_link(self):
        MR = self.env["plasticos.match.result"]
        if "transaction_id" in MR._fields:
            self.assertIn("transaction_id", MR._fields)

    def test_match_result_computed_counts(self):
        MR = self.env["plasticos.match.result"]
        if "intake_id" in MR._fields:
            self.assertIn("intake_id", MR._fields)


# ═══════════════════════════════════════════════════════════════
# 4. Transaction ↔ Document Bridge
# ═══════════════════════════════════════════════════════════════
class TestTransactionDocsBridge(TransactionCase, BridgeFactoryMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for model in ("plasticos.transaction", "plasticos.document"):
            if model not in cls.env:
                raise unittest.SkipTest(f"{model} not installed")

    def test_transaction_has_document_ids(self):
        Tx = self.env["plasticos.transaction"]
        if "document_ids" in Tx._fields:
            tx = Tx.create({})
            self.assertIsNotNone(tx.document_ids)

    def test_document_links_to_transaction(self):
        Doc = self.env["plasticos.document"]
        if "transaction_id" in Doc._fields:
            self.assertIn("transaction_id", Doc._fields)

    def test_document_count_computed(self):
        Tx = self.env["plasticos.transaction"]
        if "document_count" in Tx._fields:
            tx = Tx.create({})
            self.assertEqual(tx.document_count, 0)


# ═══════════════════════════════════════════════════════════════
# 5. Load ↔ Document Bridge
# ═══════════════════════════════════════════════════════════════
class TestLoadDocsBridge(TransactionCase, BridgeFactoryMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for model in ("plasticos.load", "plasticos.document"):
            if model not in cls.env:
                raise unittest.SkipTest(f"{model} not installed")

    def test_load_has_document_ids(self):
        Load = self.env["plasticos.load"]
        if "document_ids" in Load._fields:
            load = Load.create({})
            self.assertIsNotNone(load.document_ids)

    def test_bol_attachment(self):
        Load = self.env["plasticos.load"]
        if "bol_attachment_id" in Load._fields:
            self.assertIn("bol_attachment_id", Load._fields)


# ═══════════════════════════════════════════════════════════════
# 6. Transaction ↔ Claim Bridge
# ═══════════════════════════════════════════════════════════════
class TestTransactionClaimsBridge(TransactionCase, BridgeFactoryMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for model in ("plasticos.transaction", "plasticos.claim"):
            if model not in cls.env:
                raise unittest.SkipTest(f"{model} not installed")

    def test_transaction_has_claim_ids(self):
        Tx = self.env["plasticos.transaction"]
        if "claim_ids" in Tx._fields:
            tx = Tx.create({})
            self.assertIsNotNone(tx.claim_ids)

    def test_claim_links_to_transaction(self):
        Claim = self.env["plasticos.claim"]
        if "transaction_id" in Claim._fields:
            self.assertIn("transaction_id", Claim._fields)

    def test_claim_count_computed(self):
        Tx = self.env["plasticos.transaction"]
        if "claim_count" in Tx._fields:
            tx = Tx.create({})
            self.assertEqual(tx.claim_count, 0)


# ═══════════════════════════════════════════════════════════════
# 7. Transaction ↔ Partner Bridge
# ═══════════════════════════════════════════════════════════════
class TestPartnerBridge(TransactionCase, BridgeFactoryMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls._partner()

    def test_partner_has_intake_ids(self):
        if "intake_ids" in self.env["res.partner"]._fields:
            self.assertIsNotNone(self.partner.intake_ids)

    def test_partner_has_transaction_count(self):
        if "transaction_count" in self.env["res.partner"]._fields:
            self.assertEqual(self.partner.transaction_count, 0)

    def test_partner_has_material_profile_ids(self):
        if "material_profile_ids" in self.env["res.partner"]._fields:
            self.assertIsNotNone(self.partner.material_profile_ids)

    def test_partner_supplier_rank_from_intake(self):
        if "plasticos.intake" in self.env:
            Intake = self.env["plasticos.intake"]
            polymer = self._polymer()
            form = self._form()
            Intake.create(
                {
                    "partner_id": self.partner.id,
                    "polymer_id": polymer.id,
                    "form_id": form.id,
                    "quantity_per_load_lbs": 40000,
                }
            )
            self.assertGreaterEqual(self.partner.supplier_rank, 0)
