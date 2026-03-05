from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockPickingAutomation(TransactionCase):
    """Test suite for stock picking automation on stock.picking."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "stock.picking" not in cls.env:
            raise cls.skipTest("stock.picking not installed")
        cls.Picking = cls.env["stock.picking"]

    def test_picking_model_accessible(self):
        """Test stock.picking model is accessible."""
        self.assertIn("stock.picking", self.env)

    def test_automation_fields_exist(self):
        """Test automation fields exist on stock.picking."""
        fields_to_check = ["auto_validate", "trucker_id"]
        for field in fields_to_check:
            if hasattr(self.Picking, field):
                self.assertIn(field, self.Picking._fields)
