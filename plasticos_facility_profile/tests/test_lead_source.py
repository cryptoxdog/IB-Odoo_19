from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPlasticosLeadSourceUtils(PlasticosTestCase):
    """Test suite for plasticos.lead.source.utils"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO: Setup test data

    def _create_utils(self, **kwargs):
        """Helper to create plasticos.lead.source.utils with defaults"""
        vals = {
            # TODO: Add required fields
        }
        vals.update(kwargs)
        return self.env["plasticos.lead.source.utils"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_utils()

        self.assertTrue(record.exists())
        # TODO: Add specific assertions
