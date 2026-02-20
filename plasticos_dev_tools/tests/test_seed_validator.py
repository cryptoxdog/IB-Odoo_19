# ============================================================
# File: test_seed_validator.py
# Module: plasticos_dev_tools
# Purpose: Odoo test wrapper for seed data validation
# ============================================================
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSeedValidator(TransactionCase):
    """Seed data validation tests for PlasticOS modules."""

    def test_document_tag_uniqueness(self):
        """Verify all document tags have unique codes."""
        tags = self.env["plasticos.document.tag"].search([])
        seen_codes = {}
        duplicates = []
        
        for tag in tags:
            if tag.code in seen_codes:
                duplicates.append(
                    f"Code '{tag.code}': IDs {seen_codes[tag.code]} and {tag.id}"
                )
            else:
                seen_codes[tag.code] = tag.id
        
        self.assertEqual(
            len(duplicates), 0,
            f"Found duplicate tag codes: {duplicates}"
        )

    def test_cron_methods_exist(self):
        """Verify all cron jobs reference valid model methods."""
        crons = self.env["ir.cron"].search([
            ("model_id.model", "like", "plasticos.%"),
        ])
        missing_methods = []
        
        for cron in crons:
            if cron.state == "code" and cron.code:
                code = cron.code.strip()
                if code.startswith("model."):
                    method_name = code.replace("model.", "").replace("()", "").strip()
                    model_name = cron.model_id.model if cron.model_id else None
                    if model_name and model_name in self.env:
                        model_obj = self.env[model_name]
                        if not hasattr(model_obj, method_name):
                            missing_methods.append(
                                f"Cron '{cron.name}': method '{method_name}' not on '{model_name}'"
                            )
        
        self.assertEqual(
            len(missing_methods), 0,
            f"Found crons with missing methods: {missing_methods}"
        )

    def test_acl_model_references(self):
        """Verify all ACLs reference valid models."""
        acls = self.env["ir.model.access"].search([
            ("model_id.model", "like", "plasticos.%"),
        ])
        invalid = []
        
        for acl in acls:
            if acl.model_id and acl.model_id.model not in self.env:
                invalid.append(f"ACL '{acl.name}': model '{acl.model_id.model}'")
        
        self.assertEqual(
            len(invalid), 0,
            f"Found ACLs with invalid models: {invalid}"
        )
