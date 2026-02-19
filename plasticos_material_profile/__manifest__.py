{
    "name": "PlasticOS Material Profile",
    "version": "19.0.3.0.0",
    "summary": "Material identity profiles with canonical polymer master",
    "license": "LGPL-3",
    "author": "PlasticOS",
    "category": "Hidden",
    "depends": [
        "base",
        "contacts",
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/polymer_data.xml",
        "views/polymer_views.xml",
        "views/material_profile_views.xml",
    ],
    "installable": True,
    "application": False,
}
