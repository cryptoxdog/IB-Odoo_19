{
    "name": "PlasticOS Offer",
    "version": "19.0.1.0.0",
    "summary": "Offer lifecycle management — from match to deal",
    "license": "LGPL-3",
    "author": "PlasticOS",
    "category": "Hidden",
    "depends": [
        "base",
        "mail",
        "plasticos_intake",
        "plasticos_matching",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/offer_cron.xml",
        "views/offer_views.xml",
        "views/offer_bulk_action_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
