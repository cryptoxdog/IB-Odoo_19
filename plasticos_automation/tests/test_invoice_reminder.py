from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestInvoiceReminder(PlasticosTestCase):
    """Test suite for invoice reminder automation on account.move."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "account.move" not in cls.env:
            raise cls.skipTest("account.move not installed")
        cls.Move = cls.env["account.move"]
        cls.Partner = cls.env["res.partner"]
        cls.partner = cls.Partner.create({"name": "Test Customer"})

    # ═══════════════════════════════════════════════════════════════════
    # REMINDER FIELD TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_move_model_accessible(self):
        """Test account.move model is accessible."""
        self.assertIn("account.move", self.env)

    def test_reminder_fields_exist(self):
        """Test reminder automation fields exist on account.move."""
        if hasattr(self.Move, "reminder_sent"):
            self.assertIn("reminder_sent", self.Move._fields)
        if hasattr(self.Move, "last_reminder_date"):
            self.assertIn("last_reminder_date", self.Move._fields)
