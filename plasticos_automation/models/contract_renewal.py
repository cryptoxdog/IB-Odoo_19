import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    contract_end_date = fields.Date(string="Contract End Date")

    @api.model
    def cron_contract_renewal_alert(self):
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_automation.cron_contract_renewal_alert"]
        )
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
                    ("contract_end_date", "!=", False),
                    ("contract_end_date", "<=", threshold_date),
                    ("contract_end_date", ">=", today),
                ],
                order="contract_end_date ASC, id ASC",
                limit=200,
            )

            # One query for the partners already alerted today, one create for the new log rows.
            alerted_ids = set(
                log_model.search(
                    [
                        ("model_name", "=", "res.partner"),
                        ("res_id", "in", partners.ids),
                        ("action_type", "=", "contract_alert"),
                        ("create_date", ">=", fields.Datetime.to_datetime(f"{today} 00:00:00")),
                    ],
                    order="id ASC",
                ).mapped("res_id")
            )
            log_vals = []
            for partner in partners:
                if partner.id in alerted_ids:
                    continue

                partner.message_post(
                    body=(
                        f"Automated alert: contract expires on {partner.contract_end_date} "
                        f"(within {config.contract_alert_days_before} days)."
                    ),
                )
                log_vals.append(
                    {
                        "name": f"Contract renewal alert {partner.name}",
                        "model_name": "res.partner",
                        "res_id": partner.id,
                        "action_type": "contract_alert",
                    }
                )
            if log_vals:
                log_model.create(log_vals)
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_automation.cron_contract_renewal_alert"]
            )
