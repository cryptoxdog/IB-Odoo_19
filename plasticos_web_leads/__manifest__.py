{
    "name": "PlasticOS Web Leads",
    "version": "19.0.1.0.0",
    "summary": "REST endpoint for HOT web leads — Cognito → Agent → Odoo Intake",
    "license": "LGPL-3",
    "author": "PlasticOS",
    "category": "Hidden",
    "depends": [
        "base",
        "plasticos_security_base",
        "mail",
        "plasticos_intake",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/web_lead_config_data.xml",
        "views/web_lead_views.xml",
        "views/web_lead_config_views.xml",
    ],
    "installable": True,
    "application": False,
}
