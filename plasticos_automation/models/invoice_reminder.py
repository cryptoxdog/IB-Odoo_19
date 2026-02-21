import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    x_last_reminder_date = fields.Date(
        string="Last Reminder Date",
        help="Date when the last overdue reminder was sent.",
    )

    @api.model
    def cron_invoice_reminder(self):
        """Send reminders for invoices overdue beyond the configured threshold."""
        config = self.env["plasticos.automation.config"].get_config()
        cutoff = fields.Date.today() - timedelta(days=config.invoice_overdue_days)

        overdue = self.search(
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "!=", "paid"),
                ("invoice_date_due", "<=", cutoff),
            ]
        )

        for inv in overdue:
            inv.message_post(
                body=f"Automated reminder: invoice is overdue by more than {config.invoice_overdue_days} days.",
            )
            inv.x_last_reminder_date = fields.Date.today()

            self.env["plasticos.automation.log"].create(
                {
                    "name": f"Invoice reminder {inv.name}",
                    "model_name": "account.move",
                    "res_id": inv.id,
                    "action_type": "invoice_reminder",
                }
            )
            _logger.info(
                "Automation: sent overdue reminder for %s (due=%s, cutoff=%s)",
                inv.name,
                inv.invoice_date_due,
                cutoff,
            )
