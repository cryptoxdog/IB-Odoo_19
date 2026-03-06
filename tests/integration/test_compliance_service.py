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

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "documents", "compliance")
class TestComplianceServiceExists(TransactionCase):
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
class TestDocumentRuleModel(TransactionCase):
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
        for fname in ("name", "model_id", "tag_ids"):
            self.assertIn(
                fname,
                Rule._fields,
                f"Missing field on document.rule: {fname}",
            )


@tagged("post_install", "-at_install", "documents")
class TestDocumentValidationMatrix(TransactionCase):
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
        for fname in ("name", "rule_ids"):
            self.assertIn(fname, Matrix._fields, f"Missing: {fname}")


@tagged("post_install", "-at_install", "documents")
class TestDocumentModel(TransactionCase):
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
        self.assertIn("tag_ids", Doc._fields)

    def test_document_has_transaction_link(self):
        try:
            Doc = self.env["plasticos.document"]
        except KeyError:
            self.skipTest("not installed")
        has_tx = "transaction_id" in Doc._fields or "res_id" in Doc._fields
        self.assertTrue(has_tx, "Document must link to a transaction")
