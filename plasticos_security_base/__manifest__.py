{
    "name": "Plasticos — Security Base",
    "version": "19.0.1.2.0",
    "category": "Plasticos/Security",
    "summary": "Core RBAC roles, record rules, and private-partner flag for the Plasticos platform.",
    "description": """
        Defines the foundational security layer:
        - Three business roles: Sales Rep, Logistics, Accounting
        - Private-partner flag (x_private) on res.partner with ir.rule enforcement
        - Record rules for row-level isolation on transactions, orders, invoices, and loads
        - Category group for the Plasticos application
    """,
    "author": "Plasticos Dev",
    "depends": [
        "base",
        "sale",
        "purchase",
        "account",
        "stock",
        "plasticos_transaction",
        "plasticos_intake",
        "plasticos_material_profile",
        "plasticos_facility_profile",
        "plasticos_matching",
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
    "installable": True,
    "auto_install": False,
    "application": False,
    "license": "LGPL-3",
}
