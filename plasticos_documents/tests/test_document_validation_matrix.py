from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPlasticosDocumentValidationMatrix(TransactionCase):
    """Test suite for plasticos.document.validation.matrix"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO: Setup test data

    def _create_matrix(self, **kwargs):
        """Helper to create plasticos.document.validation.matrix with defaults"""
        vals = {
            # TODO: Add required fields
        }
        vals.update(kwargs)
        return self.env["plasticos.document.validation.matrix"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_matrix()

        self.assertTrue(record.exists())
        # TODO: Add specific assertions

    def test_constraint_name_required(self):
        """Test name is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document.validation.matrix"].create(
                {
                    # TODO: Add other required fields except name
                }
            )

    def test_constraint_doc_category_required(self):
        """Test doc_category is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document.validation.matrix"].create(
                {
                    # TODO: Add other required fields except doc_category
                }
            )

    def test_constraint_tag_id_required(self):
        """Test tag_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document.validation.matrix"].create(
                {
                    # TODO: Add other required fields except tag_id
                }
            )
