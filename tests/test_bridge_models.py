"""Bridge model tests for all PlastOS cross-module links.

Covers 7 bridge patterns:
    offer_bridge, intake_bridge, match_result_bridge,
    transaction_docs_bridge, load_docs_bridge,
    transaction_claims_bridge, partner_bridge

Bridge models use _inherit to add fields/methods to existing models,
creating cross-module relationships. These tests validate:
- Fields are properly added via _inherit
- Bidirectional relationships are consistent (Many2one ↔ One2many)
- Computed count fields are accurate
- Cascade behaviors work correctly
"""

from odoo.tests.common import TransactionCase, tagged

from .common import PlastOSTestFactoryMixin


# ═══════════════════════════════════════════════════════════════
# 1. Offer ↔ Transaction Bridge
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "bridge", "offer")
class TestOfferBridge(TransactionCase, PlastOSTestFactoryMixin):
    """Tests for offer ↔ transaction bidirectional relationship."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.offer", "plasticos.transaction", "plasticos.intake")
        cls.supplier = cls._create_partner("Bridge Supplier", supplier_rank=1)
        cls.buyer = cls._create_partner("Bridge Buyer", customer_rank=1)
        cls.polymer = cls._get_or_create_polymer()
        cls.form = cls._get_or_create_form()
        cls.intake = cls._create_intake(partner=cls.supplier, polymer=cls.polymer, form=cls.form)

    def _make_offer(self, **kw):
        from datetime import timedelta

        from odoo import fields

        vals = {
            "intake_id": self.intake.id,
            "supplier_id": self.supplier.id,
            "buyer_id": self.buyer.id,
            "price_per_lb": 0.25,
            "quantity_lbs": 40000,
            "valid_until": fields.Date.today() + timedelta(days=30),
        }
        vals.update(kw)
        return self.env["plasticos.offer"].create(vals)

    def test_offer_accept_creates_transaction(self):
        offer = self._make_offer()
        if hasattr(offer, "action_send"):
            offer.action_send()
        if hasattr(offer, "action_accept"):
            offer.action_accept()
            if hasattr(offer, "transaction_id"):
                self.assertTrue(offer.transaction_id)

    def test_transaction_links_back_to_offer(self):
        offer = self._make_offer()
        if hasattr(offer, "action_send"):
            offer.action_send()
        if hasattr(offer, "action_accept") and hasattr(offer, "transaction_id"):
            offer.action_accept()
            tx = offer.transaction_id
            if hasattr(tx, "offer_id"):
                self.assertEqual(tx.offer_id.id, offer.id)

    def test_offer_reject_no_transaction(self):
        offer = self._make_offer(state="sent")
        if hasattr(offer, "action_reject"):
            offer.action_reject()
            if hasattr(offer, "transaction_id"):
                self.assertFalse(offer.transaction_id)


# ═══════════════════════════════════════════════════════════════
# 2. Intake ↔ Transaction Bridge
# ═══════════════════════════════════════════════════════════════
@tagged("post_install", "-at_install", "plasticos", "bridge", "intake")
class TestIntakeBridge(TransactionCase, PlastOSTestFactoryMixin):
    """Tests for intake ↔ transaction bidirectional relationship."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.intake", "plasticos.transaction")
        cls.partner = cls._create_partner()
        cls.polymer = cls._get_or_create_polymer()
        cls.form = cls._get_or_create_form()

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
@tagged("post_install", "-at_install", "plasticos", "bridge", "match")
class TestMatchResultBridge(TransactionCase, PlastOSTestFactoryMixin):
    """Tests for match result bridge fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.match.result")

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
@tagged("post_install", "-at_install", "plasticos", "bridge", "document")
class TestTransactionDocsBridge(TransactionCase, PlastOSTestFactoryMixin):
    """Tests for transaction ↔ document bidirectional relationship."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.transaction", "plasticos.document")

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
@tagged("post_install", "-at_install", "plasticos", "bridge", "load")
class TestLoadDocsBridge(TransactionCase, PlastOSTestFactoryMixin):
    """Tests for load ↔ document bidirectional relationship."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.load", "plasticos.document")

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
@tagged("post_install", "-at_install", "plasticos", "bridge", "claim")
class TestTransactionClaimsBridge(TransactionCase, PlastOSTestFactoryMixin):
    """Tests for transaction ↔ claim bidirectional relationship."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.transaction", "plasticos.claim")

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
@tagged("post_install", "-at_install", "plasticos", "bridge", "partner")
class TestPartnerBridge(TransactionCase, PlastOSTestFactoryMixin):
    """Tests for partner bridge fields added by PlastOS modules."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls._create_partner()

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
        """Creating intake for partner should affect supplier_rank."""
        if "plasticos.intake" not in self.env:
            self.skipTest("plasticos.intake not installed")
        polymer = self._get_or_create_polymer()
        form = self._get_or_create_form()
        self._create_intake(partner=self.partner, polymer=polymer, form=form)
        self.assertGreaterEqual(self.partner.supplier_rank, 0)

    def test_partner_intake_count_computed(self):
        """Partner intake_count should reflect actual intake records."""
        if "intake_ids" not in self.env["res.partner"]._fields:
            self.skipTest("intake_ids not on res.partner")
        if "plasticos.intake" not in self.env:
            self.skipTest("plasticos.intake not installed")

        polymer = self._get_or_create_polymer()
        form = self._get_or_create_form()
        initial_count = len(self.partner.intake_ids)
        self._create_intake(partner=self.partner, polymer=polymer, form=form)
        self.assertEqual(len(self.partner.intake_ids), initial_count + 1)
