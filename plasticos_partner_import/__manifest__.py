{
    "name": "Plasticos Partner Import",
    "version": "19.0.1.2.0",
    "summary": "Deterministic partner import with wizard UI (Odoo 19)",
    "author": "Scrap Management Inc",
    "license": "LGPL-3",
    "depends": [
        "base",
        "contacts",
        "account",
        "plasticos_facility_profile",
        "plasticos_intake",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/partner_import_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
