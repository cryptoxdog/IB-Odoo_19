{
    "name": "Plasticos Documents — Native Bridge",
    "version": "19.0.1.4.0",
    "summary": "Plastics fields on Odoo Enterprise Documents, pending evidence rows for classified "
    "originals with manager review, and a posting guard on digitized vendor bills",
    "category": "Document Management",
    "author": "Igor Beylin",
    "license": "Other proprietary",
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
        "account",  # vendor bill posting guard (models/account_move.py)
        "account_invoice_extract",  # Enterprise: native bill digitization (IAP); the guard reads its state
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
        "views/account_move_views.xml",
    ],
    # Requires Enterprise modules `documents`, `documents_account` and `account_invoice_extract` on the host.
    "installable": True,
    "application": True,
    "auto_install": True,
}
