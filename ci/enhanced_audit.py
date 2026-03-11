#!/usr/bin/env python3
"""
Odoo Comprehensive Bug Audit (Production Version)
Enhanced with core module whitelist and smarter heuristics.
"""

import ast
import json
import re
from collections import defaultdict
from pathlib import Path

# ============================================================================
# ODOO CORE MODULES WHITELIST
# ============================================================================

ODOO_CORE_MODULES = {
    # Base modules
    "base",
    "web",
    "base_setup",
    "bus",
    "web_tour",
    "web_editor",
    # CRM & Sales
    "crm",
    "sale",
    "sale_management",
    "sale_crm",
    "sale_stock",
    "sale_timesheet",
    "sales_team",
    # Accounting
    "account",
    "account_payment",
    "account_asset",
    "account_budget",
    "account_invoice_extract",
    "account_accountant",
    # Inventory & Manufacturing
    "stock",
    "stock_account",
    "mrp",
    "quality",
    "quality_control",
    "purchase",
    "purchase_stock",
    # HR
    "hr",
    "hr_attendance",
    "hr_timesheet",
    "hr_recruitment",
    "hr_holidays",
    "hr_expense",
    "hr_payroll",
    # Project Management
    "project",
    "project_timesheet",
    "project_forecast",
    # Marketing
    "mass_mailing",
    "marketing_automation",
    "social",
    "website",
    "website_sale",
    "website_blog",
    "website_event",
    # eCommerce
    "payment",
    "delivery",
    "website_payment",
    # Communication
    "mail",
    "sms",
    "voip",
    "calendar",
    "contacts",
    # Utilities
    "utm",
    "portal",
    "digest",
    "web_unsplash",
    "rating",
    "survey",
    "documents",
    "spreadsheet",
    "sign",
    # Point of Sale
    "point_of_sale",
    "pos_restaurant",
    "pos_mercury",
    # Field Service
    "helpdesk",
    "planning",
    "appointment",
    # Reporting
    "board",
    "dashboard",
    "reporting",
    "analytic",
    # Technical
    "resource",
    "product",
    "uom",
    "barcodes",
    "web_grid",
    "web_gantt",
    "web_cohort",
    "web_dashboard",
    "web_map",
}

# ============================================================================
# FIELD AUDIT WITH ENHANCED PARSING
# ============================================================================


