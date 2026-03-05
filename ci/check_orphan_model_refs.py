#!/usr/bin/env python3
"""
Orphan Model Reference Checker
==============================

Prevents XML files from referencing models that don't exist in the codebase.

This catches errors like:
- XML data files creating records for deprecated/removed models
- View definitions for non-existent models
- Actions referencing missing res_model

The error this prevents:
    KeyError: 'model.name'
    during XML loading (convert.py → _tag_record → env[model])

Usage:
    python3 ci/check_orphan_model_refs.py [root_dir]

Exit codes:
    0 = No issues found
    1 = Orphan references found (blocks CI)
"""

import re
import sys
from pathlib import Path

from _git_utils import get_git_tracked_files


def extract_model_names_from_python(root_dir: Path) -> set[str]:
    """Extract all _name declarations from Python model files."""
    models = set()

    # Add Odoo core models that are always available
    # This list covers common models from base, mail, sale, purchase, stock, account, crm
    core_models = {
        # Base
        "res.partner",
        "res.partner.category",
        "res.partner.bank",
        "res.partner.title",
        "res.users",
        "res.users.log",
        "res.company",
        "res.groups",
        "res.country",
        "res.country.state",
        "res.currency",
        "res.lang",
        "res.bank",
        "res.config.settings",
        # IR (Information Repository)
        "ir.model",
        "ir.model.fields",
        "ir.model.access",
        "ir.rule",
        "ir.filters",
        "ir.ui.view",
        "ir.ui.menu",
        "ir.actions.act_window",
        "ir.actions.server",
        "ir.actions.report",
        "ir.actions.act_url",
        "ir.actions.client",
        "ir.sequence",
        "ir.sequence.date_range",
        "ir.attachment",
        "ir.cron",
        "ir.config_parameter",
        "ir.property",
        "ir.default",
        "ir.translation",
        "ir.module.module",
        "ir.module.category",
        # Mail
        "mail.message",
        "mail.thread",
        "mail.activity",
        "mail.activity.type",
        "mail.followers",
        "mail.alias",
        "mail.template",
        "mail.mail",
        "mail.channel",
        "mail.notification",
        # UTM
        "utm.source",
        "utm.medium",
        "utm.campaign",
        "utm.tag",
        # Product
        "product.product",
        "product.template",
        "product.category",
        "product.pricelist",
        "product.pricelist.item",
        "product.attribute",
        "product.attribute.value",
        "product.supplierinfo",
        "uom.uom",
        "uom.category",
        # Sale
        "sale.order",
        "sale.order.line",
        "sale.order.template",
        "sale.order.template.line",
        # Purchase
        "purchase.order",
        "purchase.order.line",
        # Account
        "account.move",
        "account.move.line",
        "account.account",
        "account.journal",
        "account.tax",
        "account.tax.group",
        "account.payment",
        "account.payment.term",
        "account.payment.term.line",
        "account.analytic.account",
        "account.analytic.line",
        "account.fiscal.position",
        "account.fiscal.position.tax",
        "account.incoterms",
        "account.bank.statement",
        "account.bank.statement.line",
        "account.reconcile.model",
        # Stock
        "stock.picking",
        "stock.picking.type",
        "stock.move",
        "stock.move.line",
        "stock.location",
        "stock.warehouse",
        "stock.quant",
        "stock.lot",
        "stock.rule",
        "stock.route",
        # CRM
        "crm.lead",
        "crm.stage",
        "crm.team",
        "crm.tag",
        "crm.lost.reason",
        # Calendar
        "calendar.event",
        "calendar.alarm",
        # Contacts
        "res.partner.industry",
        # Website (if installed)
        "website",
        "website.page",
        "website.menu",
        # Portal
        "portal.mixin",
        # Base Automation
        "base.automation",
        "base.automation.line",
        # Documents (Enterprise)
        "documents.document",
        "documents.folder",
        "documents.facet",
        "documents.tag",
        "documents.share",
        "documents.workflow.rule",
        "documents.workflow.action",
        # Other common models
        "res.groups.privilege",  # Security extension
        "digest.digest",
        "digest.tip",
        "fetchmail.server",
        "ir.mail_server",
        "report.paperformat",
        "web.tour",
        "web.tour.step",
    }
    models.update(core_models)

    # Pattern to match _name = "model.name" or _name = 'model.name'
    name_pattern = re.compile(r'_name\s*=\s*["\']([a-z][a-z0-9_.]+)["\']')

    # Also match _inherit = "model.name" (extends existing model)
    inherit_pattern = re.compile(r'_inherit\s*=\s*["\']([a-z][a-z0-9_.]+)["\']')

    # Search in models/, wizards/, and wizard/ directories (git-tracked only)
    search_patterns = ["*/models/*.py", "*/wizards/*.py", "*/wizard/*.py"]

    for pattern in search_patterns:
        py_files = get_git_tracked_files(pattern)
        if not py_files:
            # Fallback if not in git repo
            py_files = list(root_dir.glob(pattern))

        for py_file in py_files:
            py_file = root_dir / py_file if not py_file.is_absolute() else py_file
            if ".venv" in str(py_file) or "venv" in str(py_file):
                continue
            try:
                content = py_file.read_text(encoding="utf-8")

                # Extract _name declarations
                for match in name_pattern.finditer(content):
                    models.add(match.group(1))

                # Extract _inherit declarations (model exists if inherited)
                for match in inherit_pattern.finditer(content):
                    models.add(match.group(1))

            except Exception:
                continue

    return models


