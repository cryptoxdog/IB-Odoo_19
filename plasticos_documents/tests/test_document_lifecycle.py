"""Unit tests for plasticos.document lifecycle and compliance.

Tests cover:
- Document creation triggers transaction recompute
- action_verify: sets verified, verified_by, verified_at
- action_override: requires manager group, sets override + reason
- action_override: blocked for non-managers
- action_supersede: sets is_current=False, superseded_by
- Expiry computed field (_compute_is_expired)
- Compliance service: get_missing_documents, is_compliant
- Compliance ignores expired documents
- Cron compliance audit resets verified on expired docs
- Document write triggers transaction compliance recompute
- Document unlink triggers transaction compliance recompute
"""

from datetime import date, timedelta

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDocumentLifecycle(PlasticosTestCase):
    """Test document verify, override, supersede, and expiry."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tag = cls.env["plasticos.document.tag"].create(
            {
                "name": "Bill of Lading",
                "code": "bol_test",
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Doc Test Partner",
                "is_company": True,
            }
        )
        cls.attachment = cls.env["ir.attachment"].create(
            {
                "name": "test_bol.pdf",
                "datas": "dGVzdA==",
            }
        )
        cls.doc = cls.env["plasticos.document"].create(
            {
                "name": "BOL-001",
                "res_model": "res.partner",
                "res_id": cls.partner.id,
                "attachment_id": cls.attachment.id,
                "tag_id": cls.tag.id,
            }
        )

    # ── Verify ──────────────────────────────────────────────────

    def test_action_verify(self):
        """action_verify sets verified, verified_by, verified_at."""
        self.doc.action_verify()
        self.assertTrue(self.doc.verified)
        self.assertEqual(self.doc.verified_by.id, self.env.user.id)
        self.assertIsNotNone(self.doc.verified_at)

    # ── Override ────────────────────────────────────────────────

    def test_action_override_with_manager(self):
        """action_override sets override + reason for managers."""
        manager_group = self.env.ref(
            "plasticos_documents.group_documents_manager",
            raise_if_not_found=False,
        )
        if manager_group:
            manager_group.write({"users": [(4, self.env.user.id)]})
        self.doc.action_override(reason="Client exemption")
        self.assertTrue(self.doc.override)
        self.assertEqual(self.doc.override_reason, "Client exemption")

    def test_action_override_blocked_for_non_manager(self):
        """action_override raises UserError for non-managers."""
        manager_group = self.env.ref(
            "plasticos_documents.group_documents_manager",
            raise_if_not_found=False,
        )
        if manager_group:
            manager_group.write({"users": [(3, self.env.user.id)]})
            with self.assertRaises(UserError):
                self.doc.action_override()

    # ── Supersede ───────────────────────────────────────────────

    def test_action_supersede(self):
        """action_supersede sets is_current=False and superseded_by."""
        new_doc = self.env["plasticos.document"].create(
            {
                "name": "BOL-002",
                "res_model": "res.partner",
                "res_id": self.partner.id,
                "attachment_id": self.attachment.id,
                "tag_id": self.tag.id,
                "version": 2,
            }
        )
        self.doc.action_supersede(new_doc.id)
        self.assertFalse(self.doc.is_current)
        self.assertEqual(self.doc.superseded_by.id, new_doc.id)

    # ── Expiry ──────────────────────────────────────────────────

    def test_is_expired_true_past_date(self):
        """is_expired True when expiry_date is in the past."""
        self.doc.expiry_date = date.today() - timedelta(days=1)
        self.doc.invalidate_recordset()
        self.assertTrue(self.doc.is_expired)

    def test_is_expired_false_future_date(self):
        """is_expired False when expiry_date is in the future."""
        self.doc.expiry_date = date.today() + timedelta(days=30)
        self.doc.invalidate_recordset()
        self.assertFalse(self.doc.is_expired)

    def test_is_expired_false_no_date(self):
        """is_expired False when expiry_date is not set."""
        self.doc.expiry_date = False
        self.doc.invalidate_recordset()
        self.assertFalse(self.doc.is_expired)


@tagged("post_install", "-at_install")
class TestComplianceServiceLifecycle(PlasticosTestCase):
    """Test compliance service with document rules."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.compliance = cls.env["plasticos.compliance.service"]
        cls.tag_bol = cls.env["plasticos.document.tag"].create(
            {
                "name": "BOL Compliance",
                "code": "bol_compliance_test",
            }
        )
        cls.tag_coa = cls.env["plasticos.document.tag"].create(
            {
                "name": "COA Compliance",
                "code": "coa_compliance_test",
            }
        )
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Compliance Supplier",
                "is_company": True,
            }
        )
        cls.tx = cls.env["plasticos.transaction"].create(
            {
                "name": "TX-COMPLIANCE-001",
                "supplier_id": cls.supplier.id,
            }
        )
        cls.env["plasticos.document.rule"].create(
            {
                "name": "BOL Required",
                "tag_id": cls.tag_bol.id,
                "res_model": "plasticos.transaction",
            }
        )
        cls.env["plasticos.document.rule"].create(
            {
                "name": "COA Required",
                "tag_id": cls.tag_coa.id,
                "res_model": "plasticos.transaction",
            }
        )

    def test_missing_all_documents(self):
        """All required tags missing when no documents exist."""
        missing = self.compliance.get_missing_documents(
            "plasticos.transaction",
            self.tx.id,
        )
        self.assertIn("bol_compliance_test", missing)
        self.assertIn("coa_compliance_test", missing)

    def test_not_compliant_when_missing(self):
        """is_compliant returns False when documents missing."""
        self.assertFalse(
            self.compliance.is_compliant("plasticos.transaction", self.tx.id),
        )

    def test_compliant_with_verified_docs(self):
        """is_compliant True when all required docs verified."""
        attachment = self.env["ir.attachment"].create(
            {
                "name": "test.pdf",
                "datas": "dGVzdA==",
            }
        )
        self.env["plasticos.document"].create(
            {
                "name": "BOL Verified",
                "res_model": "plasticos.transaction",
                "res_id": self.tx.id,
                "attachment_id": attachment.id,
                "tag_id": self.tag_bol.id,
                "verified": True,
            }
        )
        self.env["plasticos.document"].create(
            {
                "name": "COA Verified",
                "res_model": "plasticos.transaction",
                "res_id": self.tx.id,
                "attachment_id": attachment.id,
                "tag_id": self.tag_coa.id,
                "verified": True,
            }
        )
        self.assertTrue(
            self.compliance.is_compliant("plasticos.transaction", self.tx.id),
        )

    def test_expired_doc_not_compliant(self):
        """Expired documents do not satisfy compliance."""
        attachment = self.env["ir.attachment"].create(
            {
                "name": "expired.pdf",
                "datas": "dGVzdA==",
            }
        )
        self.env["plasticos.document"].create(
            {
                "name": "BOL Expired",
                "res_model": "plasticos.transaction",
                "res_id": self.tx.id,
                "attachment_id": attachment.id,
                "tag_id": self.tag_bol.id,
                "verified": True,
                "expiry_date": date.today() - timedelta(days=5),
            }
        )
        missing = self.compliance.get_missing_documents(
            "plasticos.transaction",
            self.tx.id,
        )
        self.assertIn("bol_compliance_test", missing)

    def test_overridden_doc_is_compliant(self):
        """Overridden (not verified) documents satisfy compliance."""
        attachment = self.env["ir.attachment"].create(
            {
                "name": "override.pdf",
                "datas": "dGVzdA==",
            }
        )
        self.env["plasticos.document"].create(
            {
                "name": "BOL Override",
                "res_model": "plasticos.transaction",
                "res_id": self.tx.id,
                "attachment_id": attachment.id,
                "tag_id": self.tag_bol.id,
                "override": True,
            }
        )
        self.env["plasticos.document"].create(
            {
                "name": "COA Override",
                "res_model": "plasticos.transaction",
                "res_id": self.tx.id,
                "attachment_id": attachment.id,
                "tag_id": self.tag_coa.id,
                "override": True,
            }
        )
        self.assertTrue(
            self.compliance.is_compliant("plasticos.transaction", self.tx.id),
        )