class EnhancedFieldAudit:
    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)
        self.modules = {}
        self.model_fields = defaultdict(dict)
        self.xmlid_defs = defaultdict(set)
        self.xmlid_refs = defaultdict(list)
        self.view_inherits = []

    def scan_modules(self):
        """Find all Odoo modules with enhanced metadata"""
        for manifest in self.root_dir.rglob("__manifest__.py"):
            if "__pycache__" in str(manifest):
                continue

            module_dir = manifest.parent
            module_name = module_dir.name

            with open(manifest, encoding="utf-8") as f:
                try:
                    manifest_data = ast.literal_eval(f.read())
                    self.modules[module_name] = {
                        "path": module_dir,
                        "depends": manifest_data.get("depends", []),
                        "data": manifest_data.get("data", []),
                        "version": manifest_data.get("version", "unknown"),
                    }
                except Exception as e:
                    print(f"⚠️  Failed to parse {manifest}: {e}")

    def scan_model_fields(self):
        """Extract field definitions with enhanced metadata"""
        for module_name, module_data in self.modules.items():
            module_path = module_data["path"]

            for py_file in module_path.rglob("models/*.py"):
                if "__pycache__" in str(py_file):
                    continue

                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                    # Find model name
                    model_match = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', content)
                    if not model_match:
                        # Try _inherit for extensions
                        inherit_match = re.search(r'_inherit\s*=\s*["\']([^"\']+)["\']', content)
                        if inherit_match:
                            model_name = inherit_match.group(1)
                        else:
                            continue
                    else:
                        model_name = model_match.group(1)

                    # Find all field definitions with metadata
                    for match in re.finditer(
                        r"(\w+)\s*=\s*fields\.(Char|Integer|Float|Boolean|Date|Datetime|Many2one|One2many|Many2many|Selection|Text|Html|Binary|Monetary|Image|Reference)\s*\((.*?)\)",
                        content,
                        re.DOTALL,
                    ):
                        field_name = match.group(1)
                        field_type = match.group(2)
                        field_args = match.group(3)

                        # Parse field metadata
                        required = "required=True" in field_args
                        readonly = "readonly=True" in field_args
                        compute = "compute=" in field_args

                        self.model_fields[model_name][field_name] = {
                            "type": field_type,
                            "required": required,
                            "readonly": readonly,
                            "compute": compute,
                            "module": module_name,
                            "file": str(py_file.relative_to(self.root_dir)),
                        }

    def scan_xmlid_definitions(self):
        """Extract XML IDs with line numbers"""
        for module_name, module_data in self.modules.items():
            module_path = module_data["path"]

            for xml_file in module_path.rglob("*.xml"):
                if "__pycache__" in str(xml_file):
                    continue

                with open(xml_file, encoding="utf-8") as f:
                    for _line_num, line in enumerate(f, 1):
                        match = re.search(r'<record\s+id="([^"]+)"', line)
                        if match:
                            xmlid = match.group(1)
                            self.xmlid_defs[module_name].add(xmlid)

    def scan_xmlid_references(self):
        """Extract XML ID references with context"""
        for module_name, module_data in self.modules.items():
            module_path = module_data["path"]

            for xml_file in module_path.rglob("*.xml"):
                if "__pycache__" in str(xml_file):
                    continue

                with open(xml_file, encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        # Find all ref="..." attributes
                        for match in re.finditer(r'ref="([^"]+)"', line):
                            xmlid = match.group(1)
                            self.xmlid_refs[xmlid].append(
                                (str(xml_file.relative_to(self.root_dir)), line_num, module_name)
                            )

                        # Track view inheritance
                        if "inherit_id" in line and "ref=" in line:
                            ref_match = re.search(r'ref="([^"]+)"', line)
                            if ref_match:
                                parent_xmlid = ref_match.group(1)
                                self.view_inherits.append(
                                    (module_name, parent_xmlid, str(xml_file.relative_to(self.root_dir)), line_num)
                                )

    def check_dangling_refs(self):
        """Find XML IDs referenced but not defined (with core whitelist)"""
        errors = []

        for xmlid, references in self.xmlid_refs.items():
            if "." not in xmlid:
                continue

            module, record_id = xmlid.split(".", 1)

            # Skip model_* XML IDs - auto-generated by Odoo from ir.model.access.csv
            if record_id.startswith("model_"):
                continue

            # SKIP ODOO CORE MODULES
            if module in ODOO_CORE_MODULES:
                continue

            # Check if custom module exists
            if module not in self.modules:
                for file, line, ref_module in references:
                    errors.append(
                        {
                            "type": "MISSING_MODULE",
                            "severity": "CRITICAL",
                            "xmlid": xmlid,
                            "module": module,
                            "file": file,
                            "line": line,
                            "referencing_module": ref_module,
                            "message": f"Custom module '{module}' not found (or misspelled?)",
                        }
                    )
                continue

            # Check if XML ID is defined
            if record_id not in self.xmlid_defs[module]:
                for file, line, ref_module in references:
                    errors.append(
                        {
                            "type": "MISSING_XMLID",
                            "severity": "CRITICAL",
                            "xmlid": xmlid,
                            "file": file,
                            "line": line,
                            "referencing_module": ref_module,
                            "message": f"XML ID '{record_id}' not defined in module '{module}'",
                            "suggestion": f"Check for typos or add definition in {module}/",
                        }
                    )

        return errors

    def check_missing_dependencies(self):
        """Find undeclared dependencies (with core whitelist)"""
        errors = []

        for child_module, parent_xmlid, file, line in self.view_inherits:
            if "." not in parent_xmlid:
                continue

            parent_module = parent_xmlid.split(".")[0]

            # Skip self-references
            if parent_module == child_module:
                continue

            # SKIP ODOO CORE MODULES (assumed available)
            if parent_module in ODOO_CORE_MODULES:
                continue

            # Check declared dependencies
            depends = self.modules[child_module]["depends"]
            if parent_module not in depends:
                errors.append(
                    {
                        "type": "MISSING_DEPENDENCY",
                        "severity": "CRITICAL",
                        "child_module": child_module,
                        "parent_module": parent_module,
                        "parent_xmlid": parent_xmlid,
                        "file": file,
                        "line": line,
                        "message": f"Module '{child_module}' inherits from '{parent_module}' but doesn't declare it",
                        "fix": f"Add '{parent_module}' to 'depends' in {child_module}/__manifest__.py",
                    }
                )

        return errors

    def check_field_references(self):
        """Find view fields that don't exist in models"""
        errors = []
        current_model = None

        for _module_name, module_data in self.modules.items():
            module_path = module_data["path"]

            for xml_file in module_path.rglob("views/*.xml"):
                if "__pycache__" in str(xml_file):
                    continue

                with open(xml_file, encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        # Track current model context
                        model_match = re.search(r'<field name="model">([^<]+)</field>', line)
                        if model_match:
                            current_model = model_match.group(1)

                        # Find field references
                        if current_model and "<field" in line and "name=" in line:
                            field_match = re.search(r'<field\s+name="([^"]+)"', line)
                            if not field_match:
                                continue

                            field_name = field_match.group(1)

                            # Skip standard Odoo fields and view/action definition fields
                            if field_name in [
                                "name",
                                "active",
                                "id",
                                "create_uid",
                                "write_uid",
                                "create_date",
                                "write_date",
                                "__last_update",
                                "model",
                                "arch",
                                "res_model",
                                "view_mode",
                                "view_id",
                                "domain",
                                "context",
                                "target",
                                "type",
                                "priority",
                                "inherit_id",
                                "mode",
                                "groups_id",
                                "help",
                                "limit",
                                "search_view_id",
                                "view_type",
                                "multi",
                                "binding_model_id",
                                "binding_type",
                                "binding_view_types",
                                "res_id",
                            ]:
                                continue

                            # Check if field exists
                            if current_model in self.model_fields:
                                if field_name not in self.model_fields[current_model]:
                                    # Look for common typos
                                    suggestions = []
                                    if f"{field_name}_id" in self.model_fields[current_model]:
                                        suggestions.append(f"{field_name}_id")
                                    if field_name.endswith("_id"):
                                        base = field_name[:-3]
                                        if base in self.model_fields[current_model]:
                                            suggestions.append(base)

                                    errors.append(
                                        {
                                            "type": "FIELD_NOT_FOUND",
                                            "severity": "CRITICAL",
                                            "model": current_model,
                                            "field": field_name,
                                            "file": str(xml_file.relative_to(self.root_dir)),
                                            "line": line_num,
                                            "message": f"Field '{field_name}' not defined on '{current_model}'",
                                            "suggestions": suggestions if suggestions else [],
                                        }
                                    )

        return errors

    def run_audit(self):
        """Run comprehensive audit"""
        print("🔍 Scanning modules...")
        self.scan_modules()
        print(f"   Found {len(self.modules)} custom modules")

        print("🔍 Scanning model fields...")
        self.scan_model_fields()
        total_models = len(self.model_fields)
        total_fields = sum(len(fields) for fields in self.model_fields.values())
        print(f"   Found {total_models} models with {total_fields} fields")

        print("🔍 Scanning XML ID definitions...")
        self.scan_xmlid_definitions()
        total_defs = sum(len(v) for v in self.xmlid_defs.values())
        print(f"   Found {total_defs} XML ID definitions")

        print("🔍 Scanning XML ID references...")
        self.scan_xmlid_references()
        print(f"   Found {len(self.xmlid_refs)} unique XML ID references")

        print("\n📋 Running checks...\n")

        all_errors = []

        checks = [
            ("Dangling XML IDs", self.check_dangling_refs),
            ("Missing Dependencies", self.check_missing_dependencies),
            # Field reference check disabled - requires AST parsing for accuracy
            # ("Invalid Field References", self.check_field_references),
        ]

        for check_name, check_func in checks:
            print(f"   ⚙️  {check_name}...")
            errors = check_func()
            all_errors.extend(errors)

            # Count by severity
            critical = sum(1 for e in errors if e["severity"] == "CRITICAL")
            high = sum(1 for e in errors if e["severity"] == "HIGH")

            if critical > 0:
                print(f"      ❌ {critical} CRITICAL")
            if high > 0:
                print(f"      ⚠️  {high} HIGH")
            if critical == 0 and high == 0:
                print("      ✅ Clean")

        return all_errors

    def generate_report(self, errors):
        """Generate human-readable report"""
        if not errors:
            print("\n✅ No errors found! Your codebase is clean.\n")
            return

        print(f"\n{'=' * 80}")
        print("AUDIT SUMMARY")
        print(f"{'=' * 80}\n")

        # Group by severity
        by_severity = defaultdict(list)
        for error in errors:
            by_severity[error["severity"]].append(error)

        for severity in ["CRITICAL", "HIGH", "MODERATE", "LOW"]:
            if severity not in by_severity:
                continue

            print(f"\n{severity} ISSUES: {len(by_severity[severity])}\n")
            print("-" * 80)

            for i, error in enumerate(by_severity[severity][:10], 1):  # Show first 10
                print(f"\n{i}. [{error['type']}] {error['message']}")
                print(f"   📄 {error['file']}:{error.get('line', 'N/A')}")
                if "fix" in error:
                    print(f"   💡 {error['fix']}")
                if error.get("suggestions"):
                    print(f"   💡 Try: {', '.join(error['suggestions'])}")

            if len(by_severity[severity]) > 10:
                print(f"\n   ... and {len(by_severity[severity]) - 10} more")


if __name__ == "__main__":
    import sys

    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."

    auditor = EnhancedFieldAudit(root_dir)
    errors = auditor.run_audit()
    auditor.generate_report(errors)

    # Save JSON report
    with open("odoo_audit_report.json", "w") as f:
        json.dump(errors, f, indent=2)

    print("\n📄 Full report saved to odoo_audit_report.json")

    # Exit with error code if critical issues found
    critical_count = sum(1 for e in errors if e["severity"] == "CRITICAL")
    sys.exit(1 if critical_count > 0 else 0)
