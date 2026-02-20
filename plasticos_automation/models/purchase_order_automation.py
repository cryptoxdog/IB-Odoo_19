from odoo import models, fields, api

import logging

_logger = logging.getLogger(__name__)


class PurchaseOrderAutomation(models.Model):
    _inherit = "purchase.order"

    # ── Supplier Confirmation Tracking ─────────────────────────────
    x_ready_for_pickup = fields.Boolean(
        string="Ready for Pickup",
        default=False,
        help="Set when supplier confirms the load is ready for pickup.",
    )
    x_ready_confirmed_on = fields.Datetime(
        string="Ready Confirmed On",
        help="Timestamp when supplier confirmed readiness.",
    )
    x_followup_count = fields.Integer(
        string="Supplier Follow-up Count",
        default=0,
        help="Number of follow-up reminders sent to supplier.",
    )
    x_last_followup_on = fields.Datetime(
        string="Last Follow-up On",
        help="Timestamp of the last follow-up sent.",
    )
    x_buyer_id = fields.Many2one(
        "res.partner",
        string="Buyer (SO Customer)",
        help="The buyer/customer for this purchase (presell scenarios).",
    )

    # ── Automation Methods ─────────────────────────────────────────

    @api.model
    def cron_supplier_followup(self):
        """Send follow-up reminders to suppliers who have not confirmed readiness.

        Targets confirmed POs where x_ready_for_pickup is still False.
        Escalates to manager after 3 follow-ups.
        """
        orders = self.search([
            ("state", "=", "purchase"),
            ("x_ready_for_pickup", "=", False),
        ])

        log_model = self.env.get("plasticos.automation.log")

        for order in orders:
            order.x_followup_count += 1
            order.x_last_followup_on = fields.Datetime.now()

            # Post chatter notification
            order.message_post(
                body="Automated follow-up #%d: supplier has not confirmed "
                     "readiness for pickup on PO %s."
                     % (order.x_followup_count, order.name),
                message_type="notification",
            )

            # Send mail template if available
            template = self.env.ref(
                "plasticos_automation.mail_template_supplier_followup",
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(order.id, force_send=False)

            # Log to automation log
            if log_model is not None:
                log_model.create({
                    "name": "Supplier follow-up #%d for %s"
                            % (order.x_followup_count, order.name),
                    "model_name": "purchase.order",
                    "res_id": order.id,
                    "action_type": "logistics_followup",
                })

            # Escalate after 3 follow-ups
            if order.x_followup_count >= 3:
                order.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=order.user_id.id or self.env.user.id,
                    summary="ESCALATION: Supplier readiness unconfirmed on %s"
                            % order.name,
                    note="Follow-up #%d sent. Supplier %s has not confirmed "
                         "readiness. Manual intervention required."
                         % (order.x_followup_count,
                            order.partner_id.name or "Unknown"),
                )

            _logger.info(
                "Logistics automation: supplier follow-up #%d for PO %s",
                order.x_followup_count,
                order.name,
            )
