{
    "name": "PlasticOS Mack Workbench",
    "version": "19.0.1.0.1",
    "summary": "Governed Odoo-native Mack internal review requests",
    "author": "Igor Beylin",
    "license": "LGPL-3",
    "depends": [
        "mail",
        "plasticos_intake",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "security/mack_workbench_rules.xml",
        "data/internal_review_sequence.xml",
        "views/internal_review_views.xml",
        "views/workbench_config_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
