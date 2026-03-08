from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosIntakeMatch(PlasticosTestCase):
    """Test suite for plasticos.intake.match"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO: Setup test data

    def _create_match(self, **kwargs):
        """Helper to create plasticos.intake.match with defaults"""
        vals = {
            # TODO: Add required fields
        }
        vals.update(kwargs)
        return self.env["plasticos.intake.match"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_match()

        self.assertTrue(record.exists())
        # TODO: Add specific assertions

    def test_constraint_intake_id_required(self):
        """Test intake_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.intake.match"].create(
                {
                    # TODO: Add other required fields except intake_id
                }
            )

    def test_constraint_buyer_id_required(self):
        """Test buyer_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.intake.match"].create(
                {
                    # TODO: Add other required fields except buyer_id
                }
            )
