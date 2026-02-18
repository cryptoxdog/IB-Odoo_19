from odoo import models, fields, api

from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    x_contract_end_date = fields.Date(
        string="Contract End Date",
        help="End date of the partner's active contract.",
    )

    @api.model
    def cron_contract_renewal_alert(self):
        """Alert for contracts nearing expiration within the configured window."""
        config = self.env["plasticos.automation.config"].get_config()
        threshold_date = fields.Date.today() + timedelta(
            days=config.contract_alert_days_before,
        )

        partners = self.search([
            ("x_contract_end_date", "!=", False),
            ("x_contract_end_date", "<=", threshold_date),
            ("x_contract_end_date", ">=", fields.Date.today()),
        ])

        for partner in partners:
            partner.message_post(
                body="Automated alert: contract expires on %s (within %d days)."
                % (partner.x_contract_end_date, config.contract_alert_days_before),
            )

            self.env["plasticos.automation.log"].create({
                "name": "Contract renewal alert %s" % partner.name,
                "model_name": "res.partner",
                "res_id": partner.id,
                "action_type": "contract_alert",
            })
            _logger.info(
                "Automation: contract renewal alert for %s (expires=%s)",
                partner.name,
                partner.x_contract_end_date,
            )
