{
    "name": "Plasticos Documents — Native Bridge",
    "version": "19.0.1.0.0",
    "summary": "Bridge to Odoo Enterprise Documents with AI auto-sort, "
               "email alias, and plastics-specific field extensions",
    "author": "PlasticOS",
    "license": "LGPL-3",
    "depends": [
        "documents",
        "documents_account",
        "plasticos_documents",
        "plasticos_logistics",
        "plasticos_transaction",
        "plasticos_intake",
        "plasticos_material_profile",
        "plasticos_security_base",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/document_folders.xml",
        "data/document_tags.xml",
        "views/document_native_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
