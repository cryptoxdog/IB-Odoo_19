from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosCommissionRuleBridge(PlasticosTestCase):
    """Test suite for plasticos.commission.rule"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO: Setup test data

    def _create_rule(self, **kwargs):
        """Helper to create plasticos.commission.rule with defaults"""
        vals = {
            # TODO: Add required fields
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
        # TODO: Add specific assertions

    def test_constraint_name_required(self):
        """Test name is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.commission.rule"].create(
                {
                    # TODO: Add other required fields except name
                }
            )

    def test_constraint_sales_rep_id_required(self):
        """Test sales_rep_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.commission.rule"].create(
                {
                    # TODO: Add other required fields except sales_rep_id
                }
            )
