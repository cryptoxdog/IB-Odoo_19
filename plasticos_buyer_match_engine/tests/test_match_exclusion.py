from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosMatchExclusion(PlasticosTestCase):
    """Test suite for plasticos.match.exclusion"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO: Setup test data

    def _create_exclusion(self, **kwargs):
        """Helper to create plasticos.match.exclusion with defaults"""
        vals = {
            # TODO: Add required fields
        }
        vals.update(kwargs)
        return self.env["plasticos.match.exclusion"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_exclusion()

        self.assertTrue(record.exists())
        # TODO: Add specific assertions

    def test_constraint_supplier_partner_id_required(self):
        """Test supplier_partner_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.match.exclusion"].create(
                {
                    # TODO: Add other required fields except supplier_partner_id
                }
            )

    def test_constraint_buyer_partner_id_required(self):
        """Test buyer_partner_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.match.exclusion"].create(
                {
                    # TODO: Add other required fields except buyer_partner_id
                }
            )

    def test_constraint_reason_required(self):
        """Test reason is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.match.exclusion"].create(
                {
                    # TODO: Add other required fields except reason
                }
            )

    def test_constraint_exclusion_type_required(self):
        """Test exclusion_type is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.match.exclusion"].create(
                {
                    # TODO: Add other required fields except exclusion_type
                }
            )
