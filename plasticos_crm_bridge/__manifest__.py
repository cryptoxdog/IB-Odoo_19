{
    "name": "PlastOS CRM Bridge",
    "version": "19.0.1.0.0",
    "depends": [
        "crm",
        "plasticos_web_leads",
        "plasticos_matching",
        "plasticos_material_profile",
        "plasticos_transaction",
        "plasticos_logistics",
        "plasticos_enrichment_bridge",
    ],
    "data": [
        "data/lead_source_data.xml",
        "views/crm_lead_views.xml",
        "views/material_profile_views.xml",
        "security/ir.model.access.csv",
    ],
    "category": "PlastOS",
    "license": "LGPL-3",
}
