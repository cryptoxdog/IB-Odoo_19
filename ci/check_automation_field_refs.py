#!/usr/bin/env python3
"""
CI Check: Automation Field Reference Validation
================================================

Catches field name mismatches in base.automation rules and ir.actions.server code:

1. base.automation filter_domain / filter_pre_domain referencing fields that
   don't exist on the target model (causes install crash or silent no-op).

2. ir.actions.server inline Python code accessing fields via dot notation
   (records.field_name, record.field_name) that don't exist on the model.

What this prevents:
    - AttributeError at runtime when automation fires
    - Domain validation errors on module install
    - Silent dead automations that never trigger

Exit codes:
    0 = PASS
    1 = FAIL (blocking issues found)
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from _git_utils import get_git_tracked_files


def _extract_all_fields(root_dir: Path) -> dict[str, set[str]]:
    """Build {model_name: {field1, field2, ...}} from Python model files.

    Includes fields from _inherit extensions (merged into the inherited model).
    """
    model_fields: dict[str, set[str]] = {}

    # Odoo core fields present on all models
    UNIVERSAL_FIELDS = {
        "id",
        "create_date",
        "create_uid",
        "write_date",
        "write_uid",
        "display_name",
        "name",
        "__last_update",
    }

    # Common fields by model (core Odoo fields not defined in our codebase)
    CORE_MODEL_FIELDS: dict[str, set[str]] = {
        "purchase.order": {
            "name",
            "state",
            "partner_id",
            "date_order",
            "amount_total",
            "order_line",
            "picking_ids",
            "invoice_ids",
            "user_id",
            "company_id",
            "currency_id",
            "notes",
            "date_planned",
            "message_ids",
            "activity_ids",
        },
        "sale.order": {
            "name",
            "state",
            "partner_id",
            "date_order",
            "amount_total",
            "order_line",
            "picking_ids",
            "invoice_ids",
            "user_id",
            "company_id",
            "currency_id",
            "note",
            "partner_shipping_id",
            "partner_invoice_id",
            "message_ids",
            "activity_ids",
            "pricelist_id",
            "payment_term_id",
        },
        "stock.picking": {
            "name",
            "state",
            "partner_id",
            "picking_type_id",
            "picking_type_code",
            "location_id",
            "location_dest_id",
            "move_ids",
            "move_line_ids",
            "sale_id",
            "purchase_id",
            "origin",
            "scheduled_date",
            "date_done",
            "user_id",
            "company_id",
            "message_ids",
            "activity_ids",
        },
        "account.move": {
            "name",
            "state",
            "partner_id",
            "move_type",
            "date",
            "invoice_date",
            "invoice_date_due",
            "amount_total",
            "amount_residual",
            "line_ids",
            "invoice_line_ids",
            "journal_id",
            "company_id",
            "currency_id",
            "user_id",
            "message_ids",
            "activity_ids",
            "ref",
        },
    }

    field_pattern = re.compile(r"(\w+)\s*=\s*fields\.\w+\s*\(")
    name_pattern = re.compile(r'_name\s*=\s*["\']([a-z][a-z0-9_.]+)["\']')
    inherit_pattern = re.compile(r'_inherit\s*=\s*["\']([a-z][a-z0-9_.]+)["\']')

    # Seed core model fields
    for model, fields in CORE_MODEL_FIELDS.items():
        model_fields[model] = fields | UNIVERSAL_FIELDS

    py_files = get_git_tracked_files("*/models/*.py")
    if not py_files:
        py_files = list(root_dir.glob("plasticos_*/models/*.py"))

    for py_file in py_files:
        py_path = root_dir / py_file if not py_file.is_absolute() else py_file
        if ".venv" in str(py_path):
            continue
        try:
            content = py_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Determine model name(s) this file contributes to
        targets: list[str] = []
        for m in name_pattern.finditer(content):
            targets.append(m.group(1))
        for m in inherit_pattern.finditer(content):
            targets.append(m.group(1))

        # Extract field definitions
        file_fields: set[str] = set()
        for m in field_pattern.finditer(content):
            file_fields.add(m.group(1))

        for model in targets:
            if model not in model_fields:
                model_fields[model] = set(UNIVERSAL_FIELDS)
            model_fields[model].update(file_fields)

    return model_fields


def _parse_domain_fields(domain_str: str) -> list[str]:
    """Extract field names from an Odoo domain string like "[('field', '=', val)]"."""
    fields = []
    for m in re.finditer(r"\(\s*['\"](\w+)['\"]", domain_str):
        fields.append(m.group(1))
    return fields


def _extract_code_field_refs(code: str, model_fields: set[str]) -> list[str]:
    """Extract field references from server action Python code.

    Looks for patterns like:
    - records.filtered(lambda p: p.FIELD)
    - record.FIELD
    - picking.FIELD
    - po.FIELD, so.FIELD, tx.FIELD, invoice.FIELD, claim.FIELD
    """
    suspect_refs = []

    # Lambda field access: lambda x: x.field_name
    for m in re.finditer(r"lambda\s+(\w+)\s*:.*?\b\1\.(\w+)", code):
        field = m.group(2)
        if (
            field not in model_fields
            and not field.startswith("_")
            and field
            not in {
                "message_ids",
                "message_post",
                "write",
                "read",
                "search",
                "browse",
                "create",
                "unlink",
                "copy",
                "mapped",
                "filtered",
                "sorted",
                "exists",
                "ensure_one",
                "with_context",
                "sudo",
                "env",
                "id",
                "ids",
                "name",
                "display_name",
                "body",
                "subject",
                "partner_ids",
                "subtype_xmlid",
                "email",
                "phone",
                "mobile",
                "send_mail",
                "force_send",
            }
        ):
            suspect_refs.append(field)

    return suspect_refs


def _resolve_model_from_ref(model_id_ref: str) -> str | None:
    """Convert model_id ref like 'stock.model_stock_picking' to 'stock.picking'."""
    if "." not in model_id_ref:
        return None
    _, model_part = model_id_ref.split(".", 1)
    if not model_part.startswith("model_"):
        return None
    return model_part[6:].replace("_", ".")


def check_automation_field_refs(root_dir: Path) -> list[dict]:
    """Check base.automation domains and server action code for invalid field refs."""
    issues = []
    model_fields = _extract_all_fields(root_dir)

    xml_files = get_git_tracked_files("*/data/*.xml")
    if not xml_files:
        xml_files = list(root_dir.glob("plasticos_*/data/*.xml"))

    for xml_file in xml_files:
        xml_path = root_dir / xml_file if not xml_file.is_absolute() else xml_file
        if ".venv" in str(xml_path):
            continue

        try:
            tree = ET.parse(xml_path)  # nosec B314
        except ET.ParseError:
            continue

        root = tree.getroot()

        # Collect server actions: {xmlid: (model_name, code)}
        server_actions: dict[str, tuple[str, str]] = {}
        for rec in root.findall(".//record"):
            if rec.get("model") != "ir.actions.server":
                continue
            rec_id = rec.get("id", "")
            model_ref = ""
            code = ""
            for field in rec.findall("field"):
                if field.get("name") == "model_id":
                    model_ref = field.get("ref", "")
                elif field.get("name") == "code":
                    code = (field.text or "").strip()

            model_name = _resolve_model_from_ref(model_ref) if model_ref else None
            if model_name and code:
                server_actions[rec_id] = (model_name, code)

        # Check base.automation domains
        for rec in root.findall(".//record"):
            if rec.get("model") != "base.automation":
                continue
            rec_id = rec.get("id", "")

            model_ref = ""
            for field in rec.findall("field"):
                if field.get("name") == "model_id":
                    model_ref = field.get("ref", "")

            model_name = _resolve_model_from_ref(model_ref) if model_ref else None
            if not model_name:
                continue

            known_fields = model_fields.get(model_name, set())
            if not known_fields:
                continue

            for field in rec.findall("field"):
                fname = field.get("name", "")
                if fname in ("filter_domain", "filter_pre_domain"):
                    domain_text = field.text or ""
                    for domain_field in _parse_domain_fields(domain_text):
                        if domain_field not in known_fields:
                            issues.append(
                                {
                                    "file": str(xml_path.relative_to(root_dir)),
                                    "record_id": rec_id,
                                    "type": "domain_field",
                                    "model": model_name,
                                    "field": domain_field,
                                    "context": f"{fname}: {domain_text.strip()[:80]}",
                                    "severity": "BLOCKER",
                                }
                            )

        # Check server action code field references
        for action_id, (model_name, code) in server_actions.items():
            known_fields = model_fields.get(model_name, set())
            if not known_fields:
                continue

            suspect = _extract_code_field_refs(code, known_fields)
            for field in suspect:
                issues.append(
                    {
                        "file": str(xml_path.relative_to(root_dir)),
                        "record_id": action_id,
                        "type": "code_field",
                        "model": model_name,
                        "field": field,
                        "context": f"server action code references '{field}'",
                        "severity": "HIGH",
                    }
                )

    return issues


def main():
    root_dir = Path(".")

    print("=" * 70)
    print("AUTOMATION FIELD REFERENCE CHECK")
    print("=" * 70)
    print()

    issues = check_automation_field_refs(root_dir)

    if not issues:
        print("✅ PASSED: All automation field references are valid")
        sys.exit(0)

    blockers = [i for i in issues if i["severity"] == "BLOCKER"]
    highs = [i for i in issues if i["severity"] == "HIGH"]

    print(f"❌ Found {len(issues)} automation field reference issues")
    print(f"   BLOCKER: {len(blockers)}  |  HIGH: {len(highs)}")
    print()

    for issue in issues:
        sev = issue["severity"]
        print(f"  [{sev}] {issue['file']} :: {issue['record_id']}")
        print(f"         Model: {issue['model']}")
        print(f"         Field '{issue['field']}' not found on model")
        print(f"         {issue['context']}")
        print()

    print("-" * 70)
    print("HOW TO FIX:")
    print("-" * 70)
    print("""
  BLOCKER (domain fields): The field in filter_domain/filter_pre_domain
  does not exist on the model. This will crash on module install.
  → Check the Python model for the correct field name.

  HIGH (code fields): The server action code references a field that
  may not exist on the model. This will crash at runtime.
  → Verify the field name matches the Python model definition.
""")

    sys.exit(1)


if __name__ == "__main__":
    main()
