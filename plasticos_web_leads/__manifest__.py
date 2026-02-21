# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════
# Module : plasticos_web_leads
# Purpose: Web lead ingestion with AI-powered triage pipeline.
#          Supports both pre-processed agent payloads and raw
#          Cognito form submissions with LLM normalization,
#          vision analysis, and deterministic classification.
# ═══════════════════════════════════════════════════════════
{
    "name": "PlasticOS Web Leads",
    "version": "19.0.2.0.0",
    "summary": "AI-powered web lead triage: Cognito → LLM/Vision → HOT/COLD → Intake",
    "license": "LGPL-3",
    "author": "PlasticOS",
    "category": "Operations",
    "depends": [
        "base",
        "mail",
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
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
