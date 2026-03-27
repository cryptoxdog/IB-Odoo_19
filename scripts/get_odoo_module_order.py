#!/usr/bin/env python3
"""
Print Odoo module install order as comma-separated list.
Reads config/odoo_module_order.yaml. Used by rebuild-odoo-no-demo.sh and run-odoo-tests.sh.

Usage:
  scripts/get_odoo_module_order.py                              # default_install_order
  scripts/get_odoo_module_order.py --optional                   # + optional modules
  scripts/get_odoo_module_order.py --section docker_enterprise_modules
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "odoo_module_order.yaml"

CUSTOM_DEFAULT = [
    "plasticos_accounting",
    "plasticos_base",
    "plasticos_material_profile",
    "plasticos_inference_engine",
    "plasticos_logistics",
    "plasticos_facility_profile",
    "plasticos_intake",
    "plasticos_product",
    "plasticos_order_lines",
    "plasticos_transaction",
    "plasticos_documents",
    "plasticos_matching",
    "plasticos_offer",
    "plasticos_claims",
    "plasticos_automation",
    "plasticos_intake_normalizer",
    "plasticos_buyer_match_engine",
    "plasticos_partner_import",
    "plasticos_geolocalize",
    "plasticos_enrichment",
    "plasticos_security_base",
]


def _get_section(data: dict, section: str) -> list[str]:
    items = data.get(section) or []
    # Strip inline YAML comments (e.g. "currency_rate_live  # CRITICAL: ...")
    return [str(item).split("#")[0].strip() for item in items if item]


def main() -> None:
    # Parse args
    section = "default_install_order"
    include_optional = False
    for arg in sys.argv[1:]:
        if arg == "--optional":
            include_optional = True
        elif arg.startswith("--section="):
            section = arg.split("=", 1)[1]
        elif arg == "--section" and sys.argv.index(arg) + 1 < len(sys.argv):
            section = sys.argv[sys.argv.index(arg) + 1]

    try:
        import yaml
    except ImportError:
        if section != "default_install_order":
            print("")
            return
        order = CUSTOM_DEFAULT[:]
        if include_optional:
            order.append("plasticos_web_leads")
        print(",".join(order))
        return

    if not CONFIG.exists():
        if section != "default_install_order":
            print("")
            return
        order = CUSTOM_DEFAULT[:]
        if include_optional:
            order.append("plasticos_web_leads")
        print(",".join(order))
        return

    with open(CONFIG, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    order = _get_section(data, section)

    if section == "default_install_order" and include_optional:
        order += _get_section(data, "optional_modules")

    print(",".join(m for m in order if m))


if __name__ == "__main__":
    main()
