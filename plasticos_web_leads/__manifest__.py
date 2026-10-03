# ═══════════════════════════════════════════════════════════
# Module : plasticos_web_leads
# Purpose: Web lead ingestion with AI-powered triage pipeline.
#          Admits provider-neutral inbound web leads (Cognito Forms is
#          the current adapter) with LLM normalization, vision analysis,
#          and deterministic classification.
# ═══════════════════════════════════════════════════════════
{
    "name": "PlasticOS Web Leads",
    "version": "19.0.2.8.1",
    "summary": "AI-powered triage for provider-neutral inbound web leads",
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
        "python": ["anthropic", "openai", "requests"],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/web_lead_config_data.xml",
        "data/logistics_ir_rules.xml",
        "views/web_lead_views.xml",
        "views/web_lead_review_snapshot_views.xml",
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
