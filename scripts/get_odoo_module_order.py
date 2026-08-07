#!/usr/bin/env python3
"""
Print Odoo module install order as comma-separated list.
Reads config/odoo_module_order.yaml. Used by rebuild-odoo-no-demo.sh,
install_smoke.sh, and run-odoo-tests.sh.

Works without PyYAML (stdlib section parser) so host/CI python always works.

Usage:
  scripts/get_odoo_module_order.py                              # default_install_order
  scripts/get_odoo_module_order.py --optional                   # + optional modules
  scripts/get_odoo_module_order.py --all-installable            # ordered + remaining installable
  scripts/get_odoo_module_order.py --section docker_enterprise_modules
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "odoo_module_order.yaml"

# Keep in sync with config/odoo_module_order.yaml → default_install_order
# (mothballed intelligence modules must NEVER appear here).
CUSTOM_DEFAULT = [
    "plasticos_accounting",
    "plasticos_base",
    "plasticos_gate",
    "plasticos_material_profile",
    "plasticos_logistics",
    "plasticos_facility_profile",
    "plasticos_intake",
    "plasticos_product",
    "plasticos_order_lines",
    "plasticos_transaction",
    "plasticos_documents",
    "plasticos_offer",
    "plasticos_claims",
    "plasticos_automation",
    "plasticos_intake_normalizer",
    "plasticos_matching",
    "plasticos_enrichment",
    "plasticos_geolocalize",
    "plasticos_web_leads",
    "plasticos_security_base",
    "plasticos_commission",
    "plasticos_crm_bridge",
    "plasticos_partner_import",
    "plasticos_crm_sync",
    "plasticos_admin_dashboard",
]

_ITEM_RE = re.compile(r"^\s*-\s+([^\s#]+)")


def _parse_section(text: str, section: str) -> list[str]:
    """Minimal YAML list-section reader (no PyYAML required)."""
    lines = text.splitlines()
    header = re.compile(rf"^{re.escape(section)}\s*:")
    items: list[str] = []
    in_section = False
    for line in lines:
        if header.match(line):
            in_section = True
            continue
        if not in_section:
            continue
        if line and not line[0].isspace() and not line.startswith("#"):
            # next top-level key
            break
        m = _ITEM_RE.match(line)
        if m:
            items.append(m.group(1).strip())
    return items


def _get_section(data: dict, section: str) -> list[str]:
    items = data.get(section) or []
    return [str(item).split("#")[0].strip() for item in items if item]


def _manifest_installable(manifest_path: Path) -> bool:
    raw = manifest_path.read_text(encoding="utf-8")
    try:
        data = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            return False
        data = ast.literal_eval(raw[start : end + 1])
    if not isinstance(data, dict):
        return False
    return bool(data.get("installable", True))


def _all_installable(excluded: set[str], ordered: list[str]) -> list[str]:
    """Ordered core list first, then any other installable plasticos_* not excluded."""
    seen = set(ordered)
    extra: list[str] = []
    for manifest in sorted(ROOT.glob("plasticos_*/__manifest__.py")):
        name = manifest.parent.name
        if name in seen or name in excluded:
            continue
        if _manifest_installable(manifest):
            extra.append(name)
            seen.add(name)
    return ordered + extra


def main() -> None:
    section = "default_install_order"
    include_optional = False
    all_installable = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--optional":
            include_optional = True
        elif arg == "--all-installable":
            all_installable = True
        elif arg.startswith("--section="):
            section = arg.split("=", 1)[1]
        elif arg == "--section" and i + 1 < len(args):
            i += 1
            section = args[i]
        i += 1

    order: list[str] = []
    excluded: list[str] = []
    text = CONFIG.read_text(encoding="utf-8") if CONFIG.exists() else ""

    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) if text else {}
        order = _get_section(data or {}, section)
        excluded = _get_section(data or {}, "excluded_modules")
        if section == "default_install_order" and include_optional:
            order += _get_section(data or {}, "optional_modules")
            order += _get_section(data or {}, "web_leads_module")
    except ImportError:
        if text:
            order = _parse_section(text, section)
            excluded = _parse_section(text, "excluded_modules")
            if section == "default_install_order" and include_optional:
                order += _parse_section(text, "optional_modules")
                order += _parse_section(text, "web_leads_module")

    if not order and section == "default_install_order":
        order = CUSTOM_DEFAULT[:]
        if include_optional:
            order.append("plasticos_web_leads")

    if all_installable and section == "default_install_order":
        # Always include web_leads when sweeping all installable addons.
        if "plasticos_web_leads" not in order:
            order.append("plasticos_web_leads")
        order = _all_installable(set(excluded), order)

    print(",".join(m for m in order if m))


if __name__ == "__main__":
    main()
