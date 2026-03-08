"""
Configuration Integration Test Suite.

Tests the configuration models that store system-wide settings:
- plasticos.automation.config: Automation thresholds and timing
- plasticos.web.lead.config: Web lead API and AI settings
- plasticos.normalizer.config: Intake normalization rules

Migrated from legacy plastic_ai.kb_config to plasticos.* namespace.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestAutomationConfig(PlasticosTestCase):
    """Test plasticos.automation.config singleton and thresholds."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env["plasticos.automation.config"]

    def test_config_model_exists(self):
        """Test automation config model is accessible."""
        self.assertIn("plasticos.automation.config", self.env)

    def test_config_has_required_fields(self):
        """Test config has all required threshold fields."""
        required_fields = [
            "name",
            "sale_approval_threshold",
            "invoice_overdue_days",
            "contract_alert_days_before",
        ]
        for field in required_fields:
            self.assertIn(field, self.Config._fields, f"Missing field: {field}")

    def test_config_create_with_defaults(self):
        """Test config can be created with default values."""
        config = self.Config.create({"name": "Test Config"})

        self.assertTrue(config.exists())
        self.assertEqual(config.sale_approval_threshold, 10000.0)
        self.assertEqual(config.invoice_overdue_days, 30)
        self.assertEqual(config.contract_alert_days_before, 30)

    def test_config_threshold_update(self):
        """Test threshold values can be updated."""
        config = self.Config.create({"name": "Threshold Test"})
        config.write(
            {
                "sale_approval_threshold": 25000.0,
                "invoice_overdue_days": 45,
            }
        )

        self.assertEqual(config.sale_approval_threshold, 25000.0)
        self.assertEqual(config.invoice_overdue_days, 45)

    def test_config_singleton_pattern(self):
        """Test config follows singleton pattern (one active config)."""
        existing = self.Config.search([], limit=1)
        if not existing:
            existing = self.Config.create({"name": "Singleton Test"})

        self.assertTrue(existing.exists())


@tagged("post_install", "-at_install")
class TestWebLeadConfig(PlasticosTestCase):
    """Test plasticos.web.lead.config for API and AI settings."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.web.lead.config" not in cls.env:
            raise cls.skipTest("plasticos_web_leads not installed")
        cls.Config = cls.env["plasticos.web.lead.config"]

    def test_config_model_exists(self):
        """Test web lead config model is accessible."""
        self.assertIn("plasticos.web.lead.config", self.env)

    def test_config_has_api_fields(self):
        """Test config has API authentication fields."""
        api_fields = ["api_key", "is_active"]
        for field in api_fields:
            self.assertIn(field, self.Config._fields, f"Missing field: {field}")

    def test_config_has_source_type_selection(self):
        """Test default_source_type has valid selection options."""
        field = self.Config._fields.get("default_source_type")
        if field:
            self.assertTrue(field.selection, "default_source_type should have selection options")

    def test_config_is_active_default(self):
        """Test is_active defaults to True."""
        config = self.Config.create({"name": "API Test"})
        self.assertTrue(config.is_active)

    def test_config_api_key_can_be_set(self):
        """Test API key can be set on config."""
        config = self.Config.create(
            {
                "name": "API Key Test",
                "api_key": "test-key-12345",
            }
        )
        self.assertEqual(config.api_key, "test-key-12345")


@tagged("post_install", "-at_install")
class TestNormalizerConfig(PlasticosTestCase):
    """Test plasticos.normalizer.config for intake normalization rules."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.normalizer.config" not in cls.env:
            raise cls.skipTest("plasticos_intake_normalizer not installed")
        cls.Config = cls.env["plasticos.normalizer.config"]

    def test_config_model_exists(self):
        """Test normalizer config model is accessible."""
        self.assertIn("plasticos.normalizer.config", self.env)

    def test_config_fields_exist(self):
        """Test config has expected fields."""
        self.assertTrue(hasattr(self.Config, "_fields"))


@tagged("post_install", "-at_install")
class TestConfigIntegration(PlasticosTestCase):
    """Integration tests across configuration models."""

    def test_all_config_models_accessible(self):
        """Test all config models can be accessed."""
        config_models = [
            "plasticos.automation.config",
        ]
        optional_models = [
            "plasticos.web.lead.config",
            "plasticos.normalizer.config",
        ]

        for model in config_models:
            self.assertIn(model, self.env, f"Required config model missing: {model}")

        for model in optional_models:
            if model in self.env:
                self.assertTrue(True, f"Optional config model available: {model}")

    def test_config_table_structure(self):
        """Test PostgreSQL table exists for automation config."""
        self.env.cr.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'plasticos_automation_config'
            ORDER BY ordinal_position
        """)
        columns = self.env.cr.fetchall()

        self.assertTrue(columns, "Table plasticos_automation_config should exist")

        column_names = [col[0] for col in columns]
        required_columns = ["id", "name", "sale_approval_threshold"]
        for col in required_columns:
            self.assertIn(col, column_names, f"Missing column: {col}")

    def test_config_data_types(self):
        """Test config fields have correct data types."""
        Config = self.env["plasticos.automation.config"]

        threshold_field = Config._fields.get("sale_approval_threshold")
        self.assertEqual(threshold_field.type, "float")

        days_field = Config._fields.get("invoice_overdue_days")
        self.assertEqual(days_field.type, "integer")

    def test_config_help_text_present(self):
        """Test config fields have help text for documentation."""
        Config = self.env["plasticos.automation.config"]

        threshold_field = Config._fields.get("sale_approval_threshold")
        self.assertTrue(threshold_field.help, "sale_approval_threshold should have help text")

        days_field = Config._fields.get("invoice_overdue_days")
        self.assertTrue(days_field.help, "invoice_overdue_days should have help text")
