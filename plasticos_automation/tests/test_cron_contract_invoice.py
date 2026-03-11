"""Tests for contract renewal alerts and invoice reminder crons.

Target module: plasticos_automation
Models:        res.partner (contract_renewal), account.move (invoice_reminder)
"""

from datetime import timedelta

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestCronContractRenewal(PlasticosTestCase):
    """Test contract renewal alert automation."""

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
        cls.AutoLog = cls.env["plasticos.automation.log"]

    def test_contract_expiring_within_window_triggers_alert(self):
        """Partner whose contract expires within alert window gets a chatter message."""
        partner = self.env["res.partner"].create(
            {
                "name": "Expiring Supplier",
                "contract_end_date": fields.Date.today() + timedelta(days=30),
            }
        )
        msg_count_before = len(partner.message_ids)
        self.env["res.partner"].cron_contract_renewal_alert()
        partner.invalidate_recordset()
        self.assertGreater(len(partner.message_ids), msg_count_before)

    def test_contract_far_future_no_alert(self):
        """Partner whose contract expires far in the future gets no alert."""
        partner = self.env["res.partner"].create(
            {
                "name": "Safe Supplier",
                "contract_end_date": fields.Date.today() + timedelta(days=365),
            }
        )
        msg_count_before = len(partner.message_ids)
        self.env["res.partner"].cron_contract_renewal_alert()
        partner.invalidate_recordset()
        self.assertEqual(len(partner.message_ids), msg_count_before)

    def test_expired_contract_no_alert(self):
        """Past contract_end_date does not trigger alert (already expired)."""
        partner = self.env["res.partner"].create(
            {
                "name": "Expired Supplier",
                "contract_end_date": fields.Date.today() - timedelta(days=10),
            }
        )
        msg_count_before = len(partner.message_ids)
        self.env["res.partner"].cron_contract_renewal_alert()
        partner.invalidate_recordset()
        self.assertEqual(len(partner.message_ids), msg_count_before)

    def test_no_duplicate_alerts_same_day(self):
        """Running cron twice on the same day should not duplicate alerts."""
        partner = self.env["res.partner"].create(
            {
                "name": "Alert Once Supplier",
                "contract_end_date": fields.Date.today() + timedelta(days=30),
            }
        )
        self.env["res.partner"].cron_contract_renewal_alert()
        log_count_1 = self.AutoLog.search_count(
            [
                ("model_name", "=", "res.partner"),
                ("res_id", "=", partner.id),
                ("action_type", "=", "contract_alert"),
            ]
        )
        self.env["res.partner"].cron_contract_renewal_alert()
        log_count_2 = self.AutoLog.search_count(
            [
                ("model_name", "=", "res.partner"),
                ("res_id", "=", partner.id),
                ("action_type", "=", "contract_alert"),
            ]
        )
        self.assertEqual(log_count_1, log_count_2, "Cron should not create duplicate alerts on same day")

    def test_no_contract_date_skipped(self):
        """Partners without contract_end_date are skipped."""
        partner = self.env["res.partner"].create(
            {
                "name": "No Contract Partner",
            }
        )
        msg_count_before = len(partner.message_ids)
        self.env["res.partner"].cron_contract_renewal_alert()
        partner.invalidate_recordset()
        self.assertEqual(len(partner.message_ids), msg_count_before)
