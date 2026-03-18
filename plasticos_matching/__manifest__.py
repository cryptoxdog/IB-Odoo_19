{
    "name": "PlasticOS Matching",
    "version": "19.0.1.0.1",
    "summary": "Match result storage for intake-to-buyer matching",
    "license": "LGPL-3",
    "author": "Igor Beylin",
    "category": "Hidden",
    "depends": [
        "base",
        "mail",
        "plasticos_intake",
        "plasticos_facility_profile",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/match_result_views.xml",
    ],
    "installable": True,
    "auto_install": True,
    "application": False,
}
