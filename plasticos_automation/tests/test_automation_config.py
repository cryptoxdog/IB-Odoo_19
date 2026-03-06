"""Tests for plasticos.automation.config — singleton pattern & threshold validation.

Target module: plasticos_automation
Target model:  plasticos.automation.config
"""

from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestAutomationConfig(PlasticosTestCase):
    """Test the PlastOS automation configuration singleton."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env["plasticos.automation.config"]
        # Ensure clean slate
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

    # ── Singleton ────────────────────────────────────────────

    def test_get_config_returns_active_record(self):
        """get_config() returns the active singleton."""
        config = self.Config.get_config()
        self.assertEqual(config.id, self.config.id)

    def test_get_config_raises_when_no_active(self):
        """get_config() raises ValidationError when no active config exists."""
        self.config.active = False
        with self.assertRaises(ValidationError):
            self.Config.get_config()

    def test_singleton_constraint_prevents_two_active(self):
        """Only one active configuration record is allowed."""
        with self.assertRaises((ValidationError, IntegrityError)):
            self.Config.create(
                {
                    "name": "Duplicate Config",
                    "sale_approval_threshold": 1000.0,
                    "invoice_overdue_days": 7,
                    "contract_alert_days_before": 30,
                    "stock_threshold_default": 50.0,
                    "active": True,
                }
            )

    def test_second_config_allowed_when_inactive(self):
        """A second config record is allowed if inactive."""
        config2 = self.Config.create(
            {
                "name": "Inactive Config",
                "sale_approval_threshold": 1000.0,
                "invoice_overdue_days": 7,
                "contract_alert_days_before": 30,
                "stock_threshold_default": 50.0,
                "active": False,
            }
        )
        self.assertTrue(config2.id)

    # ── Positive-value constraints ───────────────────────────

    def test_negative_sale_approval_threshold_rejected(self):
        """sale_approval_threshold < 0 raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.config.sale_approval_threshold = -1.0

    def test_negative_invoice_overdue_days_rejected(self):
        """invoice_overdue_days < 0 raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.config.invoice_overdue_days = -5

    def test_negative_contract_alert_days_rejected(self):
        """contract_alert_days_before < 0 raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.config.contract_alert_days_before = -10

    def test_negative_stock_threshold_rejected(self):
        """stock_threshold_default < 0 raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.config.stock_threshold_default = -0.5

    def test_zero_values_allowed(self):
        """Zero thresholds are valid (non-negative)."""
        self.config.write(
            {
                "sale_approval_threshold": 0.0,
                "invoice_overdue_days": 0,
                "contract_alert_days_before": 0,
                "stock_threshold_default": 0.0,
            }
        )
        self.assertEqual(self.config.sale_approval_threshold, 0.0)
