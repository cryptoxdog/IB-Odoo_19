{
    "name": "Plasticos Documents Engine",
    "version": "19.0.1.0.0",
    "summary": "Document management and compliance",
    "author": "PlasticOS",
    "license": "LGPL-3",
    "depends": ["base", "plasticos_security_base", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/document_tag_views.xml",
        "views/document_rule_views.xml",
        "views/document_views.xml",
        "data/cron.xml"
    ],
    "installable": True,
    "application": False,
}
