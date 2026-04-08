{
    "name": "Plasticos — Security Base",
    "version": "19.0.1.2.7",
    "category": "Plasticos/Security",
    "summary": "Core RBAC roles, record rules, and private-partner flag for the Plasticos platform.",
    "description": """
        Defines the foundational security layer:
        - Three business roles: Sales Rep, Logistics, Accounting
        - Private-partner flag (is_private) on res.partner with ir.rule enforcement
        - Record rules for row-level isolation on transactions, orders, invoices, and loads
        - Category group for the Plasticos application
    """,
    "author": "Igor Beylin",
    "depends": [
        "base",
        "plasticos_base",
        "base_geolocalize",
        "sale",
        "purchase",
        "account",
        "stock",
        "plasticos_transaction",
        "plasticos_intake",
        "plasticos_material_profile",
        "plasticos_facility_profile",
        # "plasticos_matching",  # Disabled - external microservice
        "plasticos_offer",
        "plasticos_logistics",
        "plasticos_documents",
        "plasticos_automation",
        "plasticos_web_leads",
    ],
    "data": [
        "security/security_groups.xml",
        "security/record_rules.xml",
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": True,
    "license": "LGPL-3",
}
