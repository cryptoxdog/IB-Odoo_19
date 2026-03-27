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
    # Odoo.sh must include Enterprise `documents` + `documents_account`.
    # auto_install pulls this in once all depends (including Enterprise) are installed.
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
    # Requires Enterprise modules `documents` and `documents_account` on the host.
    "installable": False,
    "application": False,
    # auto_install disabled: documents.folder model removed in Odoo 19 Enterprise.
    # Module needs refactoring before it can be installed.
    "auto_install": False,
}
