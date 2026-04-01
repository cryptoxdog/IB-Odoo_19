import logging
import secrets

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

LLM_PROVIDER_SELECTION = [
    ("openai", "OpenAI"),
    ("anthropic", "Anthropic"),
    ("mistral", "Mistral"),
]


class PlasticosWebLeadConfig(models.Model):
    """Singleton configuration for web leads REST endpoint and AI triage.

    Stores the API key for authentication, multi-provider LLM credentials
    for AI normalization/vision, classification thresholds, and reject lists.

    LLM Provider Fallback: Primary → Secondary → Tertiary.
    If the primary provider fails, the system automatically tries the next
    configured provider in priority order.
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
    # LLM Provider Configuration (Multi-Provider with Fallback)
    # ═══════════════════════════════════════════════════════════

    llm_primary_provider = fields.Selection(
        LLM_PROVIDER_SELECTION,
        string="Primary LLM Provider",
        default="openai",
        required=True,
        help="Primary AI provider. Used first for all LLM calls.",
    )
    llm_secondary_provider = fields.Selection(
        LLM_PROVIDER_SELECTION,
        string="Secondary LLM Provider",
        default="anthropic",
        help="Fallback provider if primary fails.",
    )
    llm_tertiary_provider = fields.Selection(
        LLM_PROVIDER_SELECTION,
        string="Tertiary LLM Provider",
        default="mistral",
        help="Last-resort fallback if both primary and secondary fail.",
    )

    # ── OpenAI ────────────────────────────────────────────────

    openai_api_key = fields.Char(
        string="OpenAI API Key",
        groups="base.group_system",
        help="API key for OpenAI (sk-...).",
    )
    openai_model = fields.Selection(
        [
            ("gpt-4o", "GPT-4o"),
            ("gpt-4o-mini", "GPT-4o Mini"),
            ("gpt-4.1", "GPT-4.1"),
            ("gpt-4.1-mini", "GPT-4.1 Mini"),
            ("gpt-4.1-nano", "GPT-4.1 Nano"),
            ("o3", "o3"),
            ("o3-mini", "o3 Mini"),
            ("o4-mini", "o4 Mini"),
            ("gpt-4.5-preview", "GPT-4.5 Preview"),
        ],
        string="Text Model",
        default="gpt-4o",
        help="Model for text normalization.",
    )
    openai_vision_model = fields.Selection(
        [
            ("gpt-4o", "GPT-4o"),
            ("gpt-4o-mini", "GPT-4o Mini"),
            ("gpt-4.1", "GPT-4.1"),
            ("gpt-4.1-mini", "GPT-4.1 Mini"),
            ("o3", "o3"),
            ("o4-mini", "o4 Mini"),
        ],
        string="Vision Model",
        default="gpt-4o",
        help="Model for image analysis (must support vision).",
    )

    # ── Anthropic ─────────────────────────────────────────────

    anthropic_api_key = fields.Char(
        string="Anthropic API Key",
        groups="base.group_system",
        help="API key for Anthropic (sk-ant-...).",
    )
    anthropic_model = fields.Selection(
        [
            ("claude-sonnet-4-20250514", "Claude Sonnet 4"),
            ("claude-opus-4-20250514", "Claude Opus 4"),
            ("claude-3-7-sonnet-20250219", "Claude 3.7 Sonnet"),
            ("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet"),
            ("claude-3-5-haiku-20241022", "Claude 3.5 Haiku"),
            ("claude-3-opus-20240229", "Claude 3 Opus"),
        ],
        string="Model",
        default="claude-sonnet-4-20250514",
        help="Anthropic model for text normalization.",
    )

    # ── Mistral ───────────────────────────────────────────────

    mistral_api_key = fields.Char(
        string="Mistral API Key",
        groups="base.group_system",
        help="API key for Mistral AI.",
    )
    mistral_model = fields.Selection(
        [
            ("mistral-large-latest", "Mistral Large"),
            ("mistral-medium-latest", "Mistral Medium"),
            ("mistral-small-latest", "Mistral Small"),
            ("open-mistral-nemo", "Mistral Nemo"),
            ("codestral-latest", "Codestral"),
            ("ministral-8b-latest", "Ministral 8B"),
        ],
        string="Model",
        default="mistral-large-latest",
        help="Mistral model for text normalization.",
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
    # LLM Provider Resolution (Fallback Chain)
    # ═══════════════════════════════════════════════════════════

    def get_llm_providers_ordered(self):
        """Return an ordered list of (provider, api_key, model, base_url) tuples.

        Follows the configured priority: primary → secondary → tertiary.
        Only providers with a configured API key are included.
        """
        self.ensure_one()
        provider_order = [
            self.llm_primary_provider,
            self.llm_secondary_provider,
            self.llm_tertiary_provider,
        ]
        seen = set()
        result = []
        for provider in provider_order:
            if not provider or provider in seen:
                continue
            seen.add(provider)
            info = self._get_provider_info(provider)
            if info and info["api_key"]:
                result.append(info)
        return result

    def get_vision_provider(self):
        """Return the vision-capable provider info (OpenAI only for now).

        Anthropic and Mistral vision support can be added here later.
        """
        self.ensure_one()
        if self.openai_api_key:
            return {
                "provider": "openai",
                "api_key": self.openai_api_key,
                "model": self.openai_vision_model or "gpt-4o",
                "base_url": None,
            }
        return None

    def _get_provider_info(self, provider):
        """Return dict with api_key, model, base_url for a given provider slug."""
        if provider == "openai" and self.openai_api_key:
            return {
                "provider": "openai",
                "api_key": self.openai_api_key,
                "model": self.openai_model or "gpt-4o",
                "base_url": None,
            }
        if provider == "anthropic" and self.anthropic_api_key:
            return {
                "provider": "anthropic",
                "api_key": self.anthropic_api_key,
                "model": self.anthropic_model or "claude-sonnet-4-20250514",
                "base_url": "https://api.anthropic.com/v1/",
            }
        if provider == "mistral" and self.mistral_api_key:
            return {
                "provider": "mistral",
                "api_key": self.mistral_api_key,
                "model": self.mistral_model or "mistral-large-latest",
                "base_url": "https://api.mistral.ai/v1/",
            }
        return None

    # ═══════════════════════════════════════════════════════════
    # Actions
    # ═══════════════════════════════════════════════════════════

    def action_generate_api_key(self):
        """Generate a cryptographically secure API key and show it in a copy-friendly dialog."""
        self.ensure_one()
        new_key = secrets.token_urlsafe(48)
        self.write({"api_key": new_key})
        _logger.info("Web Lead API key regenerated for config %s", self.id)
        wizard = self.env["plasticos.web.lead.api.key.wizard"].create(
            {
                "config_id": self.id,
                "api_key": new_key,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": "New API Key — copy now",
            "res_model": "plasticos.web.lead.api.key.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }
