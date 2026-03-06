#!/usr/bin/env python3
"""
Audit test files for missing model references.

Scans all test files for self.env["model.name"] patterns and verifies
the model exists in the repo. Catches broken tests before Odoo boots.
"""

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

ODOO_CORE_MODELS = {
    "res.partner",
    "res.users",
    "res.company",
    "res.country",
    "res.country.state",
    "res.currency",
    "res.groups",
    "res.config.settings",
    "ir.model",
    "ir.model.fields",
    "ir.model.access",
    "ir.rule",
    "ir.sequence",
    "ir.attachment",
    "ir.cron",
    "ir.actions.act_window",
    "ir.actions.server",
    "ir.ui.view",
    "ir.ui.menu",
    "ir.module.module",
    "ir.config_parameter",
    "ir.property",
    "ir.default",
    "ir.mail_server",
    "mail.message",
    "mail.thread",
    "mail.activity",
    "mail.activity.type",
    "mail.template",
    "mail.followers",
    "mail.channel",
    "crm.lead",
    "crm.stage",
    "crm.team",
    "crm.tag",
    "sale.order",
    "sale.order.line",
    "purchase.order",
    "purchase.order.line",
    "account.move",
    "account.move.line",
    "account.account",
    "account.journal",
    "account.tax",
    "account.payment",
    "account.payment.term",
    "product.product",
    "product.template",
    "product.category",
    "product.pricelist",
    "product.uom",
    "product.uom.categ",
    "stock.picking",
    "stock.move",
    "stock.location",
    "stock.warehouse",
    "stock.quant",
    "stock.picking.type",
    "uom.uom",
    "uom.category",
    "utm.source",
    "utm.medium",
    "utm.campaign",
    "res.partner.category",
    "base.automation",
    "digest.digest",
    "digest.tip",
}

model_pattern = re.compile(r'(?:self\.)?env\[\s*[\'"]([a-zA-Z0-9\._]+)[\'"]\s*\]')
model_def_pattern = re.compile(r'_name\s*=\s*["\']([^"\']+)["\']')

models_found = set()
model_to_module = {}
tests_using_model = defaultdict(list)


def scan_models():
    """Scan repo for model definitions."""
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules", ".venv", ".cursor"}]

        for f in files:
            if not f.endswith(".py"):
                continue

            path = Path(root) / f
            rel_path = path.relative_to(REPO_ROOT)

            if "tests" in str(rel_path):
                continue

            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for match in model_def_pattern.findall(content):
                models_found.add(match)
                parts = str(rel_path).split("/")
                if parts:
                    module = parts[0]
                    model_to_module[match] = module


def scan_tests():
    """Scan test files for model references."""
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules", ".venv", ".cursor"}]

        if "tests" not in root:
            continue

        for f in files:
            if not f.endswith(".py") or f == "__init__.py":
                continue

            path = Path(root) / f
            rel_path = path.relative_to(REPO_ROOT)

            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for match in model_pattern.findall(content):
                tests_using_model[match].append(str(rel_path))


def main():
    print("=" * 70)
    print("AUDIT: Test Model References")
    print("=" * 70)

    scan_models()
    scan_tests()

    print(f"\nModels defined in repo: {len(models_found)}")
    print(f"Models referenced in tests: {len(tests_using_model)}")

    missing = []
    for model in sorted(tests_using_model.keys()):
        if model not in models_found and model not in ODOO_CORE_MODELS:
            missing.append(model)

    if missing:
        print("\n" + "!" * 70)
        print("🚨 MISSING MODELS REFERENCED IN TESTS:")
        print("!" * 70)

        for model in missing:
            print(f"\n  MODEL: {model}")
            for file in sorted(set(tests_using_model[model])):
                print(f"    → {file}")

        print("\n" + "!" * 70)
        print(f"TOTAL MISSING: {len(missing)} models")
        print("!" * 70)
        return 1
    else:
        print("\n✅ All model references in tests are valid.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
