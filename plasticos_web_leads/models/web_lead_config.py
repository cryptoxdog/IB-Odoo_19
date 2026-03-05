import logging
import secrets

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PlasticosWebLeadConfig(models.Model):
    """Singleton configuration for web leads REST endpoint and AI triage.

    Stores the API key for authentication, OpenAI credentials for AI
    normalization/vision, classification thresholds, and reject lists.
    """

    _name = "plasticos.web.lead.config"
    _description = "Web Lead Configuration"

    name = fields.Char(
        default="Web Lead Configuration",
        readonly=True,
    )

    # ═══════════════════════════════════════════════════════════
    # Endpoint Settings
    # ═══════════════════════════════════════════════════════════

    api_key = fields.Char(
        groups="base.group_system",
        help="Bearer token for authenticating inbound requests. Generate via the button below.",
    )
    is_active = fields.Boolean(
        default=True,
        help="When disabled, endpoints return 503.",
    )
    default_source_type = fields.Selection(
        [
            ("post_consumer", "Post Consumer"),
            ("post_industrial", "Post Industrial"),
            ("post_commercial", "Post Commercial"),
            ("agricultural", "Agricultural"),
            ("prime", "Prime/Virgin"),
            ("wide_spec", "Wide Spec"),
            ("off_spec", "Off Spec"),
            ("ocean_recovered", "Ocean Recovered"),
        ],
        default="post_consumer",
        help="Default source type for intakes created from web leads.",
    )

    # ═══════════════════════════════════════════════════════════
    # Automation Toggles
    # ═══════════════════════════════════════════════════════════

    auto_create_partner = fields.Boolean(
        default=True,
        help="Create res.partner when admin clicks 'Match to Buyers' on intake. "
        "Partner is NOT created on lead receipt — only when matching.",
    )
    auto_create_intake = fields.Boolean(
        default=True,
        help="Create plasticos.intake for HOT leads (without partner). "
        "Admin reviews intake before deciding to buyer-match or discard.",
    )

    # ═══════════════════════════════════════════════════════════
    # OpenAI Credentials (for AI Triage)
    # ═══════════════════════════════════════════════════════════

    openai_api_key = fields.Char(
        string="OpenAI API Key",
        help="API key for OpenAI. Used for text normalization and image analysis.",
    )
    openai_model = fields.Char(
        string="LLM Model",
        default="gpt-4.1-mini",
        help="Model for text normalization (e.g. gpt-4.1-mini).",
    )
    openai_vision_model = fields.Char(
        string="Vision Model",
        default="gpt-4.1-mini",
        help="Model for image analysis (must support vision).",
    )

    # ═══════════════════════════════════════════════════════════
    # Classification Thresholds
    # ═══════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════
    # Reject Lists (pipe-delimited for easy admin editing)
    # ═══════════════════════════════════════════════════════════

    reject_materials = fields.Text(
        string="Rejected Materials",
        default="vinyl siding|appliances|conduit|pvc pipe|pet bottles|carpet|mattress|tire",
        help="Pipe-delimited list of material keywords that trigger auto-COLD.",
    )
    reject_sources = fields.Text(
        string="Rejected Sources",
        default="residential|individual|homeowner|drop-off|drop off",
        help="Pipe-delimited list of source keywords that trigger auto-COLD.",
    )

    # ═══════════════════════════════════════════════════════════
    # Feature Toggles
    # ═══════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════
    # Singleton Access
    # ═══════════════════════════════════════════════════════════

    @api.model
    def get_config(self):
        """Return the singleton config record, creating it if needed."""
        config = self.search([], limit=1)
        if not config:
            config = self.create({"name": "Web Lead Configuration"})
            _logger.info("Created default web lead configuration.")
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

    # ═══════════════════════════════════════════════════════════
    # Actions
    # ═══════════════════════════════════════════════════════════

    def action_generate_api_key(self):
        """Generate a cryptographically secure API key."""
        for rec in self:
            new_key = secrets.token_urlsafe(48)
            rec.write({"api_key": new_key})
            _logger.info("Web Lead API key regenerated for config %s", rec.id)
