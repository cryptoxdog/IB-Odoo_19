"""
Test document rules.

Tests unique rule per tag+model+client constraint.
"""

from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDocumentRules(TransactionCase):
    """Test plasticos.document.rule model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tag = cls.env["plasticos.document.tag"].create(
            {
                "name": "Certificate of Insurance",
                "code": "COI",
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Client",
                "is_company": True,
            }
        )

    def _create_rule(self, **kwargs):
        """Helper to create a document rule."""
        vals = {
            "tag_id": self.tag.id,
            "model": "plasticos.transaction",
            "required": True,
        }
        vals.update(kwargs)
        return self.env["plasticos.document.rule"].create(vals)

    def test_create_rule(self):
        """Document rule can be created."""
        rule = self._create_rule()
        self.assertTrue(rule.id)

    def test_unique_tag_model_client_constraint(self):
        """Rule must be unique per tag+model+client."""
        self._create_rule(partner_id=self.partner.id)

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_document_rule
                (tag_id, model, partner_id, required)
                VALUES (%s, %s, %s, %s)
            """,
                (self.tag.id, "plasticos.transaction", self.partner.id, True),
            )

    def test_different_clients_allowed(self):
        """Same tag+model with different clients should be allowed."""
        rule1 = self._create_rule(partner_id=self.partner.id)

        partner2 = self.env["res.partner"].create(
            {
                "name": "Test Client 2",
                "is_company": True,
            }
        )
        rule2 = self._create_rule(partner_id=partner2.id)

        self.assertNotEqual(rule1.id, rule2.id)

    def test_global_rule_no_client(self):
        """Global rule (no client) should be allowed."""
        rule = self._create_rule(partner_id=False)
        self.assertFalse(rule.partner_id)
