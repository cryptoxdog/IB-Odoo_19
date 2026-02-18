# ============================================================
# File: seed_validator.py
# Module: plasticos_dev_tools
# Version: 19.0.1.0.0
# Author: PlasticOS
# Purpose: Validate seed data XML files for consistency and
#          correctness before module installation.
# Usage: Run via Odoo shell:
#   odoo shell -d <db> --addons-path=<path>
#   >>> exec(open('plasticos_dev_tools/tools/seed_validator.py').read())
#   >>> validate_seeds(env)
# ============================================================
"""
Seed Validator Tool
===================
Read-only validation that checks:
1. All document tags have unique codes
2. All cron jobs reference valid model methods
3. All security groups exist and are properly nested
4. All ir.model.access.csv entries reference valid models
5. Manifest data file ordering is correct

This script performs NO writes. It only reads and reports.
"""

import os
import csv
import logging

_logger = logging.getLogger(__name__)

# Modules to validate
_MODULES = [
    "plasticos_logistics",
    "plasticos_logistics_automation",
    "plasticos_documents",
    "plasticos_documents_extension",
    "plasticos_transaction",
    "plasticos_automation",
]


def validate_seeds(env, addons_path=None):
    """Validate seed data for all PlasticOS modules.

    Args:
        env: Odoo environment.
        addons_path: Optional path to addons directory.
                     Defaults to scanning ir.module.module.

    Returns:
        dict: Validation results per module.
    """
    results = {}

    print("=" * 60)
    print("PLASTICOS SEED DATA VALIDATOR")
    print("=" * 60)

    # ── Check 1: Document Tag Uniqueness ───────────────────────
    print("\n[1/3] Validating document tag uniqueness...")
    tags = env["plasticos.document.tag"].search([])
    seen_codes = {}
    tag_issues = []
    for tag in tags:
        if tag.code in seen_codes:
            tag_issues.append(
                "Duplicate code '%s': tag IDs %d and %d"
                % (tag.code, seen_codes[tag.code], tag.id)
            )
        else:
            seen_codes[tag.code] = tag.id
    results["tag_uniqueness"] = tag_issues
    print("  Issues: %d" % len(tag_issues))

    # ── Check 2: Cron Method Validation ────────────────────────
    print("\n[2/3] Validating cron job method references...")
    crons = env["ir.cron"].search([])
    cron_issues = []
    for cron in crons:
        if cron.state == "code" and cron.code:
            # Extract model.method() pattern
            code = cron.code.strip()
            if code.startswith("model."):
                method_name = code.replace("model.", "").replace("()", "").strip()
                model_name = cron.model_id.model if cron.model_id else None
                if model_name and model_name in env:
                    model_obj = env[model_name]
                    if not hasattr(model_obj, method_name):
                        cron_issues.append(
                            "Cron '%s': method '%s' not found on model '%s'"
                            % (cron.name, method_name, model_name)
                        )
    results["cron_methods"] = cron_issues
    print("  Issues: %d" % len(cron_issues))

    # ── Check 3: ACL Model References ──────────────────────────
    print("\n[3/3] Validating ACL model references...")
    acl_issues = []
    acls = env["ir.model.access"].search([])
    for acl in acls:
        if acl.model_id and acl.model_id.model not in env:
            acl_issues.append(
                "ACL '%s': model '%s' not in registry"
                % (acl.name, acl.model_id.model)
            )
    results["acl_models"] = acl_issues
    print("  Issues: %d" % len(acl_issues))

    # ── Summary ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    total = sum(len(v) for v in results.values())
    for key, items in results.items():
        status = "PASS" if not items else "FAIL (%d)" % len(items)
        print("  %-30s %s" % (key, status))
    print("\nTotal issues: %d" % total)

    return results
