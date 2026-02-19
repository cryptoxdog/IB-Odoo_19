{
    "name": "PlasticOS Matching",
    "version": "19.0.1.0.0",
    "summary": "Match result storage — L9 adapter populates, Odoo displays",
    "license": "LGPL-3",
    "author": "PlasticOS",
    "category": "Hidden",
    "depends": [
        "base",
        "plasticos_security_base",
        "mail",
        "plasticos_intake",
        "plasticos_facility_profile",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/match_result_views.xml",
    ],
    "installable": True,
    "application": False,
}
