"""Tests for sale approval automation — threshold enforcement + cron flagging.

Target module: plasticos_automation
Target model:  sale.order (via _inherit)
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestSaleApproval(PlasticosTestCase):
    """Test sale order approval threshold enforcement."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env["plasticos.automation.config"]
        cls.Config.search([]).unlink()
        cls.config = cls.Config.create(
            {
                "name": "Test Config",
                "sale_approval_threshold": 5000.0,
                "invoice_overdue_days": 30,
                "contract_alert_days_before": 60,
                "stock_threshold_default": 100.0,
                "active": True,
            }
        )
        cls.partner = cls.env["res.partner"].create({"name": "Test Customer"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Regrind",
                "list_price": 10000.0,
            }
        )

    def _create_sale_order(self, amount=10000.0):
        """Create a draft SO with a single line at the given amount."""
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                            "price_unit": amount,
                        },
                    )
                ],
            }
        )
        return order

    # ── Confirm blocked without approval ─────────────────────

    def test_confirm_blocked_above_threshold(self):
        """Orders above threshold cannot be confirmed without approval."""
        order = self._create_sale_order(10000.0)
        with self.assertRaises(UserError):
            order.action_confirm()

    def test_confirm_allowed_below_threshold(self):
        """Orders below threshold confirm normally."""
        order = self._create_sale_order(1000.0)
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    def test_confirm_allowed_when_approved(self):
        """Orders above threshold confirm if pre-approved."""
        order = self._create_sale_order(10000.0)
        order.approved = True
        order.action_confirm()
        self.assertEqual(order.state, "sale")

    # ── Cron: flag sale approvals ────────────────────────────

    def test_cron_flags_draft_orders_above_threshold(self):
        """Cron should flag draft orders exceeding the threshold."""
        order = self._create_sale_order(10000.0)
        self.assertFalse(order.requires_approval)
        self.env["sale.order"].cron_flag_sale_approvals()
        order.invalidate_recordset()
        self.assertTrue(order.requires_approval)

    def test_cron_skips_below_threshold(self):
        """Cron should not flag orders below the threshold."""
        order = self._create_sale_order(1000.0)
        self.env["sale.order"].cron_flag_sale_approvals()
        order.invalidate_recordset()
        self.assertFalse(order.requires_approval)

    def test_cron_skips_already_flagged(self):
        """Cron should not re-flag orders already marked."""
        order = self._create_sale_order(10000.0)
        order.requires_approval = True
        log_before = self.env["plasticos.automation.log"].search_count([])
        self.env["sale.order"].cron_flag_sale_approvals()
        log_after = self.env["plasticos.automation.log"].search_count([])
        self.assertEqual(log_before, log_after)

    def test_cron_creates_automation_log(self):
        """Cron creates an automation log entry when flagging."""
        order = self._create_sale_order(10000.0)
        self.env["sale.order"].cron_flag_sale_approvals()
        logs = self.env["plasticos.automation.log"].search(
            [
                ("model_name", "=", "sale.order"),
                ("res_id", "=", order.id),
                ("action_type", "=", "approval_flag"),
            ]
        )
        self.assertEqual(len(logs), 1)
