import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    x_requires_approval = fields.Boolean(string="Requires Approval", default=False)
    x_approved = fields.Boolean(string="Approved", default=False)

    def action_confirm(self):
        config = self.env["plasticos.automation.config"].get_config()
        for order in self:
            if order.amount_total > config.sale_approval_threshold and not order.x_approved:
                raise UserError(
                    "Approval required before confirmation. "
                    f"Order total {order.amount_total:.2f} exceeds threshold {config.sale_approval_threshold:.2f}."
                )
        return super().action_confirm()

    @api.model
    def cron_flag_sale_approvals(self):
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_automation.cron_sale_approval_flag"]
        )
        if not self.env.cr.fetchone()[0]:
            _logger.info("Skipping sale approval cron: lock is already held.")
            return

        try:
            config = self.env["plasticos.automation.config"].get_config()
            threshold = config.sale_approval_threshold
            orders = self.search(
                [
                    ("amount_total", ">", threshold),
                    ("state", "=", "draft"),
                    ("x_requires_approval", "=", False),
                ],
                order="id ASC",
                limit=500,
            )

            log_model = self.env.get("plasticos.automation.log")
            for order in orders:
                order.x_requires_approval = True
                if log_model:
                    log_model.create(
                        {
                            "name": f"Approval flag for {order.name}",
                            "model_name": "sale.order",
                            "res_id": order.id,
                            "action_type": "approval_flag",
                        }
                    )
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_automation.cron_sale_approval_flag"]
            )
