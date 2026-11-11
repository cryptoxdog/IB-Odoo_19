{
    "name": "PlasticOS Broker Intelligence: Mack Advice",
    "version": "19.0.2.0.0",
    "summary": "Source-bound, deterministic and immutable broker consultation receipts",
    "category": "Operations",
    "author": "Scrap Management Inc.",
    "license": "LGPL-3",
    "depends": ["plasticos_broker_intelligence", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "views/consultation_views.xml",
        "views/consultation_wizard_views.xml",
        "views/intake_mack_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
