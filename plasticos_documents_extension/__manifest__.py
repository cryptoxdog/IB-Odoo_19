{
    "name": "PlasticOS Documents Extension",
    "version": "19.0.1.0.0",
    "summary": "Extended document tracking: expiry, versioning, missing-doc automation, validation matrix",
    "author": "PlasticOS",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "plasticos_documents",
        "plasticos_transaction",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/document_tags_data.xml",
        "data/cron_missing_docs.xml",
        "views/document_extension_views.xml",
        "views/transaction_docs_views.xml",
        "views/validation_matrix_views.xml",
    ],
    "installable": True,
    "application": False,
}
