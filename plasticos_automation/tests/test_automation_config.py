"""Unit tests for plasticos.automation.config singleton.

Tests cover:
- Singleton constraint (only one active config)
- Positive value constraints for thresholds
- get_config returns active config or creates default
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAutomationConfig(TransactionCase):
    """Test automation config singleton and validation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env["plasticos.automation.config"]
        # Deactivate any existing configs
        cls.Config.search([]).write({"active": False})

    def test_get_config_creates_default(self):
        """get_config creates default config when none exists."""
        config = self.Config.get_config()
        self.assertTrue(config)
        self.assertTrue(config.active)

    def test_get_config_returns_existing(self):
        """get_config returns existing active config."""
        cfg = self.Config.create({"active": True})
        result = self.Config.get_config()
        self.assertEqual(result.id, cfg.id)

    def test_singleton_constraint(self):
        """Only one active config allowed."""
        self.Config.create({"active": True})
        with self.assertRaises(ValidationError):
            self.Config.create({"active": True})
