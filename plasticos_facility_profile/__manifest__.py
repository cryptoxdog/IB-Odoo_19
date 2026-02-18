{
    "name": "PlasticOS Facility Profile",
    "version": "19.0.2.0.0",
    "summary": "Facility capability profiles — equipment, tolerances, and BCP fields",
    "license": "LGPL-3",
    "author": "PlasticOS",
    "category": "Hidden",
    "depends": [
        "base",
        "contacts",
        "mail",
        "sale_management",
        "plasticos_polymer",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/facility_profile_views.xml",
    ],
    "installable": True,
    "application": False,
}
