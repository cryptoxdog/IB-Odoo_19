# ═══════════════════════════════════════════════════════════
# Module : plasticos_web_leads
# Purpose: Web lead ingestion with AI-powered triage pipeline.
#          Supports both pre-processed agent payloads and raw
#          Cognito form submissions with LLM normalization,
#          vision analysis, and deterministic classification.
# ═══════════════════════════════════════════════════════════
{
    "name": "PlasticOS Web Leads",
    "version": "19.0.2.5.0",
    "summary": "AI-powered web lead triage: Cognito → LLM/Vision → HOT/COLD → Intake",
    "license": "LGPL-3",
    "author": "Igor Beylin",
    "category": "Operations",
    "depends": [
        "base",
        "mail",
        "utm",
        "plasticos_facility_profile",
        "plasticos_intake",
        "plasticos_material_profile",
        "purchase",
    ],
    "external_dependencies": {
        "python": ["openai", "requests"],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/web_lead_config_data.xml",
        "data/logistics_ir_rules.xml",
        "views/web_lead_views.xml",
        "views/web_lead_config_views.xml",
        "views/web_lead_api_key_wizard_views.xml",
        "views/lead_bulk_action_wizard_views.xml",
        "views/web_lead_ux.xml",
        "views/web_lead_bridge_views.xml",
    ],
    "installable": True,
    "auto_install": True,
    "application": False,
}
