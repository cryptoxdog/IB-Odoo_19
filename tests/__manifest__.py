{
    "name": "PlastOS Test Pack",
    "version": "19.0.1.0.0",
    "category": "Hidden",
    "summary": "Comprehensive test suite for PlastOS modules",
    "description": "Controller/API, Security/ACL, Constraint/Onchange, Integration tests.",
    "author": "PlastOS Dev Team",
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
        # "plasticos_buyer_match_engine",  # Disabled - external microservice
        "plasticos_material_profile",
        "plasticos_facility_profile",
        # "plasticos_enrichment",  # Disabled - external microservice
        "plasticos_automation",
    ],
    "data": [],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
