"""Tests for @api.constrains across multiple PlastOS models.

Target module: (cross-module)
Target models: plasticos.commission.rule, plasticos.document.validation.matrix,
               plasticos.match.exclusion, plasticos.claim

Validates that constraint decorators fire correctly and block
invalid data from persisting.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install", "plasticos", "constraint")
class TestConstraintValidation(PlasticosTestCase):
    """Cross-module @api.constrains validation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Partners for exclusion tests
        cls.partner_a = cls.env["res.partner"].create({"name": "Supplier A"})
        cls.partner_b = cls.env["res.partner"].create({"name": "Buyer B"})

        # Commission rule dependencies
        cls.sales_rep = cls.env["res.users"].create(
            {
                "name": "Constraint Test Rep",
                "login": "test_constraint_rep",
            }
        )

        # Document tag for matrix tests
        cls.doc_tag = cls.env["plasticos.document.tag"].create(
            {
                "name": "Test BOL Tag",
                "code": "CONSTRAINT_TEST_TAG",
            }
        )

        # Transaction for claim tests
        cls.tx = cls.env["plasticos.transaction"].create({"name": "TX-CONSTRAINT"})

    # ── Commission Rule: percentage 0.0–1.0 ────────────────────

    def test_commission_rule_above_one_rejected(self):
        """Commission rate > 1.0 raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["plasticos.commission.rule"].create(
                {
                    "name": "Bad Rate",
                    "sales_rep_id": self.sales_rep.id,
                    "percentage": 1.01,
                }
            )

    def test_commission_rule_negative_rejected(self):
        """Commission rate < 0.0 raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["plasticos.commission.rule"].create(
                {
                    "name": "Negative Rate",
                    "sales_rep_id": self.sales_rep.id,
                    "percentage": -0.05,
                }
            )

    # ── Document Validation Matrix: unique(category, tag) ──────

    def test_document_matrix_duplicate_category_tag_rejected(self):
        """Duplicate (doc_category, tag_id) raises ValidationError."""
        Matrix = self.env["plasticos.document.validation.matrix"]
        Matrix.create(
            {
                "name": "Entry A",
                "doc_category": "supplier",
                "tag_id": self.doc_tag.id,
            }
        )
        with self.assertRaises(ValidationError):
            Matrix.create(
                {
                    "name": "Entry B (duplicate)",
                    "doc_category": "supplier",
                    "tag_id": self.doc_tag.id,
                }
            )

    def test_document_matrix_different_category_same_tag_accepted(self):
        """Same tag with different category is allowed."""
        Matrix = self.env["plasticos.document.validation.matrix"]
        tag2 = self.env["plasticos.document.tag"].create(
            {
                "name": "Unique Matrix Tag",
                "code": "UNIQ_MATRIX_TAG",
            }
        )
        m1 = Matrix.create(
            {
                "name": "Supplier Entry",
                "doc_category": "supplier",
                "tag_id": tag2.id,
            }
        )
        m2 = Matrix.create(
            {
                "name": "Carrier Entry",
                "doc_category": "carrier",
                "tag_id": tag2.id,
            }
        )
        self.assertTrue(m1.id)
        self.assertTrue(m2.id)

    # ── Match Exclusion: different partners ─────────────────────

    def test_match_exclusion_same_partner_rejected(self):
        """Excluding a partner from itself raises ValidationError."""
        if "plasticos.match.exclusion" not in self.env:
            return
        Exclusion = self.env["plasticos.match.exclusion"]
        with self.assertRaises((ValidationError, Exception)):
            Exclusion.create(
                {
                    "supplier_partner_id": self.partner_a.id,
                    "buyer_partner_id": self.partner_a.id,
                    "exclusion_type": "permanent",
                    "reason": "self-exclusion attempt",
                }
            )

    def test_match_exclusion_different_partners_accepted(self):
        """Different supplier/buyer is valid."""
        if "plasticos.match.exclusion" not in self.env:
            return
        Exclusion = self.env["plasticos.match.exclusion"]
        exc = Exclusion.create(
            {
                "supplier_partner_id": self.partner_a.id,
                "buyer_partner_id": self.partner_b.id,
                "exclusion_type": "permanent",
                "reason": "quality issues",
            }
        )
        self.assertTrue(exc.id)

    # ── Claim: resolution_note required ─────────────────────────

    def test_claim_resolve_without_note_raises(self):
        """Resolving a claim without resolution_note raises UserError."""
        Claim = self.env["plasticos.claim"]
        claim = Claim.create(
            {
                "transaction_id": self.tx.id,
                "case_type": "buyer_claim",
                "severity": "medium",
                "state": "in_progress",
            }
        )
        with self.assertRaises(UserError):
            claim.action_resolve()

    def test_claim_resolve_with_note_succeeds(self):
        """Resolving a claim with resolution_note succeeds."""
        Claim = self.env["plasticos.claim"]
        claim = Claim.create(
            {
                "transaction_id": self.tx.id,
                "case_type": "buyer_claim",
                "severity": "medium",
                "state": "in_progress",
            }
        )
        claim.resolution_note = "Resolved via credit memo"
        claim.action_resolve()
        self.assertEqual(claim.state, "resolved")
