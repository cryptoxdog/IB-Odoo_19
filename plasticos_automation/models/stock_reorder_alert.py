import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    min_stock_threshold = fields.Float(string="Min Stock Threshold", default=0.0)

    @api.model
    def cron_stock_reorder_alert(self):
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_automation.cron_stock_reorder_alert"]
        )
        if not self.env.cr.fetchone()[0]:
            _logger.info("Skipping stock reorder cron: lock is already held.")
            return

        try:
            config = self.env["plasticos.automation.config"].get_config()
            global_threshold = config.stock_threshold_default
            today = fields.Date.today()
            log_model = self.env["plasticos.automation.log"]

            # Odoo 19: storable products use type='consu', earlier versions used 'product'
            products = self.search(
                [("type", "in", ("product", "consu"))],
                order="id ASC",
                limit=500,
            )

            # One query for the products already alerted today, one create for the new log rows.
            alerted_ids = set(
                log_model.search(
                    [
                        ("model_name", "=", "product.product"),
                        ("res_id", "in", products.ids),
                        ("action_type", "=", "stock_alert"),
                        ("create_date", ">=", fields.Datetime.to_datetime(f"{today} 00:00:00")),
                    ],
                    order="id ASC",
                ).mapped("res_id")
            )
            log_vals = []
            for product in products:
                threshold = product.min_stock_threshold or global_threshold
                if threshold <= 0 or product.qty_available >= threshold:
                    continue

                if product.id in alerted_ids:
                    continue

                product.message_post(
                    body=(
                        f"Automated alert: stock level {product.qty_available:.2f} is below threshold {threshold:.2f}."
                    ),
                )
                log_vals.append(
                    {
                        "name": f"Stock alert {product.display_name}",
                        "model_name": "product.product",
                        "res_id": product.id,
                        "action_type": "stock_alert",
                    }
                )
            if log_vals:
                log_model.create(log_vals)
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_automation.cron_stock_reorder_alert"]
            )
