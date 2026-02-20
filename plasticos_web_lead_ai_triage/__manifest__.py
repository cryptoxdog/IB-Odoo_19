# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════
# Module : plasticos_web_lead_ai_triage
# Version: 19.0.1.0.0
# Author : PlasticOS
# Purpose: AI-powered web lead normalization + deterministic
#          HOT/COLD classification — zero external services.
# ═══════════════════════════════════════════════════════════
{
    "name": "PlasticOS Web Lead AI Triage",
    "version": "19.0.1.0.0",
    "summary": (
        "AI normalization (1 LLM + 1 Vision call) and deterministic "
        "HOT/COLD classification for web leads. Eliminates the external "
        "triage service — everything runs inside Odoo."
    ),
    "license": "LGPL-3",
    "author": "PlasticOS",
    "category": "Operations",
    "depends": [
        "base",
        "mail",
        "plasticos_web_leads",
        "plasticos_intake",
        "plasticos_material_profile",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/triage_config_data.xml",
        "data/logistics_ir_rules.xml",
        "views/triage_config_views.xml",
        "views/web_lead_triage_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
