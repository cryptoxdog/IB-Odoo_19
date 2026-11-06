"""Automation crons write their log rows in one create and dedupe with one query."""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


def _counting(model_cls, method_name, calls):
    real = getattr(model_cls, method_name)

    def wrapped(self, *args, **kwargs):
        calls.append(args[0] if args else kwargs)
        return real(self, *args, **kwargs)

    return patch.object(model_cls, method_name, wrapped)


def _log_count(env, model_name, res_id, action_type):
    return env["plasticos.automation.log"].search_count(
        [("model_name", "=", model_name), ("res_id", "=", res_id), ("action_type", "=", action_type)]
    )


@tagged("post_install", "-at_install", "cron", "automation")
class TestCronLogBatch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.log_cls = type(cls.env["plasticos.automation.log"])
        cls.config = cls.env["plasticos.automation.config"].get_config()

    def test_sale_approval_flags_two_orders_with_one_log_create(self):
        self.config.sale_approval_threshold = 100.0
        partner = self.env["res.partner"].create({"name": "Approval Batch Buyer", "is_company": True})
        product = self.env["product.product"].create({"name": "Approval Batch Goods", "type": "consu"})
        orders = self.env["sale.order"].create(
            [
                {
                    "partner_id": partner.id,
                    "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": 10, "price_unit": 50.0})],
                }
                for _ in range(2)
            ]
        )
        self.assertTrue(all(order.amount_total > 100.0 for order in orders))
        creates = []
        with _counting(self.log_cls, "create", creates):
            self.env["sale.order"].cron_flag_sale_approvals()
        self.assertEqual(len(creates), 1, creates)
        for order in orders:
            self.assertTrue(order.requires_approval)
            self.assertEqual(_log_count(self.env, "sale.order", order.id, "approval_flag"), 1)

    def test_stock_alert_dedupes_with_one_query_and_logs_with_one_create(self):
        products = self.env["product.product"].create(
            [{"name": f"Reorder Batch {index}", "type": "consu", "min_stock_threshold": 5.0} for index in range(2)]
        )
        searches, creates = [], []
        with _counting(self.log_cls, "search", searches), _counting(self.log_cls, "create", creates):
            self.env["product.product"].cron_stock_reorder_alert()
        self.assertEqual(len(searches), 1, searches)
        self.assertLessEqual(len(creates), 1, creates)
        for product in products:
            self.assertEqual(_log_count(self.env, "product.product", product.id, "stock_alert"), 1)
        self.env["product.product"].cron_stock_reorder_alert()
        for product in products:
            self.assertEqual(_log_count(self.env, "product.product", product.id, "stock_alert"), 1)

    def test_contract_renewal_dedupes_with_one_query_and_logs_with_one_create(self):
        soon = fields.Date.today() + timedelta(days=1)
        partners = self.env["res.partner"].create(
            [{"name": f"Renewal Batch {index}", "is_company": True, "contract_end_date": soon} for index in range(2)]
        )
        searches, creates = [], []
        with _counting(self.log_cls, "search", searches), _counting(self.log_cls, "create", creates):
            self.env["res.partner"].cron_contract_renewal_alert()
        self.assertEqual(len(searches), 1, searches)
        self.assertLessEqual(len(creates), 1, creates)
        for partner in partners:
            self.assertEqual(_log_count(self.env, "res.partner", partner.id, "contract_alert"), 1)
        self.env["res.partner"].cron_contract_renewal_alert()
        for partner in partners:
            self.assertEqual(_log_count(self.env, "res.partner", partner.id, "contract_alert"), 1)
