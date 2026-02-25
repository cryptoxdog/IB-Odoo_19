import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    x_contract_end_date = fields.Date(string="Contract End Date")

    @api.model
    def cron_contract_renewal_alert(self):
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_automation.cron_contract_renewal_alert"])
        if not self.env.cr.fetchone()[0]:
            _logger.info("Skipping contract renewal cron: lock is already held.")
            return

        try:
            config = self.env["plasticos.automation.config"].get_config()
            today = fields.Date.today()
            threshold_date = today + timedelta(days=config.contract_alert_days_before)
            log_model = self.env["plasticos.automation.log"]

            partners = self.search(
                [
                    ("x_contract_end_date", "!=", False),
                    ("x_contract_end_date", "<=", threshold_date),
                    ("x_contract_end_date", ">=", today),
                ],
                order="x_contract_end_date ASC, id ASC",
                limit=200,
            )

            for partner in partners:
                existing_log = log_model.search_count(
                    [
                        ("model_name", "=", "res.partner"),
                        ("res_id", "=", partner.id),
                        ("action_type", "=", "contract_alert"),
                        ("create_date", ">=", fields.Datetime.to_datetime(f"{today} 00:00:00")),
                    ]
                )
                if existing_log:
                    continue

                partner.message_post(
                    body=(
                        f"Automated alert: contract expires on {partner.x_contract_end_date} "
                        f"(within {config.contract_alert_days_before} days)."
                    ),
                )
                log_model.create(
                    {
                        "name": f"Contract renewal alert {partner.name}",
                        "model_name": "res.partner",
                        "res_id": partner.id,
                        "action_type": "contract_alert",
                    }
                )
        finally:
            self.env.cr.execute("SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_automation.cron_contract_renewal_alert"])
