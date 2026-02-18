{
    "name": "PlasticOS Facility Profile",
    "version": "19.0.2.0.0",
    "summary": "Facility mechanical capability profiles — relational equipment model",
    "license": "LGPL-3",
    "author": "PlasticOS",
    "category": "Hidden",
    "depends": [
        "base",
        "contacts",
        "mail",
        "sale_management"
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/equipment_type_data.xml",
        "views/facility_profile_views.xml",
    ],
    "installable": True,
    "application": False,
}
