from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPlasticosPackagingType(TransactionCase):
    """Test suite for plasticos.packaging.type"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO: Setup test data

    def _create_type(self, **kwargs):
        """Helper to create plasticos.packaging.type with defaults"""
        vals = {
            # TODO: Add required fields
        }
        vals.update(kwargs)
        return self.env["plasticos.packaging.type"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_type()

        self.assertTrue(record.exists())
        # TODO: Add specific assertions

    def test_constraint_name_required(self):
        """Test name is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.packaging.type"].create(
                {
                    # TODO: Add other required fields except name
                }
            )

    def test_constraint_code_required(self):
        """Test code is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.packaging.type"].create(
                {
                    # TODO: Add other required fields except code
                }
            )
