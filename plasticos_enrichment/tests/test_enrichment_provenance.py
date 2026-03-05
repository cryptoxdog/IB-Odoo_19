from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPlasticosEnrichmentProvenance(TransactionCase):
    """Test suite for plasticos.enrichment.provenance"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # TODO: Setup test data

    def _create_provenance(self, **kwargs):
        """Helper to create plasticos.enrichment.provenance with defaults"""
        vals = {
            # TODO: Add required fields
        }
        vals.update(kwargs)
        return self.env["plasticos.enrichment.provenance"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_basic(self):
        """Test basic record creation"""
        record = self._create_provenance()

        self.assertTrue(record.exists())
        # TODO: Add specific assertions

    def test_constraint_run_id_required(self):
        """Test run_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.enrichment.provenance"].create(
                {
                    # TODO: Add other required fields except run_id
                }
            )

    def test_constraint_partner_id_required(self):
        """Test partner_id is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.enrichment.provenance"].create(
                {
                    # TODO: Add other required fields except partner_id
                }
            )

    def test_constraint_target_model_required(self):
        """Test target_model is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.enrichment.provenance"].create(
                {
                    # TODO: Add other required fields except target_model
                }
            )

    def test_constraint_target_field_required(self):
        """Test target_field is required"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.enrichment.provenance"].create(
                {
                    # TODO: Add other required fields except target_field
                }
            )