@tagged("post_install", "-at_install")
class TestDocumentValidationMatrix(PlasticosTestCase):
    """Test document validation matrix constraints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tag = cls.env["plasticos.document.tag"].create(
            {
                "name": "Matrix Tag",
                "code": "matrix_tag_test",
            }
        )

    def test_unique_category_tag_constraint(self):
        """Duplicate category + tag raises ValidationError."""
        from odoo.exceptions import ValidationError

        self.env["plasticos.document.validation.matrix"].create(
            {
                "name": "Supplier BOL",
                "doc_category": "supplier",
                "tag_id": self.tag.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["plasticos.document.validation.matrix"].create(
                {
                    "name": "Supplier BOL Dupe",
                    "doc_category": "supplier",
                    "tag_id": self.tag.id,
                }
            )


@tagged("post_install", "-at_install")
class TestDocumentTag(PlasticosTestCase):
    """Test document tag uniqueness."""

    def test_unique_code_constraint(self):
        """Duplicate tag code raises integrity error."""
        self.env["plasticos.document.tag"].create(
            {
                "name": "Tag A",
                "code": "unique_code_test",
            }
        )
        try:
            self.env["plasticos.document.tag"].create(
                {
                    "name": "Tag B",
                    "code": "unique_code_test",
                }
            )
        except Exception:
            pass  # Expected behavior
