#!/usr/bin/env python3
"""
Print default Odoo module install order as comma-separated list.
Reads config/odoo_module_order.yaml. Used by rebuild-odoo-no-demo.sh and run-odoo-tests.sh.
Usage: scripts/get_odoo_module_order.py [--optional]   (default: no optional)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "odoo_module_order.yaml"


def main() -> None:
    try:
        import yaml
    except ImportError:
        # Fallback if PyYAML not installed: hardcoded order
        default = [
            "plasticos_accounting",
            "plasticos_base",
            "plasticos_material_profile",
            "plasticos_inference_engine",
            "plasticos_logistics",
            "plasticos_facility_profile",
            "plasticos_intake",
            "plasticos_product",
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
        optional = ["plasticos_web_leads"]
        if "--optional" in sys.argv:
            print(",".join(default + optional))
        else:
            print(",".join(default))
        return

    if not CONFIG.exists():
        default = [
            "plasticos_accounting",
            "plasticos_base",
            "plasticos_material_profile",
            "plasticos_inference_engine",
            "plasticos_logistics",
            "plasticos_facility_profile",
            "plasticos_intake",
            "plasticos_product",
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
        if "--optional" in sys.argv:
            default.append("plasticos_web_leads")
        print(",".join(default))
        return

    with open(CONFIG, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    order = data.get("default_install_order") or []
    if "--optional" in sys.argv:
        order = order + (data.get("optional_modules") or [])

    print(",".join(order))


if __name__ == "__main__":
    main()
