#!/usr/bin/env python3
"""
XML View Field Reference Integrity Audit v2

More accurate parsing - only checks fields INSIDE <field name="arch"> blocks.
Excludes ir.ui.view metadata fields (model, inherit_id, arch, priority, etc.)
"""

import glob
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Odoo magic/base fields that always exist on all models
ODOO_MAGIC_FIELDS = {
    "id",
    "create_uid",
    "create_date",
    "write_uid",
    "write_date",
    "display_name",
    "__last_update",
    "active",
    "name",
    "sequence",
    # mail.thread fields
    "message_ids",
    "message_follower_ids",
    "activity_ids",
    "message_main_attachment_id",
    "message_partner_ids",
    "message_attachment_count",
    "message_has_error",
    "message_has_error_counter",
    "message_needaction",
    "message_needaction_counter",
    "message_is_follower",
    "activity_state",
    "activity_user_id",
    "activity_type_id",
    "activity_date_deadline",
    "activity_summary",
    "my_activity_date_deadline",
}

# Odoo base model fields that are inherited but not explicitly defined
ODOO_BASE_MODEL_FIELDS = {
    "res.partner": {
        "name",
        "display_name",
        "date",
        "title",
        "parent_id",
        "parent_name",
        "child_ids",
        "ref",
        "lang",
        "tz",
        "user_id",
        "vat",
        "website",
        "comment",
        "category_id",
        "active",
        "employee",
        "function",
        "type",
        "street",
        "street2",
        "zip",
        "city",
        "state_id",
        "country_id",
        "country_code",
        "partner_latitude",
        "partner_longitude",
        "email",
        "email_formatted",
        "is_company",
        "industry_id",
        "company_type",
        "company_id",
        "color",
        "contact_address",
        "commercial_partner_id",
        "commercial_company_name",
        "company_name",
        "barcode",
        "phone",
        "mobile",
        "image_1920",
        "image_1024",
        "image_512",
        "image_256",
        "image_128",
        "avatar_1920",
        "avatar_1024",
        "avatar_512",
        "avatar_256",
        "avatar_128",
        "customer_rank",
        "supplier_rank",
    },
    "sale.order": {
        "name",
        "origin",
        "client_order_ref",
        "state",
        "date_order",
        "user_id",
        "partner_id",
        "partner_invoice_id",
        "partner_shipping_id",
        "pricelist_id",
        "order_line",
        "invoice_ids",
        "invoice_status",
        "note",
        "amount_untaxed",
        "amount_tax",
        "amount_total",
        "currency_id",
        "payment_term_id",
        "company_id",
        "team_id",
        "commitment_date",
        "transaction_ids",
        "tag_ids",
        "campaign_id",
        "source_id",
        "medium_id",
    },
    "purchase.order": {
        "name",
        "origin",
        "partner_ref",
        "date_order",
        "date_approve",
        "partner_id",
        "currency_id",
        "state",
        "order_line",
        "notes",
        "invoice_ids",
        "invoice_status",
        "date_planned",
        "amount_untaxed",
        "amount_tax",
        "amount_total",
        "fiscal_position_id",
        "payment_term_id",
        "user_id",
        "company_id",
    },
    "crm.lead": {
        "name",
        "partner_id",
        "active",
        "email_from",
        "website",
        "team_id",
        "description",
        "contact_name",
        "partner_name",
        "type",
        "priority",
        "date_closed",
        "stage_id",
        "user_id",
        "probability",
        "expected_revenue",
        "date_deadline",
        "color",
        "street",
        "street2",
        "zip",
        "city",
        "state_id",
        "country_id",
        "phone",
        "mobile",
        "function",
        "title",
        "company_id",
        "tag_ids",
        "campaign_id",
        "source_id",
        "medium_id",
        "company_name",  # This is a native crm.lead field
    },
    "stock.picking": {
        "name",
        "origin",
        "note",
        "move_type",
        "state",
        "group_id",
        "priority",
        "scheduled_date",
        "date_deadline",
        "has_deadline_issue",
        "date",
        "date_done",
        "location_id",
        "location_dest_id",
        "move_ids",
        "move_ids_without_package",
        "has_scrap_move",
        "picking_type_id",
        "picking_type_code",
        "picking_type_entire_packs",
        "partner_id",
        "company_id",
        "user_id",
        "move_line_ids",
        "move_line_ids_without_package",
        "move_line_nosuggest_ids",
        "move_line_exist",
        "has_packages",
        "show_check_availability",
        "show_mark_as_todo",
        "show_validate",
        "immediate_transfer",
        "show_operations",
        "show_reserved",
        "show_lots_text",
        "owner_id",
        "printed",
        "signature",
        "is_locked",
        "products_availability",
        "products_availability_state",
        "json_popover",
        "package_level_ids",
        "package_level_ids_details",
        "has_tracking",
        "backorder_id",
        "backorder_ids",
        "return_id",
        "return_ids",
    },
}

