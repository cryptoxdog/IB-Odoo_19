#!/usr/bin/env python3
"""
Auto-fixer for safe Odoo antipatterns.

Fixes (mechanical, safe substitutions only):
1. self.env.get("model.name")  →  self.env["model.name"]
2. self.pool.get("model.name") →  self.env["model.name"]
3. @api.multi                  →  (line deleted)

Skips:
- Anything requiring semantic understanding (fields.function, unbounded search)

Usage:
    python3 scripts/fix_odoo_antipatterns.py [--check] [file ...]
    pre-commit run fix-odoo-antipatterns --all-files

Exit codes:
    0 = No issues (or --check: no issues found)
    1 = Files were modified (or --check: issues found)
"""

import re
import sys
from pathlib import Path

ENV_GET_RE = re.compile(r'\bself\.env\.get\s*\(\s*(["\'])([^"\']+)\1\s*\)')
POOL_GET_RE = re.compile(r'\bself\.pool\.get\s*\(\s*(["\'])([^"\']+)\1\s*\)')
API_MULTI_RE = re.compile(r'^(\s*)@api\.multi\s*$')

PLASTICOS_MODULES = [
    "plasticos_automation", "plasticos_base", "plasticos_buyer_match_engine",
    "plasticos_claims", "plasticos_commission", "plasticos_crm_bridge",
    "plasticos_dev_tools", "plasticos_documents", "plasticos_documents_native",
    "plasticos_enrichment", "plasticos_enrichment_bridge",
    "plasticos_facility_profile", "plasticos_geolocalize",
    "plasticos_graph_intelligence", "plasticos_inference_engine",
    "plasticos_intake", "plasticos_intake_normalizer", "plasticos_logistics",
    "plasticos_matching", "plasticos_material_profile", "plasticos_offer",
    "plasticos_order_lines", "plasticos_partner_import", "plasticos_product",
    "plasticos_security_base", "plasticos_transaction", "plasticos_web_leads",
]


def fix_content(content: str) -> tuple[str, list[str]]:
    """Apply all safe auto-fixes. Returns (new_content, list_of_changes)."""
    changes = []
    lines = content.splitlines(keepends=True)
    new_lines = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Skip comment lines
        if stripped.startswith("#"):
            new_lines.append(line)
            continue

        original = line

        # Fix 1: self.env.get("model") → self.env["model"]
        def replace_env_get(m: re.Match) -> str:
            quote, model = m.group(1), m.group(2)
            changes.append(f"  line {i}: env.get({quote}{model}{quote}) → env[\"{model}\"]")
            return f'self.env["{model}"]'

        line = ENV_GET_RE.sub(replace_env_get, line)

        # Fix 2: self.pool.get("model") → self.env["model"]
        def replace_pool_get(m: re.Match) -> str:
            quote, model = m.group(1), m.group(2)
            changes.append(f"  line {i}: pool.get({quote}{model}{quote}) → env[\"{model}\"]")
            return f'self.env["{model}"]'

        line = POOL_GET_RE.sub(replace_pool_get, line)

        # Fix 3: @api.multi → delete line
        if API_MULTI_RE.match(line):
            changes.append(f"  line {i}: removed @api.multi")
            continue  # Drop the line

        new_lines.append(line)

    return "".join(new_lines), changes


def find_python_files(paths: list[str]) -> list[Path]:
    if paths:
        return [Path(p) for p in paths if p.endswith(".py")]
    files = []
    for module in PLASTICOS_MODULES:
        if Path(module).is_dir():
            files.extend(Path(module).rglob("*.py"))
    if Path("tests").is_dir():
        files.extend(Path("tests").rglob("*.py"))
    return files


def main() -> int:
    check_only = "--check" in sys.argv
    file_args = [a for a in sys.argv[1:] if not a.startswith("--")]

    files = find_python_files(file_args)
    modified = 0

    for path in files:
        try:
            original = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        fixed, changes = fix_content(original)
        if changes:
            modified += 1
            print(f"{'Would fix' if check_only else 'Fixed'}: {path}")
            for c in changes:
                print(c)
            if not check_only:
                path.write_text(fixed, encoding="utf-8")

    if modified:
        status = "issues found" if check_only else "files fixed"
        print(f"\n{'❌' if check_only else '✅'} {modified} {status}")
        return 1
    else:
        print("✅ No Odoo antipatterns found")
        return 0


if __name__ == "__main__":
    sys.exit(main())