def extract_model_refs_from_xml(xml_file: Path) -> list[tuple[str, int, str]]:
    """Extract model references from XML file.

    Returns list of (model_name, line_number, context) tuples.
    """
    refs = []

    try:
        # Parse with line numbers
        with open(xml_file, encoding="utf-8") as f:
            content = f.read()

        # Use regex to find model references with approximate line numbers
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # <record model="model.name">
            match = re.search(r'<record[^>]+model=["\']([a-z][a-z0-9_.]+)["\']', line)
            if match:
                refs.append((match.group(1), i, "record"))

            # <field name="model">model.name</field>
            match = re.search(r'<field\s+name=["\']model["\']>([a-z][a-z0-9_.]+)</field>', line)
            if match:
                refs.append((match.group(1), i, "field[model]"))

            # <field name="res_model">model.name</field>
            match = re.search(r'<field\s+name=["\']res_model["\']>([a-z][a-z0-9_.]+)</field>', line)
            if match:
                refs.append((match.group(1), i, "field[res_model]"))

            # model="model.name" in views
            match = re.search(r'<field\s+name=["\']model["\']>([a-z][a-z0-9_.]+)</field>', line)
            if match:
                refs.append((match.group(1), i, "view[model]"))

    except Exception:
        pass

    return refs


def extract_model_refs_from_csv(csv_file: Path) -> list[tuple[str, int, str]]:
    """Extract model references from ir.model.access.csv file.

    Returns list of (model_name, line_number, context) tuples.
    """
    refs = []

    try:
        with open(csv_file, encoding="utf-8") as f:
            lines = f.readlines()

        header_found = False
        for i, line in enumerate(lines, 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Skip header row (contains "model_id:id")
            if "model_id:id" in line:
                header_found = True
                continue

            if not header_found:
                continue

            # CSV format: id,name,model_id:id,group_id:id,...
            # model_id:id value is typically "module.model_some_model" or "model_some_model"
            parts = line.split(",")
            if len(parts) >= 3:
                model_ref = parts[2].strip()

                # Handle format: module.model_some_model
                if "." in model_ref:
                    model_ref = model_ref.split(".")[-1]

                # Convert model_plasticos_some_model -> plasticos.some.model
                if model_ref.startswith("model_"):
                    model_name = model_ref[6:].replace("_", ".")
                    refs.append((model_name, i, "ir.model.access.csv"))

    except Exception:
        pass

    return refs


def check_orphan_references(root_dir: Path) -> list[dict]:
    """Check for XML and CSV files referencing non-existent models."""
    issues = []

    # Get all defined models
    defined_models = extract_model_names_from_python(root_dir)

    # Check all XML files in data/ and views/ directories (git-tracked only)
    xml_patterns = ["*/data/*.xml", "*/views/*.xml", "*/security/*.xml"]

    for pattern in xml_patterns:
        xml_files = get_git_tracked_files(pattern)
        if not xml_files:
            xml_files = list(root_dir.glob(pattern))

        for xml_file in xml_files:
            xml_file = root_dir / xml_file if not xml_file.is_absolute() else xml_file
            if ".venv" in str(xml_file) or "venv" in str(xml_file):
                continue

            refs = extract_model_refs_from_xml(xml_file)

            for model_name, line_num, context in refs:
                if model_name not in defined_models:
                    # Check if it might be a typo of an existing model
                    suggestions = [m for m in defined_models if model_name.split(".")[-1] in m]

                    issues.append(
                        {
                            "file": str(xml_file.relative_to(root_dir)),
                            "line": line_num,
                            "model": model_name,
                            "context": context,
                            "suggestions": suggestions[:3],
                        }
                    )

    # Check ir.model.access.csv files for orphan model references (git-tracked only)
    csv_files = get_git_tracked_files("*/security/ir.model.access.csv")
    if not csv_files:
        csv_files = list(root_dir.glob("*/security/ir.model.access.csv"))

    for csv_file in csv_files:
        csv_file = root_dir / csv_file if not csv_file.is_absolute() else csv_file
        if ".venv" in str(csv_file) or "venv" in str(csv_file):
            continue

        refs = extract_model_refs_from_csv(csv_file)

        for model_name, line_num, context in refs:
            if model_name not in defined_models:
                suggestions = [m for m in defined_models if model_name.split(".")[-1] in m]

                issues.append(
                    {
                        "file": str(csv_file.relative_to(root_dir)),
                        "line": line_num,
                        "model": model_name,
                        "context": context,
                        "suggestions": suggestions[:3],
                    }
                )

    return issues


def main():
    root_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

    print("=" * 70)
    print("ORPHAN MODEL REFERENCE CHECK")
    print("=" * 70)
    print(f"Scanning: {root_dir.absolute()}")
    print()

    issues = check_orphan_references(root_dir)

    if not issues:
        print("✅ No orphan model references found")
        print()
        print("All XML model references have corresponding Python model definitions.")
        return 0

    print(f"❌ Found {len(issues)} orphan model reference(s)")
    print()

    # Group by file
    by_file = {}
    for issue in issues:
        f = issue["file"]
        if f not in by_file:
            by_file[f] = []
        by_file[f].append(issue)

    for file_path, file_issues in sorted(by_file.items()):
        print(f"📄 {file_path}")
        for issue in file_issues:
            print(f"   Line {issue['line']}: model=\"{issue['model']}\" ({issue['context']})")
            print(f"   ❌ Model '{issue['model']}' not found in codebase")
            if issue["suggestions"]:
                print(f"   💡 Did you mean: {', '.join(issue['suggestions'])}?")
            print()

    print("-" * 70)
    print("HOW TO FIX:")
    print("-" * 70)
    print("""
1. If the model was DEPRECATED:
   - Remove the XML file from the manifest 'data' list
   - Delete the orphaned XML file
   - Run migration to clean up database records

2. If the model should EXIST:
   - Check models/__init__.py imports the model file
   - Check the _name matches exactly (case-sensitive)
   - Check for syntax errors in the model file

3. If it's a TYPO:
   - Correct the model name in the XML file
""")

    return 1


if __name__ == "__main__":
    sys.exit(main())
