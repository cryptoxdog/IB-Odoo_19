#!/usr/bin/env python3
"""
Fail closed when plasticos XML refs an external module id that is not a
declared dependency (or base/web/mail/...). Catches the class of bug where
plasticos_logistics referenced plasticos_security_base.group_* before that
module could install (circular / missing depends).

Usage:
  python3 ci/check_xml_module_ref_deps.py
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# eval="...ref('module.id')..." and attribute form ref="module.id"
REF_RE = re.compile(r"""(?:ref\(\s*['"]|ref\s*=\s*['"])([a-zA-Z0-9_]+)\.([a-zA-Z0-9_.]+)['"]""")

# Always available in Odoo core / common stack without plasticos depends.
CORE_OK = frozenset(
    {
        "base",
        "web",
        "mail",
        "sale",
        "sale_management",
        "purchase",
        "purchase_stock",
        "account",
        "stock",
        "crm",
        "sales_team",
        "contacts",
        "product",
        "uom",
        "portal",
        "http_routing",
        "auth_signup",
        "bus",
        "base_geolocalize",
        "base_setup",
        "base_import",
        "resource",
        "utm",
        "phone_validation",
        "sms",
        "iap",
        "digest",
        "spreadsheet",
        "documents",
        "documents_account",
    }
)


def _manifest_dict(manifest_path: Path) -> dict:
    """Parse Odoo __manifest__.py even when header comments precede the dict."""
    raw = manifest_path.read_text(encoding="utf-8")
    try:
        data = ast.literal_eval(raw)
        if isinstance(data, dict):
            return data
    except (SyntaxError, ValueError):
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"No dict literal in {manifest_path}")
    data = ast.literal_eval(raw[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError(f"Manifest root is not a dict: {manifest_path}")
    return data


def _strip_xml_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def _excluded_modules() -> set[str]:
    """Honor config/odoo_module_order.yaml excluded_modules (stdlib parse)."""
    cfg = ROOT / "config" / "odoo_module_order.yaml"
    if not cfg.exists():
        return set()
    items: set[str] = set()
    in_section = False
    item_re = re.compile(r"^\s*-\s+([^\s#]+)")
    for line in cfg.read_text(encoding="utf-8").splitlines():
        if re.match(r"^excluded_modules\s*:", line):
            in_section = True
            continue
        if not in_section:
            continue
        if line and not line[0].isspace() and not line.startswith("#"):
            break
        m = item_re.match(line)
        if m:
            items.add(m.group(1).strip())
    return items


def main() -> int:
    violations: list[str] = []
    excluded = _excluded_modules()
    for manifest in sorted(ROOT.glob("plasticos_*/__manifest__.py")):
        module = manifest.parent.name
        if module in excluded:
            continue
        try:
            data = _manifest_dict(manifest)
        except ValueError as exc:
            violations.append(str(exc))
            continue
        if not data.get("installable", True):
            continue
        depends = set(data.get("depends") or [])
        depends.add(module)
        allowed = depends | CORE_OK
        for xml in sorted(manifest.parent.rglob("*.xml")):
            text = _strip_xml_comments(xml.read_text(encoding="utf-8"))
            for match in REF_RE.finditer(text):
                target_mod = match.group(1)
                if target_mod not in allowed:
                    rel = xml.relative_to(ROOT)
                    violations.append(
                        f"{rel}: ref('{target_mod}.{match.group(2)}') but {module} does not depend on {target_mod}"
                    )
    if violations:
        print("❌ XML external-id dependency violations:")
        for v in violations:
            print(f"  - {v}")
        print("\nFix: move the XML into the module that owns the groups/models, or add a non-circular depends entry.")
        return 1
    print("✅ XML module refs match declared depends")
    return 0


if __name__ == "__main__":
    sys.exit(main())
