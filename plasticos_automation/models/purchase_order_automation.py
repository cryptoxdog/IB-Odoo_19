import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

OPERATIONS_MANAGER_GROUP = "plasticos_security_base.group_operations_manager"


class PurchaseOrderAutomation(models.Model):
    _inherit = "purchase.order"

    supplier_ready = fields.Boolean(string="Ready for Pickup", default=False)
    ready_confirmed_on = fields.Datetime(string="Ready Confirmed On")
    followup_count = fields.Integer(string="Supplier Follow-up Count", default=0)
    last_followup_on = fields.Datetime(string="Last Follow-up On")
    buyer_id = fields.Many2one("res.partner", string="Buyer (SO Customer)", ondelete="restrict")

    @api.model
    def cron_supplier_followup(self):
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_automation.cron_supplier_followup"]
        )
        if not self.env.cr.fetchone()[0]:
            _logger.info("Skipping supplier follow-up cron: lock is already held.")
            return

        try:
            now = fields.Datetime.now()
            orders = self.search(
                [
                    ("state", "=", "purchase"),
                    ("supplier_ready", "=", False),
                    "|",
                    ("last_followup_on", "=", False),
                    ("last_followup_on", "<", fields.Datetime.subtract(now, days=1)),
                ],
                order="last_followup_on ASC, id ASC",
                limit=200,
            )
            log_model = self.env["plasticos.automation.log"]
            log_vals = []

            for order in orders:
                order.followup_count += 1
                order.last_followup_on = now
                order.message_post(
                    body=(
                        f"Automated follow-up #{order.followup_count}: supplier has not "
                        f"confirmed readiness for pickup on PO {order.name}."
                    ),
                    message_type="notification",
                )
                template = self.env.ref(
                    "plasticos_automation.email_template_supplier_followup", raise_if_not_found=False
                )
                if template:
                    template.send_mail(order.id, force_send=False)
                log_vals.append(
                    {
                        "name": f"Supplier follow-up #{order.followup_count} for {order.name}",
                        "model_name": "purchase.order",
                        "res_id": order.id,
                        "action_type": "logistics_followup",
                    }
                )
                if order.followup_count >= 3:
                    # One open escalation per order, owned by an Operations Manager in the
                    # order's company: never the buyer on the order, never the cron user.
                    self.env["res.users"]._plasticos_escalate_to_manager(
                        order,
                        OPERATIONS_MANAGER_GROUP,
                        summary=f"ESCALATION: Supplier readiness unconfirmed on {order.name}",
                        note=(
                            f"Follow-up #{order.followup_count} sent. Supplier "
                            f"{order.partner_id.name or 'Unknown'} has not confirmed readiness."
                        ),
                        label="supplier readiness escalation",
                        companies=order.company_id,
                        exclude_users=order.user_id,
                    )
            if log_vals:
                log_model.create(log_vals)
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_automation.cron_supplier_followup"]
            )
