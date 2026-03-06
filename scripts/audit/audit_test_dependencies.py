#!/usr/bin/env python3
"""
Audit test files for missing module dependencies.

Detects when a test uses a model from another module but the manifest
doesn't declare that dependency.
"""

import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

model_pattern = re.compile(r'(?:self\.)?env\[\s*[\'"]([a-zA-Z0-9\._]+)[\'"]\s*\]')
model_def_pattern = re.compile(r'_name\s*=\s*["\']([^"\']+)["\']')

ODOO_CORE_MODELS = {
    "res.partner",
    "res.users",
    "res.company",
    "res.country",
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
    "mail.message",
    "mail.thread",
    "mail.activity",
    "mail.template",
    "crm.lead",
    "crm.stage",
    "crm.team",
    "sale.order",
    "sale.order.line",
    "purchase.order",
    "purchase.order.line",
    "account.move",
    "account.move.line",
    "account.account",
    "account.journal",
    "product.product",
    "product.template",
    "product.category",
    "stock.picking",
    "stock.move",
    "stock.location",
    "uom.uom",
    "utm.source",
    "utm.medium",
    "res.country.state",
    "ir.property",
    "ir.default",
    "mail.followers",
}


def load_manifests():
    """Load all module manifests."""
    manifests = {}
    for item in REPO_ROOT.iterdir():
        if not item.is_dir():
            continue
        manifest_path = item / "__manifest__.py"
        if manifest_path.exists():
            try:
                content = manifest_path.read_text()
                manifest = ast.literal_eval(content)
                manifests[item.name] = manifest.get("depends", [])
            except Exception:
                pass
    return manifests


def find_model_modules():
    """Map models to their defining modules."""
    model_to_module = {}
    for item in REPO_ROOT.iterdir():
        if not item.is_dir():
            continue
        models_dir = item / "models"
        if not models_dir.exists():
            continue

        for py_file in models_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                for match in model_def_pattern.findall(content):
                    model_to_module[match] = item.name
            except Exception:
                pass
    return model_to_module


def find_test_model_usage():
    """Find which models each test module uses."""
    test_usage = defaultdict(set)
    for item in REPO_ROOT.iterdir():
        if not item.is_dir():
            continue
        tests_dir = item / "tests"
        if not tests_dir.exists():
            continue

        for py_file in tests_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                for match in model_pattern.findall(content):
                    test_usage[item.name].add(match)
            except Exception:
                pass
    return test_usage


def get_transitive_deps(module, manifests, visited=None):
    """Get all transitive dependencies of a module."""
    if visited is None:
        visited = set()
    if module in visited:
        return visited
    visited.add(module)
    for dep in manifests.get(module, []):
        if dep in manifests:
            get_transitive_deps(dep, manifests, visited)
    return visited


def main():
    print("=" * 70)
    print("AUDIT: Test Module Dependencies")
    print("=" * 70)

    manifests = load_manifests()
    model_to_module = find_model_modules()
    test_usage = find_test_model_usage()

    print(f"\nModules with manifests: {len(manifests)}")
    print(f"Models mapped to modules: {len(model_to_module)}")
    print(f"Test modules scanned: {len(test_usage)}")

    missing_deps = []

    for test_module, models_used in sorted(test_usage.items()):
        all_deps = get_transitive_deps(test_module, manifests)

        for model in models_used:
            if model in ODOO_CORE_MODELS:
                continue

            model_module = model_to_module.get(model)
            if model_module and model_module not in all_deps:
                missing_deps.append(
                    {
                        "test_module": test_module,
                        "model": model,
                        "model_module": model_module,
                    }
                )

    if missing_deps:
        print("\n" + "!" * 70)
        print("🚨 MISSING MODULE DEPENDENCIES:")
        print("!" * 70)

        by_test_module = defaultdict(list)
        for item in missing_deps:
            by_test_module[item["test_module"]].append(item)

        for test_module, items in sorted(by_test_module.items()):
            print(f"\n  MODULE: {test_module}")
            print(f"  CURRENT DEPS: {manifests.get(test_module, [])}")
            print("  MISSING:")
            seen = set()
            for item in items:
                key = (item["model_module"], item["model"])
                if key not in seen:
                    seen.add(key)
                    print(f"    → {item['model_module']} (provides {item['model']})")

        print("\n" + "!" * 70)
        print(f"TOTAL ISSUES: {len(missing_deps)}")
        print("!" * 70)
        return 1
    else:
        print("\n✅ All test module dependencies are satisfied.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
