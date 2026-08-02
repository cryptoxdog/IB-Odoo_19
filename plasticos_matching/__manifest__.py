{
    "name": "PlasticOS Matching",
    "version": "19.0.2.0.0",
    "summary": "Gate-mediated match runs, exclusions, and result storage (mothball M2)",
    "license": "LGPL-3",
    "author": "Igor Beylin",
    "category": "Hidden",
    "depends": [
        "base",
        "mail",
        "plasticos_intake",
        "plasticos_facility_profile",
        "plasticos_gate",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/match_result_views.xml",
        "views/match_run_views.xml",
        "views/match_exclusion_views.xml",
    ],
    "installable": True,
    "auto_install": True,
    "application": False,
}
