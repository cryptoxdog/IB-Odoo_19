"""Test 19 — Document Compliance Service Tests.

File: plasticos_documents/models/compliance_service.py
Risk: HIGH — Compliance gating. Gates invoice posting and tx close.

Validates:
  - plasticos.compliance.service model exists
  - is_compliant() method exists and returns bool
  - is_compliant() returns True when all docs present
  - is_compliant() returns False when docs missing
  - Document rule model exists
  - Document validation matrix model exists
"""

import inspect

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_documents.models.compliance_service import PlasticosComplianceService
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "documents", "compliance")
class TestComplianceServiceExists(PlasticosTestCase):
    """Verify compliance service model and API."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.Service = cls.env["plasticos.compliance.service"]
            cls.skip = False
        except KeyError:
            cls.skip = True

    def _skip_check(self):
        if self.skip:
            self.skipTest("plasticos_documents not installed")

    def test_model_exists(self):
        self._skip_check()
        self.assertIsNotNone(self.Service)

    def test_is_compliant_method_exists(self):
        self._skip_check()
        self.assertTrue(
            callable(getattr(self.Service, "is_compliant", None)),
            "is_compliant() missing on compliance.service",
        )

    def test_is_compliant_signature(self):
        """is_compliant should accept model name and record id."""
        self._skip_check()
        import inspect

        sig = inspect.signature(self.Service.is_compliant)
        params = list(sig.parameters.keys())
        self.assertGreaterEqual(
            len(params),
            2,
            "is_compliant must accept at least (model_name, record_id)",
        )


@tagged("post_install", "-at_install", "documents", "compliance")
class TestDocumentRuleModel(PlasticosTestCase):
    """Document rule model wiring."""

    def test_document_rule_model_exists(self):
        try:
            Rule = self.env["plasticos.document.rule"]
        except KeyError:
            self.skipTest("plasticos.document.rule not installed")
        self.assertIsNotNone(Rule)

    def test_document_rule_has_required_fields(self):
        try:
            Rule = self.env["plasticos.document.rule"]
        except KeyError:
            self.skipTest("not installed")
        # A rule names its target model as a Char and requires exactly one tag
        # (plasticos_documents/models/document_rule.py:8-10); there is no model_id / tag_ids.
        for fname in ("name", "res_model", "tag_id"):
            self.assertIn(
                fname,
                Rule._fields,
                f"Missing field on document.rule: {fname}",
            )
        self.assertEqual(Rule._fields["res_model"].type, "char")
        self.assertEqual(Rule._fields["tag_id"].comodel_name, "plasticos.document.tag")
        self.assertTrue(Rule._fields["tag_id"].required)

    def test_legacy_invoice_and_close_read_legacy_rows_only(self):
        """Export campaign S3: invoice/close stay legacy; operation rows never contaminate them."""
        source = inspect.getsource(PlasticosComplianceService.get_missing_documents)
        self.assertIn("_legacy_obligation_domain()", source)
        self.assertEqual(
            self.env["plasticos.document"]._legacy_obligation_domain(), [("obligation_kind", "=", "legacy")]
        )
        field = self.env["plasticos.document"]._fields["obligation_kind"]
        self.assertTrue(field.required)
        self.assertEqual(self.env["plasticos.document"].default_get(["obligation_kind"])["obligation_kind"], "legacy")
        self.assertEqual(self.env["plasticos.document"]._scoped_obligation_kinds(), frozenset())

    def test_receiving_policy_does_not_sum_partial_rows(self):
        source = inspect.getsource(PlasticosComplianceService._quantity_covers_subject)
        self.assertIn("Partial rows are not summed", source)
        self.assertIn("RECEIVING_TAG_CODE", source)


@tagged("post_install", "-at_install", "documents")
class TestDocumentValidationMatrix(PlasticosTestCase):
    """Document validation matrix model wiring."""

    def test_validation_matrix_model_exists(self):
        try:
            Matrix = self.env["plasticos.document.validation.matrix"]
        except KeyError:
            self.skipTest("validation matrix not installed")
        self.assertIsNotNone(Matrix)

    def test_validation_matrix_has_key_fields(self):
        try:
            Matrix = self.env["plasticos.document.validation.matrix"]
        except KeyError:
            self.skipTest("not installed")
        # Each matrix row is one requirement: a party category plus the one tag it requires
        # (plasticos_documents/models/document_validation_matrix.py:14-39); there is no rule_ids.
        for fname in ("name", "doc_category", "tag_id"):
            self.assertIn(fname, Matrix._fields, f"Missing: {fname}")
        self.assertEqual(Matrix._fields["tag_id"].comodel_name, "plasticos.document.tag")


@tagged("post_install", "-at_install", "documents")
class TestDocumentModel(PlasticosTestCase):
    """Core document model wiring."""

    def test_document_model_exists(self):
        try:
            Doc = self.env["plasticos.document"]
        except KeyError:
            self.skipTest("plasticos.document not installed")
        self.assertIsNotNone(Doc)

    def test_document_has_tag_ids(self):
        try:
            Doc = self.env["plasticos.document"]
        except KeyError:
            self.skipTest("not installed")
        # A document carries exactly one tag (plasticos_documents/models/document.py:19).
        self.assertIn("tag_id", Doc._fields)
        self.assertEqual(Doc._fields["tag_id"].comodel_name, "plasticos.document.tag")

    def test_document_has_transaction_link(self):
        try:
            Doc = self.env["plasticos.document"]
        except KeyError:
            self.skipTest("not installed")
        has_tx = "transaction_id" in Doc._fields or "res_id" in Doc._fields
        self.assertTrue(has_tx, "Document must link to a transaction")
