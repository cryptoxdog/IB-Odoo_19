#!/usr/bin/env python3
"""
Odoo Comprehensive Bug Audit
============================
Runs all checks and generates unified report.

Combines all audit categories:
1. Field Name Mismatches
2. Required Field Violations
3. Compute/Depends Errors
4. Security/Access Control Gaps
5. Constraint Violations
6. State Machine Errors
7. Onchange/API Errors

Usage:
    python3 scripts/audit/odoo_audit.py [root_dir]

Known False Positive Patterns (for code review agents)
------------------------------------------------------
1. INVALID_DEPENDS for inherited fields:
   - Fields like `document_ids` may be defined via `_inherit` in bridge modules
   - Example: `plasticos_documents/models/transaction_docs_bridge.py` adds
     `document_ids` to `plasticos.transaction` via inheritance
   - The audit now tracks `_inherit` files to reduce these false positives

2. MISSING_ACL for AbstractModel/TransientModel:
   - Service classes using `models.AbstractModel` don't create database tables
   - They don't need ir.model.access.csv entries
   - Examples: plasticos.graph.service, plasticos.compliance.service
   - The audit now skips AbstractModel and TransientModel classes

3. FIELD_NOT_FOUND for action window fields:
   - Views for `ir.actions.act_window` use standard fields like `arch`,
     `res_model`, `view_mode` that aren't defined on custom models
   - These are Odoo framework fields, not bugs

4. Magic fields (create_date, write_date, etc.):
   - These exist on all Odoo models automatically
   - The audit excludes them from INVALID_DEPENDS checks
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path


class OdooAudit:
    """Comprehensive Odoo codebase auditor.

    Limitations:
    - Does not track inherited fields (_inherit). Fields added via inheritance
      in other modules will show as "not found" false positives.
    - Does not track fields from Odoo core models (res.partner, etc.)
    """

    MAGIC_FIELDS = frozenset(
        {
            "id",
            "create_uid",
            "create_date",
            "write_uid",
            "write_date",
            "display_name",
            "__last_update",
            "active",
            "name",
        }
    )

    ODOO_CORE_MODELS = frozenset(
        {
            "res.partner",
            "res.users",
            "res.company",
            "res.country",
            "res.currency",
            "crm.lead",
            "sale.order",
            "purchase.order",
            "account.move",
            "stock.picking",
            "product.product",
            "product.template",
        }
    )

    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)
        self.model_fields = defaultdict(dict)  # model_name -> {field: type}
        self.inherited_fields = defaultdict(dict)  # model_name -> {field: type} (from _inherit)
        self.field_refs = defaultdict(list)  # (model, field) -> [(file, line)]
        self.all_models = set()  # (model_name, py_file, is_abstract)
        self.state_models = {}  # model_name -> {field, values}

    def scan_model_fields(self):
        """Extract all field definitions from Python models."""
        for py_file in self.root_dir.rglob("*/models/*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            model_match = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', content)
            inherit_match = re.search(r'_inherit\s*=\s*["\']([^"\']+)["\']', content)

            if inherit_match and not model_match:
                inherited_model = inherit_match.group(1)
                for match in re.finditer(
                    r"(\w+)\s*=\s*fields\.(Char|Integer|Float|Boolean|Date|Datetime|"
                    r"Many2one|One2many|Many2many|Selection|Text|Html|Binary|Monetary|Reference|Image)",
                    content,
                ):
                    field_name = match.group(1)
                    field_type = match.group(2)
                    self.inherited_fields[inherited_model][field_name] = {"type": field_type}
                continue

            if not model_match:
                continue

            model_name = model_match.group(1)
            is_abstract = "AbstractModel" in content or "TransientModel" in content
            if not model_name.startswith("_"):
                self.all_models.add((model_name, str(py_file), is_abstract))

            for match in re.finditer(
                r"(\w+)\s*=\s*fields\.(Char|Integer|Float|Boolean|Date|Datetime|"
                r"Many2one|One2many|Many2many|Selection|Text|Html|Binary|Monetary|Reference|Image)",
                content,
            ):
                field_name = match.group(1)
                field_type = match.group(2)
                self.model_fields[model_name][field_name] = {"type": field_type}

                if "required=True" in content[match.end() : match.end() + 200]:
                    self.model_fields[model_name][field_name]["required"] = True

            state_match = re.search(
                r"(state|status)\s*=\s*fields\.Selection\(\s*\[(.*?)\]",
                content,
                re.DOTALL,
            )
            if state_match:
                field_name = state_match.group(1)
                values_text = state_match.group(2)
                states = re.findall(r'["\']([^"\']+)["\']', values_text)
                self.state_models[model_name] = {
                    "field": field_name,
                    "values": set(states[::2]) if states else set(),
                }

    def scan_view_field_refs(self):
        """Find all <field name="..."> in XML views."""
        for xml_file in self.root_dir.rglob("*/views/*.xml"):
            if "__pycache__" in str(xml_file):
                continue
            try:
                with open(xml_file, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            current_model = None
            for line_num, line in enumerate(content.split("\n"), 1):
                model_match = re.search(r'<field name="model">([^<]+)</field>', line)
                if model_match:
                    current_model = model_match.group(1)
                    continue

                for match in re.finditer(r'<field\s+name="([^"]+)"', line):
                    field_name = match.group(1)
                    if current_model:
                        self.field_refs[(current_model, field_name)].append((str(xml_file), line_num))

    def check_field_mismatches(self):
        """Find field references that don't exist in model."""
        errors = []
        for (model, field), refs in self.field_refs.items():
            if model not in self.model_fields:
                continue
            if field in self.model_fields[model]:
                continue
            if field in ("id", "create_uid", "create_date", "write_uid", "write_date"):
                continue

            suggestions = []
            if f"{field}_id" in self.model_fields[model]:
                suggestions.append(f"{field}_id")
            if field.endswith("_id"):
                base = field[:-3]
                if base in self.model_fields[model]:
                    suggestions.append(base)

            for file, line in refs:
                errors.append(
                    {
                        "type": "FIELD_NOT_FOUND",
                        "severity": "CRITICAL",
                        "model": model,
                        "field": field,
                        "file": file,
                        "line": line,
                        "message": f"Field '{field}' not defined on model '{model}'",
                        "suggestions": suggestions or "No obvious match found",
                    }
                )
        return errors

    def check_compute_depends(self):
        """Validate @api.depends() field references."""
        errors = []
        for py_file in self.root_dir.rglob("*/models/*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            model_match = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', content)
            if not model_match:
                continue
            model_name = model_match.group(1)

            for match in re.finditer(r"@api\.depends\(([^)]+)\)\s+def\s+(\w+)", content, re.MULTILINE):
                depends_args = match.group(1)
                compute_method = match.group(2)
                field_names = re.findall(r'["\']([^"\']+)["\']', depends_args)

                for field_path in field_names:
                    base_field = field_path.split(".")[0]
                    if base_field in self.MAGIC_FIELDS:
                        continue
                    if base_field in self.model_fields.get(model_name, {}):
                        continue
                    if base_field in self.inherited_fields.get(model_name, {}):
                        continue
                    line_num = content[: match.start()].count("\n") + 1
                    errors.append(
                        {
                            "type": "INVALID_DEPENDS",
                            "severity": "HIGH",
                            "model": model_name,
                            "compute_method": compute_method,
                            "field": base_field,
                            "file": str(py_file),
                            "line": line_num,
                            "message": f"@api.depends references non-existent field '{base_field}'",
                            "note": "May be inherited from another module (_inherit)",
                        }
                    )
        return errors

    def check_security_rules(self):
        """Find models without ACL definitions."""
        errors = []
        secured_models = set()

        for csv_file in self.root_dir.rglob("*/security/*.csv"):
            try:
                with open(csv_file, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue
            for match in re.finditer(r"model_([a-z_0-9]+)", content):
                model_name = match.group(1).replace("_", ".")
                secured_models.add(model_name)

        for model_name, py_file, is_abstract in self.all_models:
            if model_name in secured_models:
                continue
            if is_abstract:
                continue
            if model_name in self.ODOO_CORE_MODELS:
                continue
            errors.append(
                {
                    "type": "MISSING_ACL",
                    "severity": "HIGH",
                    "model": model_name,
                    "file": py_file,
                    "message": f"Model '{model_name}' has no ir.model.access.csv entry",
                    "fix": "Add ACL rules in security/ir.model.access.csv",
                }
            )
        return errors

    def check_constraints(self):
        """Validate constraint decorators and SQL constraints."""
        errors = []
        for py_file in self.root_dir.rglob("*/models/*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            model_match = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', content)
            if not model_match:
                continue
            model_name = model_match.group(1)

            for match in re.finditer(r"@api\.constrains\(([^)]+)\)", content):
                constraint_fields = re.findall(r'["\']([^"\']+)["\']', match.group(1))
                for field in constraint_fields:
                    if field not in self.model_fields.get(model_name, {}):
                        line_num = content[: match.start()].count("\n") + 1
                        errors.append(
                            {
                                "type": "INVALID_CONSTRAINT_FIELD",
                                "severity": "HIGH",
                                "model": model_name,
                                "field": field,
                                "file": str(py_file),
                                "line": line_num,
                                "message": f"@api.constrains references non-existent field '{field}'",
                            }
                        )
        return errors

    def check_onchange_methods(self):
        """Validate @api.onchange decorators."""
        errors = []
        for py_file in self.root_dir.rglob("*/models/*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            model_match = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', content)
            if not model_match:
                continue
            model_name = model_match.group(1)

            for match in re.finditer(r"@api\.onchange\(([^)]+)\)\s+def\s+(\w+)", content):
                onchange_fields = re.findall(r'["\']([^"\']+)["\']', match.group(1))
                method_name = match.group(2)

                for field in onchange_fields:
                    if field not in self.model_fields.get(model_name, {}):
                        line_num = content[: match.start()].count("\n") + 1
                        errors.append(
                            {
                                "type": "INVALID_ONCHANGE_FIELD",
                                "severity": "HIGH",
                                "model": model_name,
                                "method": method_name,
                                "field": field,
                                "file": str(py_file),
                                "line": line_num,
                                "message": f"@api.onchange references non-existent field '{field}'",
                            }
                        )
        return errors

    def check_state_machine(self):
        """Validate state field and button visibility."""
        errors = []
        for xml_file in self.root_dir.rglob("*/views/*.xml"):
            if "__pycache__" in str(xml_file):
                continue
            try:
                with open(xml_file, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            current_model = None
            for line_num, line in enumerate(content.split("\n"), 1):
                model_match = re.search(r'<field name="model">([^<]+)</field>', line)
                if model_match:
                    current_model = model_match.group(1)
                    continue

                if "<button" in line and "invisible=" in line:
                    inv_match = re.search(r'invisible="([^"]+)"', line)
                    if inv_match and current_model and current_model in self.state_models:
                        condition = inv_match.group(1)
                        valid_states = self.state_models[current_model]["values"]
                        for state in re.findall(r"'(\w+)'", condition):
                            if state not in valid_states and valid_states:
                                errors.append(
                                    {
                                        "type": "INVALID_STATE_VALUE",
                                        "severity": "MODERATE",
                                        "model": current_model,
                                        "invalid_state": state,
                                        "file": str(xml_file),
                                        "line": line_num,
                                        "message": f"Button condition references invalid state '{state}'",
                                        "valid_states": list(valid_states),
                                    }
                                )
        return errors

    def run_all_checks(self):
        """Run all audit checks."""
        print("🔍 Scanning model fields...")
        self.scan_model_fields()
        print(f"   Found {len(self.model_fields)} models with {sum(len(f) for f in self.model_fields.values())} fields")

        print("🔍 Scanning view field references...")
        self.scan_view_field_refs()
        print(f"   Found {len(self.field_refs)} field references")

        all_errors = []
        checks = [
            ("Field Mismatches", self.check_field_mismatches),
            ("Compute Depends", self.check_compute_depends),
            ("Security Rules", self.check_security_rules),
            ("Constraints", self.check_constraints),
            ("Onchange Methods", self.check_onchange_methods),
            ("State Machines", self.check_state_machine),
        ]

        for check_name, check_func in checks:
            print(f"🔍 Running: {check_name}...")
            errors = check_func()
            all_errors.extend(errors)
            print(f"   Found {len(errors)} issues")

        return all_errors


def main():
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    auditor = OdooAudit(root_dir)
    errors = auditor.run_all_checks()

    critical = [e for e in errors if e["severity"] == "CRITICAL"]
    high = [e for e in errors if e["severity"] == "HIGH"]
    moderate = [e for e in errors if e["severity"] == "MODERATE"]

    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    print(f"Total Issues: {len(errors)}")
    print(f"  CRITICAL: {len(critical)}")
    print(f"  HIGH: {len(high)}")
    print(f"  MODERATE: {len(moderate)}")

    with open("odoo_audit_report.json", "w") as f:
        json.dump(errors, f, indent=2)
    print("\n📄 JSON report saved to odoo_audit_report.json")

    with open("AUDIT_REPORT.md", "w") as f:
        f.write("# Odoo Codebase Audit Report\n\n")
        f.write(f"**Total Issues:** {len(errors)}\n")
        f.write(f"- CRITICAL: {len(critical)}\n")
        f.write(f"- HIGH: {len(high)}\n")
        f.write(f"- MODERATE: {len(moderate)}\n\n")

        for severity in ["CRITICAL", "HIGH", "MODERATE"]:
            severity_errors = [e for e in errors if e["severity"] == severity]
            if severity_errors:
                f.write(f"## {severity} Issues\n\n")
                for error in severity_errors:
                    f.write(f"### {error['type']}\n")
                    f.write(f"- **Model:** {error.get('model', 'N/A')}\n")
                    f.write(f"- **Message:** {error['message']}\n")
                    f.write(f"- **File:** `{error['file']}:{error.get('line', 'N/A')}`\n")
                    if "fix" in error:
                        f.write(f"- **Fix:** {error['fix']}\n")
                    if "suggestions" in error and error["suggestions"]:
                        f.write(f"- **Suggestions:** {error['suggestions']}\n")
                    f.write("\n")

    print("📄 Markdown report saved to AUDIT_REPORT.md")

    if critical:
        print(f"\n❌ {len(critical)} CRITICAL issues found!")
        sys.exit(1)
    elif high:
        print(f"\n⚠️  {len(high)} HIGH issues found (no critical)")
        sys.exit(0)
    else:
        print("\n✅ No critical or high issues found!")
        sys.exit(0)


if __name__ == "__main__":
    main()
