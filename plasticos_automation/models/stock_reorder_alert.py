from odoo import models, fields, api

import logging

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    x_min_stock_threshold = fields.Float(
        string="Min Stock Threshold",
        default=0.0,
        help="Per-product minimum stock level override. "
             "Falls back to the global default if zero.",
    )

    @api.model
    def cron_stock_reorder_alert(self):
        """Alert for products whose available stock falls below threshold.

        Per-product threshold takes precedence over the global default.
        Products with both thresholds at zero are skipped.
        """
        config = self.env["plasticos.automation.config"].get_config()
        global_threshold = config.stock_threshold_default

        products = self.search([
            ("type", "=", "product"),
        ])

        for product in products:
            threshold = product.x_min_stock_threshold or global_threshold
            if threshold <= 0:
                continue

            if product.qty_available < threshold:
                product.message_post(
                    body="Automated alert: stock level %.2f is below threshold %.2f."
                    % (product.qty_available, threshold),
                )

                self.env["plasticos.automation.log"].create({
                    "name": "Stock alert %s" % product.display_name,
                    "model_name": "product.product",
                    "res_id": product.id,
                    "action_type": "stock_alert",
                })
                _logger.info(
                    "Automation: stock alert for %s (qty=%.2f, threshold=%.2f)",
                    product.display_name,
                    product.qty_available,
                    threshold,
                )
