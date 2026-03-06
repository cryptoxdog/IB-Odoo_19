"""
Test compliance service.

Tests check transaction docs vs required rules.
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestComplianceService(PlasticosTestCase):
    """Test plasticos.compliance.service model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "is_company": True,
            }
        )
        cls.tag = cls.env["plasticos.document.tag"].create(
            {
                "name": "Certificate of Insurance",
                "code": "COI_COMPLIANCE_TEST",
            }
        )
        cls.attachment = cls.env["ir.attachment"].create(
            {"name": "test_compliance_doc.pdf", "type": "binary", "datas": "dGVzdA=="}
        )

    def test_check_compliance_no_rules(self):
        """Compliance check with no rules should pass."""
        service = self.env["plasticos.compliance.service"]

        # Create a mock transaction if model exists
        if "plasticos.transaction" in self.env:
            tx = self.env["plasticos.transaction"].create(
                {
                    "supplier_id": self.partner.id,
                    "buyer_id": self.partner.id,
                }
            )

            result = service.check_compliance(tx)
            self.assertTrue(result.get("compliant", True))

    def test_check_compliance_missing_document(self):
        """Compliance check should fail if required document missing."""
        service = self.env["plasticos.compliance.service"]

        # Create required rule
        self.env["plasticos.document.rule"].create(
            {
                "tag_id": self.tag.id,
                "model": "plasticos.transaction",
                "required": True,
            }
        )

        if "plasticos.transaction" in self.env:
            tx = self.env["plasticos.transaction"].create(
                {
                    "supplier_id": self.partner.id,
                    "buyer_id": self.partner.id,
                }
            )

            result = service.check_compliance(tx)
            self.assertFalse(result.get("compliant", True))
            self.assertIn("COI", str(result.get("missing", [])))

    def test_check_compliance_with_document(self):
        """Compliance check should pass if required document exists."""
        service = self.env["plasticos.compliance.service"]

        # Create required rule
        self.env["plasticos.document.rule"].create(
            {
                "tag_id": self.tag.id,
                "model": "plasticos.transaction",
                "required": True,
            }
        )

        if "plasticos.transaction" in self.env:
            tx = self.env["plasticos.transaction"].create(
                {
                    "supplier_id": self.partner.id,
                    "buyer_id": self.partner.id,
                }
            )

            # Create document with all required fields
            self.env["plasticos.document"].create(
                {
                    "name": "COI Document",
                    "res_model": "plasticos.transaction",
                    "res_id": tx.id,
                    "attachment_id": self.attachment.id,
                    "tag_id": self.tag.id,
                    "transaction_id": tx.id,
                    "verified": True,
                }
            )

            result = service.check_compliance(tx)
            self.assertTrue(result.get("compliant", False))
