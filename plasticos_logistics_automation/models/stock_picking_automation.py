from odoo import models, fields, api

import logging

_logger = logging.getLogger(__name__)


class StockPickingAutomation(models.Model):
    _inherit = "stock.picking"

    # ── Broker / Dispatch Tracking ─────────────────────────────────
    x_broker_id = fields.Many2one(
        "res.partner",
        string="Freight Broker",
        help="The freight broker responsible for this delivery.",
    )
    x_receipt_confirmation = fields.Boolean(
        string="Broker Receipt Confirmed",
        default=False,
        help="Set when broker confirms receipt of dispatch packet.",
    )
    x_broker_notified_on = fields.Datetime(
        string="Broker Notified On",
        help="Timestamp when broker was first notified.",
    )
    x_broker_followup_count = fields.Integer(
        string="Broker Follow-ups",
        default=0,
        help="Number of follow-up attempts made to broker.",
    )

    @api.model
    def cron_broker_followup(self):
        """Send follow-up reminders to brokers who have not confirmed receipt.

        Targets outgoing pickings with a broker assigned but no receipt
        confirmation. Escalates to manager after 3 follow-ups.
        """
        pickings = self.search([
            ("picking_type_code", "=", "outgoing"),
            ("x_broker_id", "!=", False),
            ("x_receipt_confirmation", "=", False),
            ("state", "not in", ("done", "cancel")),
        ])

        log_model = self.env.get("plasticos.automation.log")

        for picking in pickings:
            picking.x_broker_followup_count += 1

            # Post chatter notification
            picking.message_post(
                body="Automated follow-up #%d: broker %s has not confirmed "
                     "receipt for %s."
                     % (picking.x_broker_followup_count,
                        picking.x_broker_id.name or "Unknown",
                        picking.name),
                message_type="notification",
            )

            # Send mail template if available
            template = self.env.ref(
                "plasticos_logistics_automation.mail_template_broker_followup",
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(picking.id, force_send=False)

            # Log to automation log
            if log_model is not None:
                log_model.create({
                    "name": "Broker follow-up #%d for %s"
                            % (picking.x_broker_followup_count, picking.name),
                    "model_name": "stock.picking",
                    "res_id": picking.id,
                    "action_type": "logistics_followup",
                })

            # Escalate after 3 follow-ups
            if picking.x_broker_followup_count >= 3:
                picking.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=picking.user_id.id or self.env.user.id,
                    summary="ESCALATION: Broker receipt unconfirmed on %s"
                            % picking.name,
                    note="Follow-up #%d sent. Broker %s has not confirmed "
                         "receipt. Manual intervention required."
                         % (picking.x_broker_followup_count,
                            picking.x_broker_id.name or "Unknown"),
                )

            _logger.info(
                "Logistics automation: broker follow-up #%d for %s",
                picking.x_broker_followup_count,
                picking.name,
            )
