from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPlasticosTransactionLine(TransactionCase):
    """Test suite for plasticos.transaction.line"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO: Setup test data

    def _create_line(self, **kwargs):
        """Helper to create plasticos.transaction.line with defaults"""
        vals = {
            # TODO: Add required fields
        }
        vals.update(kwargs)
        return self.env["plasticos.transaction.line"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_line()

        self.assertTrue(record.exists())
        # TODO: Add specific assertions

    def test_constraint_transaction_id_required(self):
        """Test transaction_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.transaction.line"].create(
                {
                    # TODO: Add other required fields except transaction_id
                }
            )
