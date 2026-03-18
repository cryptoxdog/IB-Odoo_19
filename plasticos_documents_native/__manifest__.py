{
    "name": "Plasticos Documents — Native Bridge",
    "version": "19.0.1.1.0",
    "summary": "Bridge to Odoo Enterprise Documents with AI auto-sort, "
    "email alias, and plastics-specific field extensions",
    "category": "Document Management",
    "author": "Igor Beylin",
    "license": "LGPL-3",
    # ══════════════════════════════════════════════════════════════════════════
    # ENTERPRISE DEPENDENCY: This module requires Odoo Enterprise 'documents'
    # and 'documents_account' modules.
    #
    # INSTALL ORDER ON ODOO.SH:
    # 1. First install 'documents' from Apps (Enterprise module)
    # 2. Then set installable: True here and push
    # 3. Install this module from Apps
    #
    # Currently set to installable: False to prevent rebuild failures.
    # ══════════════════════════════════════════════════════════════════════════
    "depends": [
        "documents",  # Enterprise: Document Management
        "documents_account",  # Enterprise: Documents ↔ Accounting bridge
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
    # Set to False until 'documents' Enterprise module is installed on Odoo.sh
    # Change to True after installing 'documents' from Apps
    "installable": False,
    "application": False,
    "auto_install": False,
}
