import logging
import secrets

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class PlasticosWebLeadConfig(models.Model):
    """Singleton configuration for the web leads REST endpoint.

    Stores the API key used to authenticate inbound requests from
    the lead_intake agent, plus default mapping preferences.
    """

    _name = "plasticos.web.lead.config"
    _description = "Web Lead Endpoint Configuration"

    name = fields.Char(
        default="Web Lead Configuration",
        readonly=True,
    )
    api_key = fields.Char(
        help="Bearer token the lead_intake agent must send. "
             "Generate via the button below.",
    )
    is_active = fields.Boolean(
        default=True,
        help="When disabled, the endpoint returns 503.",
    )
    default_source_type = fields.Selection(
        [
            ("post_consumer", "Post Consumer"),
            ("post_industrial", "Post Industrial"),
            ("purge", "Purge"),
            ("off_spec", "Off Spec"),
            ("mixed", "Mixed"),
        ],
        default="post_consumer",
        help="Default source type assigned to intakes created from web leads.",
    )
    auto_create_partner = fields.Boolean(
        default=True,
        help="Automatically create res.partner if company name not found.",
    )

    # ─────────────────────────────────────────────────────────
    # Singleton pattern
    # ─────────────────────────────────────────────────────────

    @api.model
    def get_config(self):
        """Return the singleton config record, creating it if needed."""
        config = self.search([], limit=1)
        if not config:
            config = self.create({"name": "Web Lead Configuration"})
        return config

    # ─────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────

    def action_generate_api_key(self):
        """Generate a cryptographically secure API key."""
        for rec in self:
            new_key = secrets.token_urlsafe(48)
            rec.write({"api_key": new_key})
            _logger.info(
                "Web Lead API key regenerated for config %s", rec.id,
            )
