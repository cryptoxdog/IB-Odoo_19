from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPlasticosPolymer(TransactionCase):
    """Test suite for plasticos.polymer"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO: Setup test data

    def _create_polymer(self, **kwargs):
        """Helper to create plasticos.polymer with defaults"""
        vals = {
            # TODO: Add required fields
        }
        vals.update(kwargs)
        return self.env["plasticos.polymer"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_polymer()

        self.assertTrue(record.exists())
        # TODO: Add specific assertions

    def test_constraint_name_required(self):
        """Test name is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.polymer"].create(
                {
                    # TODO: Add other required fields except name
                }
            )

    def test_constraint_code_required(self):
        """Test code is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.polymer"].create(
                {
                    # TODO: Add other required fields except code
                }
            )
