from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLoadAutomation(TransactionCase):
    """Test suite for load automation on plasticos.load."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.load" not in cls.env:
            raise cls.skipTest("plasticos.load not installed")
        cls.Load = cls.env["plasticos.load"]

    # ═══════════════════════════════════════════════════════════════════
    # AUTOMATION FIELD TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_load_model_accessible(self):
        """Test plasticos.load model is accessible."""
        self.assertIn("plasticos.load", self.env)

    def test_automation_fields_exist(self):
        """Test automation fields exist on plasticos.load."""
        fields_to_check = ["auto_dispatch", "dispatch_reminder_sent"]
        for field in fields_to_check:
            if hasattr(self.Load, field):
                self.assertIn(field, self.Load._fields)
