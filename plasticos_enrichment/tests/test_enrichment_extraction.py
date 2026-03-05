from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPlasticosEnrichmentExtraction(TransactionCase):
    """Test suite for plasticos.enrichment.extraction"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO: Setup test data

    def _create_extraction(self, **kwargs):
        """Helper to create plasticos.enrichment.extraction with defaults"""
        vals = {
            # TODO: Add required fields
        }
        vals.update(kwargs)
        return self.env["plasticos.enrichment.extraction"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_extraction()

        self.assertTrue(record.exists())
        # TODO: Add specific assertions

    def test_constraint_run_id_required(self):
        """Test run_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.enrichment.extraction"].create(
                {
                    # TODO: Add other required fields except run_id
                }
            )

    def test_constraint_source_id_required(self):
        """Test source_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.enrichment.extraction"].create(
                {
                    # TODO: Add other required fields except source_id
                }
            )
