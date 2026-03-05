#!/usr/bin/env python3
"""
Convert _sql_constraints to models.Constraint (Odoo 17+).
Run: python3 scripts/convert_sql_constraints.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# All modules with _sql_constraints (Odoo 19: use models.Constraint)
FILES = [
    "plasticos_automation/models/automation_config.py",
    "plasticos_buyer_match_engine/models/match_exclusion.py",
    "plasticos_claims/models/claim.py",
    "plasticos_documents/models/document_rule.py",
    "plasticos_facility_profile/models/equipment_type.py",
    "plasticos_facility_profile/models/facility_profile.py",
    "plasticos_facility_profile/models/partner_type.py",
    "plasticos_logistics/models/rate_memory.py",
    "plasticos_matching/models/match_result.py",
    "plasticos_material_profile/models/material_attribute.py",
    "plasticos_material_profile/models/material_color.py",
    "plasticos_material_profile/models/material_form.py",
    "plasticos_material_profile/models/material_profile.py",
    "plasticos_material_profile/models/packaging_type.py",
    "plasticos_material_profile/models/polymer.py",
    "plasticos_material_profile/models/process_type.py",
    "plasticos_material_profile/models/source_type.py",
    "plasticos_offer/models/offer.py",
    "plasticos_transaction/models/commission_rule.py",
    "plasticos_transaction/models/transaction.py",
    "plasticos_web_leads/models/web_lead.py",
]

# Match one constraint tuple: ( "name", "sql", "msg" ), — comma may be before or after )
_CONSTRAINT_TUPLE = re.compile(
    r"\s*\(\s*" r'"([^"]+)"\s*,\s*' r'"([^"]+)"\s*,\s*' r'"([^"]*)"\s*' r",?\s*\)\s*",
    re.DOTALL,
)


def extract_constraints(content: str) -> list[tuple[str, str, str]]:
    """Extract (name, sql, message) tuples from _sql_constraints block content."""
    constraints = []
    for m in _CONSTRAINT_TUPLE.finditer(content):
        constraints.append((m.group(1), m.group(2), m.group(3)))
    return constraints


def _find_sql_constraints_block(content: str) -> tuple[int, int, str] | None:
    """Find _sql_constraints = [ ... ] and return (start, end, indent)."""
    match = re.search(r"(\s+)_sql_constraints\s*=\s*\[", content)
    if not match:
        return None
    indent = match.group(1)
    start = match.start()
    bracket_start = match.end() - 1  # position of [
    depth = 1
    i = bracket_start + 1
    while i < len(content) and depth > 0:
        if content[i] == "[":
            depth += 1
        elif content[i] == "]":
            depth -= 1
        i += 1
    if depth != 0:
        return None
    return (start, i, indent)


def find_and_replace(content: str, filepath: Path) -> str:
    """Replace _sql_constraints block with models.Constraint attributes."""
    block_info = _find_sql_constraints_block(content)
    if not block_info:
        return content
    start, end, indent = block_info
    block = content[start:end]
    constraints = extract_constraints(block)
    if not constraints:
        return content

    # Use line-level indent (spaces only) for continuation lines
    base_indent = indent.split("\n")[-1] if "\n" in indent else indent
    if not base_indent.strip():
        base_indent = indent.strip() or "    "

    # Build replacement: one models.Constraint per constraint
    replacement_lines = []
    for name, sql, msg in constraints:
        attr_name = f"_check_{name}"
        replacement_lines.append(
            f"{indent}{attr_name} = models.Constraint(\n"
            f'{base_indent}    "{sql}",\n'
            f'{base_indent}    "{msg}",\n'
            f"{base_indent})"
        )

    replacement = "\n\n".join(replacement_lines)
    return content[:start] + replacement + content[end:]


def main() -> int:
    errors = 0
    for rel in FILES:
        path = ROOT / rel
        if not path.exists():
            print(f"Skip (not found): {rel}", file=sys.stderr)
            continue
        content = path.read_text(encoding="utf-8")
        if "_sql_constraints" not in content:
            continue
        new_content = find_and_replace(content, path)
        if new_content != content:
            path.write_text(new_content, encoding="utf-8")
            print(f"Converted: {rel}")
        else:
            print(f"No change: {rel}", file=sys.stderr)
            errors += 1
    return errors


if __name__ == "__main__":
    sys.exit(main())
