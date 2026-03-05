import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    last_reminder_date = fields.Date(string="Last Reminder Date")

    @api.model
    def cron_invoice_reminder(self):
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_automation.cron_invoice_reminder"])
        if not self.env.cr.fetchone()[0]:
            _logger.info("Skipping invoice reminder cron: lock is already held.")
            return

        try:
            config = self.env["plasticos.automation.config"].get_config()
            today = fields.Date.today()
            cutoff = today - timedelta(days=config.invoice_overdue_days)
            overdue = self.search(
                [
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "posted"),
                    ("payment_state", "!=", "paid"),
                    ("invoice_date_due", "<=", cutoff),
                    "|",
                    ("last_reminder_date", "=", False),
                    ("last_reminder_date", "<", today),
                ],
                order="invoice_date_due ASC, id ASC",
                limit=200,
            )

            # Collect log entries for batch create
            log_vals_list = []
            for inv in overdue:
                inv.message_post(
                    body=f"Automated reminder: invoice is overdue by more than {config.invoice_overdue_days} days.",
                )
                inv.last_reminder_date = today
                log_vals_list.append(
                    {
                        "name": f"Invoice reminder {inv.name}",
                        "model_name": "account.move",
                        "res_id": inv.id,
                        "action_type": "invoice_reminder",
                    }
                )

            # Batch create all log entries
            if log_vals_list:
                self.env["plasticos.automation.log"].create(log_vals_list)
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_automation.cron_invoice_reminder"]
            )
