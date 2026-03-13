import uuid

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install", "-standard", "disabled")
class TestPlasticosCommissionRuleBridge(PlasticosTestCase):
    """Test suite for plasticos.commission.rule"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_sales_rep = cls.env["res.users"].create(
            {
                "name": "Test Sales Rep Bridge",
                "login": f"test_sales_rep_bridge_{uuid.uuid4().hex[:6]}",
            }
        )

    def _create_rule(self, **kwargs):
        """Helper to create plasticos.commission.rule with defaults"""
        vals = {
            "name": f"Test Rule {uuid.uuid4().hex[:6]}",
            "sales_rep_id": self.test_sales_rep.id,
            "percentage": 0.05,
        }
        vals.update(kwargs)
        return self.env["plasticos.commission.rule"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_rule()

        self.assertTrue(record.exists())
        self.assertTrue(record.name)
        self.assertTrue(record.sales_rep_id)
        self.assertGreaterEqual(record.percentage, 0.0)

    def test_constraint_name_required(self):
        """Test name is required (explicitly pass False to override default)"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.commission.rule"].create(
                {
                    "name": False,
                    "sales_rep_id": self.test_sales_rep.id,
                    "percentage": 0.05,
                }
            )

    def test_constraint_sales_rep_id_required(self):
        """Test sales_rep_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.commission.rule"].create(
                {
                    "name": "No Sales Rep Rule",
                    "sales_rep_id": False,  # Explicitly pass False to test constraint
                    "percentage": 0.05,
                }
            )
