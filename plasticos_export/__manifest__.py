{
    "name": "PlasticOS Export",
    "version": "19.0.1.0.0",
    "summary": "Export booking and shipment context over native and PlasticOS owners",
    "category": "PlasticOS",
    "author": "Igor Beylin",
    "license": "LGPL-3",
    # Export depends on its owners, never the reverse. plasticos_documents_native
    # reaches Enterprise documents/documents_account and the Documents, Logistics,
    # Transaction and Security Base modules. Add an owner here when Export first
    # imports from it directly.
    "depends": [
        "plasticos_documents_native",
    ],
    # Scaffold: no data, views, ACL or reports yet; installing it writes nothing.
    "data": [],
    "installable": True,
    "application": True,
    "auto_install": False,
}
