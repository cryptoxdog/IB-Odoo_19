{
    "name": "PlasticOS Broker Intelligence: Rejection Advice",
    "version": "19.0.2.0.2",
    "summary": "Non-authoritative buyer rejection explanations for offers and match results",
    "category": "Operations",
    "author": "Scrap Management Inc.",
    "license": "LGPL-3",
    "depends": ["plasticos_broker_intelligence", "plasticos_offer", "plasticos_matching"],
    "data": [
        "security/ir.model.access.csv",
        "views/rejection_wizard_views.xml",
        "views/offer_rejection_views.xml",
        "views/match_rejection_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
