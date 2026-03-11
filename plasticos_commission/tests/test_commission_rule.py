import uuid

from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosCommissionRule(PlasticosTestCase):
    """Test suite for plasticos.commission.rule"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CommissionRule = cls.env["plasticos.commission.rule"]
        cls.test_sales_rep = cls.env["res.users"].create(
            {
                "name": "Test Sales Rep CR",
                "login": f"test_sales_rep_cr_{uuid.uuid4().hex[:6]}",
            }
        )

    def _create_sales_rep(self, suffix=""):
        """Helper: create a unique sales rep for testing."""
        unique = uuid.uuid4().hex[:6]
        return self.env["res.users"].create(
            {
                "name": f"Test Rep {suffix}{unique}",
                "login": f"test_rep_{suffix}{unique}",
            }
        )

    def _create_rule(self, **kwargs):
        """Helper to create plasticos.commission.rule with defaults"""
        vals = {
            "name": f"Test Rule {uuid.uuid4().hex[:6]}",
            "sales_rep_id": kwargs.pop("sales_rep_id", self.test_sales_rep.id),
            "percentage": kwargs.pop("percentage", 0.05),
        }
        vals.update(kwargs)
        return self.CommissionRule.create(vals)

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
        """Test name is required"""
        raised = False
        try:
            self.CommissionRule.create(
                {
                    "sales_rep_id": self.test_sales_rep.id,
                    "percentage": 0.05,
                }
            )
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    def test_constraint_sales_rep_id_required(self):
        """Test sales_rep_id is required"""
        raised = False
        try:
            self.CommissionRule.create(
                {
                    "name": "No Sales Rep Rule",
                    "percentage": 0.05,
                }
            )
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")
