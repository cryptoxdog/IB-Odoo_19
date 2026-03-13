"""Tests for plasticos.document.rule — compliance rule constraints and defaults.

Target module: plasticos_documents
Target model:  plasticos.document.rule
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDocumentRules(PlasticosTestCase):
    """Test document rule model constraints and defaults."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Rule = cls.env["plasticos.document.rule"]
        cls.Tag = cls.env["plasticos.document.tag"]
        cls.tag_bol = cls.Tag.create({"name": "Bill of Lading", "code": "BOL_RULE_TEST"})
        cls.tag_st = cls.Tag.create({"name": "Scale Ticket", "code": "ST_RULE_TEST"})
        cls.partner = cls.env["res.partner"].create({"name": "Client A"})

    def test_create_rule_defaults(self):
        """New rule has correct defaults."""
        rule = self.Rule.create(
            {
                "name": "BOL Required for Transaction",
                "tag_id": self.tag_bol.id,
                "res_model": "plasticos.transaction",
            }
        )
        self.assertTrue(rule.required_for_close)
        self.assertFalse(rule.required_for_invoice)
        self.assertFalse(rule.required_for_dispatch)
        self.assertEqual(rule.overdue_business_days, 1)
        self.assertEqual(rule.escalation_business_days, 5)

    def test_unique_rule_per_tag_model_client(self):
        """Cannot create duplicate rules for same tag + model + client."""
        self.Rule.create(
            {
                "name": "BOL for TX - Client A",
                "tag_id": self.tag_bol.id,
                "res_model": "plasticos.transaction",
                "client_id": self.partner.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.Rule.create(
                {
                    "name": "BOL for TX - Client A (dup)",
                    "tag_id": self.tag_bol.id,
                    "res_model": "plasticos.transaction",
                    "client_id": self.partner.id,
                }
            )

    def test_different_clients_same_tag_model_allowed(self):
        """Different clients can have the same rule tag + model."""
        partner2 = self.env["res.partner"].create({"name": "Client B"})
        rule1 = self.Rule.create(
            {
                "name": "BOL for TX - Client A",
                "tag_id": self.tag_bol.id,
                "res_model": "plasticos.transaction",
                "client_id": self.partner.id,
            }
        )
        rule2 = self.Rule.create(
            {
                "name": "BOL for TX - Client B",
                "tag_id": self.tag_bol.id,
                "res_model": "plasticos.transaction",
                "client_id": partner2.id,
            }
        )
        self.assertNotEqual(rule1.id, rule2.id)

    def test_doc_category_selection_values(self):
        """Document category field accepts all valid selections."""
        for cat in ["supplier", "carrier", "buyer", "internal"]:
            rule = self.Rule.create(
                {
                    "name": f"Rule - {cat}",
                    "tag_id": self.tag_st.id,
                    "res_model": "plasticos.load",
                    "doc_category": cat,
                }
            )
            self.assertEqual(rule.doc_category, cat)

    def test_global_rule_no_client(self):
        """Global rule (no client) should be allowed."""
        rule = self.Rule.create(
            {
                "name": "Global BOL Rule",
                "tag_id": self.tag_bol.id,
                "res_model": "plasticos.load",
                "client_id": False,
            }
        )
        self.assertFalse(rule.client_id)
