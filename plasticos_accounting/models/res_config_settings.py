import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    @api.model
    def _register_hook(self):
        """Ensure currency_provider is always defined on res.config.settings.

        The Enterprise module currency_rate_live defines:
            currency_provider = fields.Selection(related="company_id.currency_provider")

        When that module is installed but in a broken state (stale DB entry,
        failed upgrade, partial install), the field is absent from the model
        registry but the Settings view still references it — crashing Owl with
        "field is undefined" and making the Settings page completely inaccessible.

        This hook runs at EVERY registry build (server start and module update),
        not just on first install. When currency_rate_live is healthy the field
        already exists and this is a no-op. When the field is missing we register
        a minimal safe placeholder so the Settings page renders instead of crashing.
        """
        super()._register_hook()
        cls = type(self)
        if "currency_provider" not in cls._fields:
            _logger.info(
                "plasticos_accounting: currency_provider not found on res.config.settings "
                "— registering fallback field (currency_rate_live may be in broken state)"
            )
            cls._add_field(
                "currency_provider",
                fields.Selection(
                    selection=[],
                    string="Currency Provider",
                    store=False,
                ),
            )
