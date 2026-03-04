{
    "name": "PlasticOS Intake",
    "version": "19.0.5.1.0",
    "summary": "Transactional Material Intake — contact intelligence, smart memory, UX normalization",
    "author": "PlasticOS",
    "depends": [
        "base",
        "contacts",
        "mail",
        "plasticos_material_profile",
        "plasticos_facility_profile",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/intake_views.xml",
        "views/material_profile_intake_views.xml",
        "views/intake_ux.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
