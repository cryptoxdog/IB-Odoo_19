from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPlasticosDocumentRule(TransactionCase):
    """Test suite for plasticos.document.rule"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO: Setup test data

    def _create_rule(self, **kwargs):
        """Helper to create plasticos.document.rule with defaults"""
        vals = {
            # TODO: Add required fields
        }
        vals.update(kwargs)
        return self.env["plasticos.document.rule"].create(vals)

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
            self.env["plasticos.document.rule"].create(
                {
                    # TODO: Add other required fields except name
                }
            )

    def test_constraint_tag_id_required(self):
        """Test tag_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document.rule"].create(
                {
                    # TODO: Add other required fields except tag_id
                }
            )

    def test_constraint_res_model_required(self):
        """Test res_model is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.document.rule"].create(
                {
                    # TODO: Add other required fields except res_model
                }
            )
