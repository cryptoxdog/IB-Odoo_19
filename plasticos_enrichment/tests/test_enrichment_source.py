from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPlasticosEnrichmentSource(TransactionCase):
    """Test suite for plasticos.enrichment.source"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO: Setup test data

    def _create_source(self, **kwargs):
        """Helper to create plasticos.enrichment.source with defaults"""
        vals = {
            # TODO: Add required fields
        }
        vals.update(kwargs)
        return self.env["plasticos.enrichment.source"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_source()

        self.assertTrue(record.exists())
        # TODO: Add specific assertions

    def test_constraint_partner_id_required(self):
        """Test partner_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.enrichment.source"].create(
                {
                    # TODO: Add other required fields except partner_id
                }
            )

    def test_constraint_source_type_required(self):
        """Test source_type is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.enrichment.source"].create(
                {
                    # TODO: Add other required fields except source_type
                }
            )

    def test_constraint_url_required(self):
        """Test url is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.enrichment.source"].create(
                {
                    # TODO: Add other required fields except url
                }
            )
