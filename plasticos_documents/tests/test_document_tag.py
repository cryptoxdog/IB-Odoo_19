from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPlasticosDocumentTag(TransactionCase):
    """Test suite for plasticos.document.tag"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO: Setup test data

    def _create_tag(self, **kwargs):
        """Helper to create plasticos.document.tag with defaults"""
        vals = {
            # TODO: Add required fields
        }
        vals.update(kwargs)
        return self.env["plasticos.document.tag"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_tag()

        self.assertTrue(record.exists())
        # TODO: Add specific assertions

    def test_constraint_name_required(self):
        """Test name is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document.tag"].create(
                {
                    # TODO: Add other required fields except name
                }
            )

    def test_constraint_code_required(self):
        """Test code is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document.tag"].create(
                {
                    # TODO: Add other required fields except code
                }
            )
