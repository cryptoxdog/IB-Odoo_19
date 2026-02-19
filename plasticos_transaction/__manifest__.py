{
    "name": "Plasticos Transaction Spine",
    "version": "19.0.1.1.0",
    "summary": "Core transaction lifecycle management",
    "author": "PlasticOS",
    "license": "LGPL-3",
    "depends": [
        "base",
        "plasticos_security_base",
        "mail",
        "account",
        "sale_management",
        "purchase",
        "plasticos_logistics",
        "plasticos_documents",
        "plasticos_commission",
        "plasticos_material_profile",
        "plasticos_facility_profile",
        "plasticos_intake"
    ],
    "data": [
        "security/security_hardening.xml",
        "security/ir.model.access.csv",
        "security/commission_acl.xml",
        "data/sequence.xml",
        "data/audit_cron.xml",
        "views/transaction_views.xml"
    ],
    "installable": True,
    "application": False,
}
