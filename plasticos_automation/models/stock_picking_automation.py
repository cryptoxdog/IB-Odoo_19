import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockPickingAutomation(models.Model):
    _inherit = "stock.picking"

    # ── Trucker / Dispatch Tracking ─────────────────────────────────
    x_trucker_id = fields.Many2one(
        "res.partner",
        string="Trucker",
        help="The trucker (carrier or freight broker) responsible for this delivery.",
    )
    x_receipt_confirmation = fields.Boolean(
        string="Trucker Receipt Confirmed",
        default=False,
        help="Set when trucker confirms receipt of dispatch packet.",
    )
    x_trucker_notified_on = fields.Datetime(
        string="Trucker Notified On",
        help="Timestamp when trucker was first notified.",
    )
    x_trucker_followup_count = fields.Integer(
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
        pickings = self.search(
            [
                ("picking_type_code", "=", "outgoing"),
                ("x_trucker_id", "!=", False),
                ("x_receipt_confirmation", "=", False),
                ("state", "not in", ("done", "cancel")),
            ]
        )

        log_model = self.env.get("plasticos.automation.log")

        for picking in pickings:
            picking.x_trucker_followup_count += 1

            # Post chatter notification
            picking.message_post(
                body="Automated follow-up #%d: trucker %s has not confirmed "
                "receipt for %s."
                % (picking.x_trucker_followup_count, picking.x_trucker_id.name or "Unknown", picking.name),
                message_type="notification",
            )

            # Send mail template if available
            template = self.env.ref(
                "plasticos_automation.email_template_trucker_followup",
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(picking.id, force_send=False)

            # Log to automation log
            if log_model is not None:
                log_model.create(
                    {
                        "name": "Trucker follow-up #%d for %s" % (picking.x_trucker_followup_count, picking.name),
                        "model_name": "stock.picking",
                        "res_id": picking.id,
                        "action_type": "logistics_followup",
                    }
                )

            # Escalate after 3 follow-ups
            if picking.x_trucker_followup_count >= 3:
                picking.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=picking.user_id.id or self.env.user.id,
                    summary="ESCALATION: Trucker receipt unconfirmed on %s" % picking.name,
                    note="Follow-up #%d sent. Trucker %s has not confirmed "
                    "receipt. Manual intervention required."
                    % (picking.x_trucker_followup_count, picking.x_trucker_id.name or "Unknown"),
                )

            _logger.info(
                "Logistics automation: trucker follow-up #%d for %s",
                picking.x_trucker_followup_count,
                picking.name,
            )
