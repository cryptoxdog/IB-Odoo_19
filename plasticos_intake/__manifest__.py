{
    "name": "PlasticOS Intake",
    "version": "19.0.2.0.0",
    "summary": "Transactional Material Intake — unified with material profile",
    "author": "PlasticOS",
    "depends": [
        "base",
        "plasticos_security_base",
        "mail",
        "plasticos_material_profile",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/intake_views.xml"
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3"
}
