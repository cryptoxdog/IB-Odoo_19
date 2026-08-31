{
    "name": "PlastOS Test Pack",
    "version": "19.0.1.0.0",
    "category": "Hidden",
    "summary": "Comprehensive test suite for PlastOS modules",
    "description": "Controller/API, Security/ACL, Constraint/Onchange, Integration tests.",
    "author": "Igor Beylin",
    "depends": [
        "plasticos_base",
        "plasticos_transaction",
        "plasticos_claims",
        "plasticos_logistics",
        "plasticos_offer",
        "plasticos_intake",
        "plasticos_documents",
        "plasticos_web_leads",
        "plasticos_crm_bridge",
        # plasticos_buyer_match_engine was physically retired in M7 / TASK-051
        # (docs/adr/ADR-003-single-external-intelligence-authority.md). Do not re-add.
        "plasticos_material_profile",
        "plasticos_facility_profile",
        "plasticos_intake_normalizer",
        "plasticos_enrichment",
        "plasticos_matching",
        "plasticos_commission",
        "plasticos_automation",
    ],
    "data": [],
    # Not installable: the Odoo-backed suites in this tree run under
    # `odoo --test-enable` against the addons they exercise, and the pure-Python
    # suites run under pytest (tests/conftest.py collect-ignores the Odoo ones).
    "installable": False,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
