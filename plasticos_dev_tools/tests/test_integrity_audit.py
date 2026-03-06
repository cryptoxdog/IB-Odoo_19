# ============================================================
# File: test_integrity_audit.py
# Module: plasticos_dev_tools
# Purpose: Odoo test wrapper for integrity audit checks
# ============================================================
from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestIntegrityAudit(PlasticosTestCase):
    """Integrity audit tests for PlasticOS data consistency."""

    def test_no_orphaned_documents(self):
        """Verify no documents reference non-existent records."""
        documents = self.env["plasticos.document"].search([("active", "=", True)])
        orphaned = []
        for doc in documents:
            try:
                target = self.env[doc.res_model].browse(doc.res_id)
                if not target.exists():
                    orphaned.append(doc.name)
            except (KeyError, ValueError):
                orphaned.append(f"{doc.name} (model {doc.res_model} not found)")

        self.assertEqual(len(orphaned), 0, f"Found {len(orphaned)} orphaned documents: {orphaned[:5]}")

    def test_compliance_rules_exist(self):
        """Verify compliance rules are defined for transactions."""
        rules = self.env["plasticos.document.rule"].search(
            [
                ("res_model", "=", "plasticos.transaction"),
                ("active", "=", True),
            ]
        )
        self.assertTrue(rules, "No active compliance rules found for plasticos.transaction")

    def test_no_invalid_rule_models(self):
        """Verify all document rules reference valid models."""
        rules = self.env["plasticos.document.rule"].search([("active", "=", True)])
        invalid = []
        for rule in rules:
            if rule.res_model not in self.env:
                invalid.append(f"{rule.name} -> {rule.res_model}")

        self.assertEqual(len(invalid), 0, f"Found {len(invalid)} rules with invalid models: {invalid}")

    def test_no_duplicate_tag_codes(self):
        """Verify document tag codes are unique."""
        tags = self.env["plasticos.document.tag"].search([("active", "=", True)])
        code_counts = {}
        for tag in tags:
            code_counts.setdefault(tag.code, []).append(tag.id)

        duplicates = {code: ids for code, ids in code_counts.items() if len(ids) > 1}
        self.assertEqual(len(duplicates), 0, f"Found duplicate tag codes: {duplicates}")
