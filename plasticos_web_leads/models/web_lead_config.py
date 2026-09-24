import logging
import secrets

from odoo import api, fields, models

from .evidence_keys import (
    KEY_API_KEY,
    KEY_BASE_URL,
    KEY_MODEL,
    KEY_PROVIDER,
    KEY_TEMPERATURE,
    KEY_TRANSPORT,
    KEY_WORKSPACE_ID,
)

_logger = logging.getLogger(__name__)

LLM_PROVIDER_SELECTION = [
    ("openai", "OpenAI"),
    ("anthropic", "Anthropic"),
    ("mistral", "Mistral"),
]

INFERENCE_TRANSPORT_SELECTION = [
    ("openai_compatible", "OpenAI-Compatible Chat Completions"),
    ("anthropic_messages", "Anthropic Messages API"),
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
        copy=False,
        help="Bearer token for authenticating inbound requests. "
        "Reveal the masked value (eye icon) or regenerate via the button below.",
    )
    api_key_configured = fields.Boolean(
        string="API Key Configured",
        compute="_compute_api_key_configured",
        help="True when an inbound webhook Bearer token is stored on this config.",
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
    hot_intake_reviewer_id = fields.Many2one(
        "res.users",
        string="HOT Intake Reviewer",
        ondelete="set null",
        domain="[('share', '=', False), ('active', '=', True)]",
        help=(
            "Internal Odoo user who receives the HOT web-lead review activity. "
            "When unset, Odoo records the handoff as blocked rather than routing "
            "it to the ingestion worker or an arbitrary user. ondelete='set null' "
            "is deliberate: deleting the reviewer must not cascade into deleting "
            "the configuration, and the resulting empty value is caught by the "
            "same blocked-handoff state, so a HOT lead is never silently assigned "
            "to a technical actor."
        ),
    )

    # ═══════════════════════════════════════════════════════════
    # Attachment Acquisition Policy
    # ═══════════════════════════════════════════════════════════

    attachment_allowed_hosts = fields.Text(
        string="Additional Attachment Hosts",
        help=(
            "Pipe-delimited hostnames the worker may fetch inbound attachments from, "
            "in addition to the provider adapter's built-in destination (for Cognito: "
            "cognitoforms.com and its subdomains). Subdomains of a listed host are "
            "accepted. Every fetch is HTTPS-only, must resolve to a public address, "
            "and each redirect hop is revalidated against this policy."
        ),
    )

    # ═══════════════════════════════════════════════════════════
    # Inference Role Selection
    # ═══════════════════════════════════════════════════════════

    text_inference_provider = fields.Selection(
        LLM_PROVIDER_SELECTION,
        string="Text Inference Provider",
        default="openai",
        required=True,
        help="Provider used for structured text normalization. Change this setting to swap providers without code changes.",
    )
    vision_inference_provider = fields.Selection(
        LLM_PROVIDER_SELECTION,
        string="Vision Inference Provider",
        default="openai",
        required=True,
        help="Provider used for structured analysis of each admitted image.",
    )
    economic_inference_provider = fields.Selection(
        LLM_PROVIDER_SELECTION,
        string="Economic Assessment Provider",
        default="openai",
        required=True,
        help="Provider used for advisory opportunity assessment after deterministic evidence and policy gates pass.",
    )
    inference_temperature = fields.Float(
        string="Inference Temperature",
        default=0.0,
        help="Sampling temperature for structured inference. Zero is required for repeatable triage behavior.",
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
    openai_model = fields.Char(
        string="Text Model Identifier",
        default="gpt-4o",
        help="OpenAI-compatible model identifier for text normalization. The value is intentionally unrestricted so operators can change models without code changes.",
    )
    openai_vision_model = fields.Char(
        string="Vision Model Identifier",
        default="gpt-4o",
        help="OpenAI-compatible multimodal model identifier for image analysis.",
    )

    openai_economic_model = fields.Char(
        string="Economic Assessment Model Identifier",
        default="gpt-4o",
        help="OpenAI-compatible model identifier for advisory economic opportunity assessment.",
    )

    # ── Anthropic ─────────────────────────────────────────────

    anthropic_api_key = fields.Char(
        string="Anthropic API Key",
        groups="base.group_system",
        help="API key for Anthropic (sk-ant-...).",
    )
    anthropic_model = fields.Char(
        string="Text Model Identifier",
        default="claude-sonnet-4-20250514",
        help="Anthropic model identifier for text normalization, for example a configured Claude Haiku model.",
    )
    anthropic_vision_model = fields.Char(
        string="Vision Model Identifier",
        default="claude-sonnet-4-20250514",
        help="Anthropic multimodal model identifier used for structured image analysis.",
    )
    anthropic_economic_model = fields.Char(
        string="Economic Assessment Model Identifier",
        default="claude-sonnet-4-20250514",
        help="Anthropic model identifier used for advisory economic opportunity assessment.",
    )
    anthropic_transport = fields.Selection(
        INFERENCE_TRANSPORT_SELECTION,
        string="Anthropic Transport",
        default="anthropic_messages",
        required=True,
        help="Native Anthropic Messages API is the production default; OpenAI compatibility is for comparison only.",
    )
    anthropic_base_url = fields.Char(
        string="Anthropic API Base URL",
        default="https://api.anthropic.com",
        help="Optional Anthropic-compatible endpoint. Leave at the default for the native Claude API.",
    )
    anthropic_workspace_id = fields.Char(
        string="Anthropic Workspace ID",
        groups="base.group_system",
        help="Optional Anthropic workspace header for multi-workspace keys.",
    )

    # ── Mistral ───────────────────────────────────────────────

    mistral_api_key = fields.Char(
        string="Mistral API Key",
        groups="base.group_system",
        help="API key for Mistral AI.",
    )
    mistral_model = fields.Char(
        string="Text Model Identifier",
        default="mistral-large-latest",
        help="OpenAI-compatible Mistral model identifier for text normalization.",
    )
    mistral_vision_model = fields.Char(
        string="Vision Model Identifier",
        default="mistral-large-latest",
        help="OpenAI-compatible Mistral multimodal model identifier used for image analysis.",
    )
    mistral_economic_model = fields.Char(
        string="Economic Assessment Model Identifier",
        default="mistral-large-latest",
        help="OpenAI-compatible Mistral model identifier used for advisory economic opportunity assessment.",
    )
    mistral_base_url = fields.Char(
        string="Mistral API Base URL",
        default="https://api.mistral.ai/v1",
        help="OpenAI-compatible Mistral API endpoint.",
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
    reusable_item_hot_min_lbs = fields.Integer(
        string="Reusable Item HOT Minimum (lbs)",
        default=8000,
        help="Lower HOT threshold only for canonical reusable-item material classes such as pallets, totes, and crates. It never applies to LDPE film or other polymer grades by themselves.",
    )
    reusable_item_policy_codes = fields.Text(
        string="Reusable Item Policy Codes",
        default="PLASTIC_PALLETS|PALLETS|TOTES|CRATES",
        help="Pipe-delimited canonical polymer or material-form codes allowed to use the reusable-item threshold. This is an explicit allow-list, not a polymer-grade rule.",
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

    @api.depends("api_key")
    def _compute_api_key_configured(self):
        for rec in self:
            rec.api_key_configured = bool((rec.api_key or "").strip())

    @api.model
    def get_config(self):
        """Return the singleton config record, creating it if needed.

        Prefers the XML-seeded ``web_lead_config_default`` record so auth always
        validates against the same row the Settings form opens — not an arbitrary
        ``search([], limit=1)`` hit when duplicate configs exist.
        """
        config = self.env.ref(
            "plasticos_web_leads.web_lead_config_default",
            raise_if_not_found=False,
        )
        if config and config.exists():
            return config
        config = self.search([], limit=1, order="id asc")
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

    def get_reusable_item_policy_codes(self):
        """Return canonical uppercase material codes eligible for the lower threshold."""
        raw = (self.reusable_item_policy_codes or "").strip()
        if not raw:
            return frozenset()
        return frozenset(code.strip().upper() for code in raw.split("|") if code.strip())

    def get_attachment_allowed_hosts(self, provider_hosts=()):
        """Return the attachment destination allowlist: adapter default plus operator additions."""
        hosts = [str(host).strip().lower() for host in (provider_hosts or ()) if str(host).strip()]
        raw = (self.attachment_allowed_hosts or "").strip() if self else ""
        for entry in raw.split("|"):
            host = entry.strip().lower()
            if host and host not in hosts:
                hosts.append(host)
        return tuple(hosts)

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
        """Return the configured swappable provider for vision analysis."""
        return self.get_inference_provider("vision_analysis")

    def get_inference_provider(self, role):
        """Resolve one configured provider profile for a named inference role.

        Credentials remain only in configuration. Returned metadata is safe for
        runtime client construction; callers must persist only its redacted
        provider/model/transport identity in evidence.
        """
        self.ensure_one()
        provider_by_role = {
            "text_normalization": self.text_inference_provider,
            "vision_analysis": self.vision_inference_provider,
            "economic_evaluation": self.economic_inference_provider,
        }
        provider = provider_by_role.get(role)
        if provider == "openai" and self.openai_api_key:
            model_by_role = {
                "text_normalization": self.openai_model or "gpt-4o",
                "vision_analysis": self.openai_vision_model or "gpt-4o",
                "economic_evaluation": self.openai_economic_model or "gpt-4o",
            }
            return {
                KEY_PROVIDER: "openai",
                KEY_TRANSPORT: "openai_compatible",
                KEY_API_KEY: self.openai_api_key,
                KEY_MODEL: model_by_role[role],
                KEY_BASE_URL: None,
                KEY_WORKSPACE_ID: None,
                KEY_TEMPERATURE: self.inference_temperature,
            }
        if provider == "anthropic" and self.anthropic_api_key:
            model_by_role = {
                "text_normalization": self.anthropic_model or "claude-sonnet-4-20250514",
                "vision_analysis": self.anthropic_vision_model or "claude-sonnet-4-20250514",
                "economic_evaluation": self.anthropic_economic_model or "claude-sonnet-4-20250514",
            }
            return {
                KEY_PROVIDER: "anthropic",
                KEY_TRANSPORT: self.anthropic_transport or "anthropic_messages",
                KEY_API_KEY: self.anthropic_api_key,
                KEY_MODEL: model_by_role[role],
                KEY_BASE_URL: self.anthropic_base_url or "https://api.anthropic.com",
                KEY_WORKSPACE_ID: self.anthropic_workspace_id or None,
                KEY_TEMPERATURE: self.inference_temperature,
            }
        if provider == "mistral" and self.mistral_api_key:
            model_by_role = {
                "text_normalization": self.mistral_model or "mistral-large-latest",
                "vision_analysis": self.mistral_vision_model or "mistral-large-latest",
                "economic_evaluation": self.mistral_economic_model or "mistral-large-latest",
            }
            return {
                KEY_PROVIDER: "mistral",
                KEY_TRANSPORT: "openai_compatible",
                KEY_API_KEY: self.mistral_api_key,
                KEY_MODEL: model_by_role[role],
                KEY_BASE_URL: self.mistral_base_url or "https://api.mistral.ai/v1",
                KEY_WORKSPACE_ID: None,
                KEY_TEMPERATURE: self.inference_temperature,
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
        """Generate a cryptographically secure API key and show it in a copy-friendly dialog.

        Always persist on get_config() (XML singleton), not merely ``self``, so the
        key the wizard displays is the same row the public API authenticates against.
        """
        self.ensure_one()
        target = self.get_config()
        new_key = secrets.token_urlsafe(48)
        target.write({"api_key": new_key})
        # Keep the open form row in sync when an orphan duplicate was edited.
        if self.id != target.id:
            self.write({"api_key": new_key})
            _logger.warning(
                "Web Lead API key written to singleton config %s (form was orphan %s)",
                target.id,
                self.id,
            )
        else:
            _logger.info("Web Lead API key regenerated for config %s", target.id)
        wizard = self.env["plasticos.web.lead.api.key.wizard"].create(
            {
                "config_id": target.id,
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
