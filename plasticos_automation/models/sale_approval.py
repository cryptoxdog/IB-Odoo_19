from odoo import models, fields, api
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    x_requires_approval = fields.Boolean(
        string="Requires Approval",
        default=False,
        help="Flagged by automation when order exceeds approval threshold.",
    )
    x_approved = fields.Boolean(
        string="Approved",
        default=False,
        help="Set to True when a manager approves the order.",
    )

    def action_confirm(self):
        """Gate confirmation on approval for orders exceeding threshold."""
        config = self.env["plasticos.automation.config"].get_config()

        for order in self:
            if (
                order.amount_total > config.sale_approval_threshold
                and not order.x_approved
            ):
                raise UserError(
                    "Approval required before confirmation. "
                    "Order total %.2f exceeds threshold %.2f."
                    % (order.amount_total, config.sale_approval_threshold)
                )

        return super().action_confirm()

    @api.model
    def cron_flag_sale_approvals(self):
        """Flag draft orders exceeding the configured approval threshold."""
        config = self.env["plasticos.automation.config"].get_config()
        threshold = config.sale_approval_threshold

        orders = self.search([
            ("amount_total", ">", threshold),
            ("state", "=", "draft"),
            ("x_requires_approval", "=", False),
        ])

        for order in orders:
            order.x_requires_approval = True
            self.env["plasticos.automation.log"].create({
                "name": "Approval flag for %s" % order.name,
                "model_name": "sale.order",
                "res_id": order.id,
                "action_type": "approval_flag",
            })
            _logger.info(
                "Automation: flagged %s for approval (total=%.2f, threshold=%.2f)",
                order.name,
                order.amount_total,
                threshold,
            )