# ir.ui.view metadata fields - NOT model fields
VIEW_METADATA_FIELDS = {
    "model",
    "inherit_id",
    "arch",
    "priority",
    "mode",
    "groups_id",
    "res_model",
    "view_mode",
    "target",
    "binding_model_id",
    "binding_view_types",
    "context",
    "domain",
    "limit",
    "help",
    "type",
    "view_id",
    "search_view_id",
    "act_window_id",
}

# Expression keywords to exclude
EXPR_KEYWORDS = {
    "True",
    "False",
    "None",
    "true",
    "false",
    "null",
    "and",
    "or",
    "not",
    "in",
    "is",
    "if",
    "else",
    "lt",
    "gt",
    "le",
    "ge",
    "eq",
    "ne",  # comparison operators in expressions
    "context",
    "parent",
    "self",
    "env",
    "user",
    "uid",
    "sum",
    "avg",
    "count",
    "min",
    "max",
}


def extract_model_fields(repo_root: Path) -> dict[str, set[str]]:
    """Extract all field definitions from plasticos_*/models/*.py files."""
    model_fields = defaultdict(set)
    model_inherits = defaultdict(list)

    pattern = repo_root / "plasticos_*/models/*.py"
    py_files = glob.glob(str(pattern))

    name_pattern = re.compile(r'_name\s*=\s*["\']([^"\']+)["\']')
    inherit_pattern = re.compile(r'_inherit\s*=\s*["\']([^"\']+)["\']')
    inherit_list_pattern = re.compile(r"_inherit\s*=\s*\[([^\]]+)\]")
    field_pattern = re.compile(
        r"^\s+(\w+)\s*=\s*fields\.(Char|Text|Html|Integer|Float|Boolean|Date|Datetime|Binary|Selection|Many2one|Many2many|One2many|Reference|Monetary|Image|Json|Serialized|Properties|PropertiesDefinition)",
        re.MULTILINE,
    )

    for py_file in py_files:
        if "__init__" in py_file:
            continue

        try:
            with open(py_file, encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue

        model_name = None
        name_match = name_pattern.search(content)
        if name_match:
            model_name = name_match.group(1)

        inherit_match = inherit_pattern.search(content)
        if inherit_match:
            inherited = inherit_match.group(1)
            if model_name:
                model_inherits[model_name].append(inherited)
            else:
                model_name = inherited

        inherit_list_match = inherit_list_pattern.search(content)
        if inherit_list_match:
            inherits_str = inherit_list_match.group(1)
            for m in re.findall(r'["\']([^"\']+)["\']', inherits_str):
                if model_name:
                    model_inherits[model_name].append(m)

        if not model_name:
            continue

        for match in field_pattern.finditer(content):
            field_name = match.group(1)
            model_fields[model_name].add(field_name)

    # Merge inherited fields
    for model, parents in model_inherits.items():
        for parent in parents:
            if parent in model_fields:
                model_fields[model].update(model_fields[parent])

    # Add magic fields
    for model in model_fields:
        model_fields[model].update(ODOO_MAGIC_FIELDS)

    return dict(model_fields)


def extract_arch_field_refs(xml_content: str, file_path: str) -> list[dict]:
    """Extract field references from INSIDE arch blocks only."""
    refs = []

    # Find all ir.ui.view records
    view_pattern = re.compile(r'<record[^>]*model\s*=\s*["\']ir\.ui\.view["\'][^>]*>.*?</record>', re.DOTALL)

    for view_match in view_pattern.finditer(xml_content):
        view_block = view_match.group(0)
        view_start = view_match.start()

        # Extract target model
        model_match = re.search(r'<field\s+name\s*=\s*["\']model["\']>([^<]+)</field>', view_block)
        if not model_match:
            continue
        target_model = model_match.group(1).strip()

        # Extract arch content
        arch_match = re.search(r'<field\s+name\s*=\s*["\']arch["\'][^>]*>(.*?)</field>', view_block, re.DOTALL)
        if not arch_match:
            continue
        arch_content = arch_match.group(1)
        arch_start = view_start + arch_match.start(1)

        # Find field tags inside arch
        field_tag_pattern = re.compile(r'<field\s+name\s*=\s*["\'](\w+)["\']')
        for field_match in field_tag_pattern.finditer(arch_content):
            field_name = field_match.group(1)
            if field_name not in VIEW_METADATA_FIELDS and field_name not in EXPR_KEYWORDS:
                line_num = xml_content[: arch_start + field_match.start()].count("\n") + 1
                refs.append(
                    {
                        "file": file_path,
                        "line": line_num,
                        "field": field_name,
                        "model": target_model,
                        "context": "field_tag",
                    }
                )

        # Find field refs in invisible/readonly/required/decoration attributes
        attr_pattern = re.compile(
            r'(?:invisible|readonly|required|column_invisible|decoration-\w+)\s*=\s*["\']([^"\']+)["\']'
        )
        field_in_expr = re.compile(r"\b([a-z_][a-z0-9_]*)\b")

        for attr_match in attr_pattern.finditer(arch_content):
            expr = attr_match.group(1)
            line_num = xml_content[: arch_start + attr_match.start()].count("\n") + 1

            for field_match in field_in_expr.finditer(expr):
                field_name = field_match.group(1)
                if (
                    field_name not in VIEW_METADATA_FIELDS
                    and field_name not in EXPR_KEYWORDS
                    and not field_name.isdigit()
                    and len(field_name) > 1
                ):
                    refs.append(
                        {
                            "file": file_path,
                            "line": line_num,
                            "field": field_name,
                            "model": target_model,
                            "context": "attribute",
                        }
                    )

    return refs


def cross_reference(model_fields: dict[str, set[str]], field_refs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Cross-reference field refs against model fields."""
    missing = []
    verified = []
    seen = set()

    for ref in field_refs:
        key = (ref["file"], ref["field"], ref["model"])
        if key in seen:
            continue
        seen.add(key)

        model = ref["model"]
        field = ref["field"]

        # Handle dotted refs
        if "." in field:
            field = field.split(".")[0]

        model_field_set = model_fields.get(model, set()) | ODOO_MAGIC_FIELDS
        # Add Odoo base model fields if applicable
        if model in ODOO_BASE_MODEL_FIELDS:
            model_field_set = model_field_set | ODOO_BASE_MODEL_FIELDS[model]

        if field in model_field_set:
            verified.append(ref)
        else:
            if model not in model_fields:
                ref["notes"] = f"Model '{model}' not in registry"
            else:
                ref["notes"] = "Field not defined on model"
            missing.append(ref)

    return missing, verified


def generate_report(missing: list[dict], verified: list[dict], model_fields: dict, xml_file_count: int) -> str:
    """Generate the structured audit report."""
    # Filter out false positives from missing
    real_missing = []
    for ref in missing:
        # Skip if model not in our registry (likely Odoo base or wizard)
        if "not in registry" in ref.get("notes", ""):
            continue
        real_missing.append(ref)

    report = []
    report.append("# FIELD REFERENCE AUDIT REPORT")
    report.append("=" * 50)
    report.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append("**Branch:** staging")
    report.append("**Scope:** All plasticos_*/views/*.xml files")
    report.append("")

    report.append("## Summary")
    report.append(f"- **XML files scanned:** {xml_file_count}")
    report.append(f"- **Models in registry:** {len(model_fields)}")
    report.append(f"- **Total field references checked:** {len(real_missing) + len(verified)}")
    report.append(f"- **Fields verified OK:** {len(verified)}")
    report.append(f"- **Fields MISSING (in known models):** {len(real_missing)}")
    report.append(f"- **Skipped (unknown models/wizards):** {len(missing) - len(real_missing)}")
    report.append("")

    if real_missing:
        report.append("## MISSING FIELDS (CRITICAL — will crash registry)")
        report.append("")
        report.append("| # | XML File | Line | Field | Model | Notes |")
        report.append("|---|----------|------|-------|-------|-------|")

        for i, ref in enumerate(real_missing, 1):
            file_short = ref["file"].replace("/Users/ib-mac/Dropbox/Odoo_19_ReBoot/", "")
            notes = ref.get("notes", "")
            report.append(f"| {i} | `{file_short}` | ~{ref['line']} | `{ref['field']}` | `{ref['model']}` | {notes} |")

        report.append("")
        report.append("## Recommended Fixes")
        report.append("")

        by_file = defaultdict(list)
        for ref in real_missing:
            by_file[ref["file"]].append(ref)

        for file_path, refs in sorted(by_file.items()):
            file_short = file_path.replace("/Users/ib-mac/Dropbox/Odoo_19_ReBoot/", "")
            report.append(f"### `{file_short}`")
            for ref in refs:
                report.append(f"- **{ref['field']}** on `{ref['model']}`:")
                report.append("  - Option A: Add field to Python model")
                report.append("  - Option B: Remove field reference from view")
            report.append("")
    else:
        report.append("## ✅ NO MISSING FIELDS FOUND")
        report.append("")
        report.append("All field references in XML views have corresponding field definitions.")

    report.append("")
    report.append("## Models in Registry")
    report.append("")
    for model in sorted(model_fields.keys()):
        field_count = len(model_fields[model])
        report.append(f"- `{model}`: {field_count} fields")

    return "\n".join(report)


def main():
    repo_root = Path("/Users/ib-mac/Dropbox/Odoo_19_ReBoot")

    print("Phase 1: Building model → fields map...")
    model_fields = extract_model_fields(repo_root)
    print(f"  Found {len(model_fields)} models")

    print("Phase 2: Extracting arch field references...")
    xml_files = glob.glob(str(repo_root / "plasticos_*/views/*.xml"))
    all_refs = []
    for xml_file in xml_files:
        try:
            with open(xml_file, encoding="utf-8") as f:
                content = f.read()
            refs = extract_arch_field_refs(content, xml_file)
            all_refs.extend(refs)
        except Exception as e:
            print(f"  Error parsing {xml_file}: {e}")
    print(f"  Found {len(all_refs)} field references")

    print("Phase 3: Cross-referencing...")
    missing, verified = cross_reference(model_fields, all_refs)
    print(f"  Missing: {len(missing)}, Verified: {len(verified)}")

    print("Phase 4: Generating report...")
    report = generate_report(missing, verified, model_fields, len(xml_files))

    report_path = repo_root / "reports" / "GMP-Report-AUDIT-XML-Field-References.md"
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, "w") as f:
        f.write(report)

    print(f"\nReport saved to: {report_path}")
    print("\n" + "=" * 50)
    print(report)


if __name__ == "__main__":
    main()
