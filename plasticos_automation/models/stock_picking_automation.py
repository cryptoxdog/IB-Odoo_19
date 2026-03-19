import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockPickingAutomation(models.Model):
    _inherit = "stock.picking"

    # ── Carrier / Dispatch Tracking ─────────────────────────────────
    carrier_id = fields.Many2one(
        "res.partner",
        string="Carrier",
        help="The carrier (trucker or freight broker) responsible for this delivery.",
    )
    receipt_confirmation = fields.Boolean(
        string="Trucker Receipt Confirmed",
        default=False,
        help="Set when trucker confirms receipt of dispatch packet.",
    )
    trucker_notified_on = fields.Datetime(
        string="Trucker Notified On",
        help="Timestamp when trucker was first notified.",
    )
    trucker_followup_count = fields.Integer(
        string="Trucker Follow-ups",
        default=0,
        help="Number of follow-up attempts made to trucker.",
    )

    @api.model
    def cron_trucker_followup(self):
        """Send follow-up reminders to truckers who have not confirmed receipt.

        Targets outgoing pickings with a trucker assigned but no receipt
        confirmation. Escalates to manager after 3 follow-ups.
        """
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_automation.cron_trucker_followup"])
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping trucker follow-up cron: lock is already held.")
            return

        try:
            now = fields.Datetime.now()
            pickings = self.search(
                [
                    ("picking_type_code", "=", "outgoing"),
                    ("carrier_id", "!=", False),
                    ("receipt_confirmation", "=", False),
                    ("state", "not in", ("done", "cancel")),
                    "|",
                    ("trucker_notified_on", "=", False),
                    ("trucker_notified_on", "<", fields.Datetime.subtract(now, days=1)),
                ],
                order="trucker_notified_on ASC, id ASC",
                limit=200,
            )

            log_model = self.env["plasticos.automation.log"]

            for picking in pickings:
                picking.trucker_followup_count += 1
                picking.trucker_notified_on = now
                trucker_name = picking.carrier_id.name or "Unknown"

                picking.message_post(
                    body=(
                        f"Automated follow-up #{picking.trucker_followup_count}: "
                        f"trucker {trucker_name} has not confirmed receipt for {picking.name}."
                    ),
                    message_type="notification",
                )

                template = self.env.ref(
                    "plasticos_automation.email_template_trucker_followup",
                    raise_if_not_found=False,
                )
                if template:
                    template.send_mail(picking.id, force_send=False)

                log_model.create(
                    {
                        "name": f"Trucker follow-up #{picking.trucker_followup_count} for {picking.name}",
                        "model_name": "stock.picking",
                        "res_id": picking.id,
                        "action_type": "logistics_followup",
                    }
                )

                if picking.trucker_followup_count >= 3:
                    picking.activity_schedule(
                        "mail.mail_activity_data_todo",
                        user_id=picking.user_id.id or self.env.user.id,
                        summary=f"ESCALATION: Trucker receipt unconfirmed on {picking.name}",
                        note=(
                            f"Follow-up #{picking.trucker_followup_count} sent. "
                            f"Trucker {trucker_name} has not confirmed receipt. "
                            "Manual intervention required."
                        ),
                    )

                _logger.info(
                    "Logistics automation: trucker follow-up #%d for %s",
                    picking.trucker_followup_count,
                    picking.name,
                )
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_automation.cron_trucker_followup"]
            )
