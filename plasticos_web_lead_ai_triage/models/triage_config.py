# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════
# Model : plasticos.triage.config
# Purpose: Singleton configuration for the AI triage pipeline.
# ═══════════════════════════════════════════════════════════
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PlasticosTriageConfig(models.Model):
    """Singleton that stores all tunables for the web-lead AI triage
    pipeline: OpenAI credentials, classification thresholds, and
    reject-list patterns.
    """

    _name = "plasticos.triage.config"
    _description = "Web Lead AI Triage Configuration"

    name = fields.Char(default="Triage Configuration", required=True)

    # ── OpenAI Credentials ───────────────────────────────────
    openai_api_key = fields.Char(
        string="OpenAI API Key",
        help="API key for OpenAI. Used for text normalization and image analysis.",
    )
    openai_model = fields.Char(
        string="LLM Model",
        default="gpt-4.1-mini",
        help="Model for text normalization (e.g. gpt-4.1-mini, gpt-4.1-nano).",
    )
    openai_vision_model = fields.Char(
        string="Vision Model",
        default="gpt-4.1-mini",
        help="Model for image analysis (must support vision).",
    )

    # ── Classification Thresholds ────────────────────────────
    hot_min_lbs = fields.Integer(
        string="HOT Minimum (lbs)",
        default=10000,
        help="Minimum estimated lbs to qualify as HOT.",
    )
    cold_max_lbs = fields.Integer(
        string="Auto-COLD Below (lbs)",
        default=8000,
        help="Leads below this weight are auto-classified COLD.",
    )
    auto_create_partner = fields.Boolean(
        string="Auto-Create Partner",
        default=True,
        help="Automatically create res.partner for HOT leads.",
    )
    auto_create_intake = fields.Boolean(
        string="Auto-Create Intake",
        default=True,
        help="Automatically create plasticos.intake for HOT leads.",
    )

    # ── Reject-List (pipe-delimited for easy admin editing) ──
    reject_materials = fields.Text(
        string="Rejected Materials",
        default=(
            "vinyl siding|appliances|conduit|pvc pipe|"
            "pet bottles|carpet|mattress|tire"
        ),
        help=(
            "Pipe-delimited list of material keywords that trigger "
            "auto-COLD classification."
        ),
    )
    reject_sources = fields.Text(
        string="Rejected Sources",
        default="residential|individual|homeowner|drop-off|drop off",
        help=(
            "Pipe-delimited list of source keywords that trigger "
            "auto-COLD classification."
        ),
    )

    # ── Feature Toggles ──────────────────────────────────────
    ai_enabled = fields.Boolean(
        string="AI Normalization Enabled",
        default=True,
        help="When disabled, leads are classified on raw text only.",
    )
    vision_enabled = fields.Boolean(
        string="Vision Analysis Enabled",
        default=True,
        help="When disabled, image URLs are stored but not analyzed.",
    )

    # ═════════════════════════════════════════════════════════
    # Singleton Access
    # ═════════════════════════════════════════════════════════

    @api.model
    def get_config(self):
        """Return the singleton config record, creating it if needed."""
        config = self.search([], limit=1)
        if not config:
            config = self.create({"name": "Triage Configuration"})
            _logger.info("Created default triage configuration.")
        return config

    def get_reject_materials(self):
        """Return a frozenset of lowercase reject-material patterns."""
        raw = (self.reject_materials or "").strip()
        if not raw:
            return frozenset()
        return frozenset(p.strip().lower() for p in raw.split("|") if p.strip())

    def get_reject_sources(self):
        """Return a frozenset of lowercase reject-source patterns."""
        raw = (self.reject_sources or "").strip()
        if not raw:
            return frozenset()
        return frozenset(p.strip().lower() for p in raw.split("|") if p.strip())
