"""Contract tests for bridge model wiring.

Bridge models use _inherit to add fields/methods to core models.
These tests verify that the bridges are properly installed and
the fields they add are present on the target models.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "contract")
class TestIntakeBridgeWiring(TransactionCase):
    """Verify all intake bridge fields are actually installed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fields = cls.env["plasticos.intake"]._fields

    def test_normalizer_fields_present(self):
        """plasticos_intake_normalizer adds these via intake_normalizer.py."""
        normalizer_fields = [
            "normalized",
            "normalized_date",
            "normalizer_config_id",
        ]
        for fname in normalizer_fields:
            self.assertIn(
                fname,
                self.fields,
                f"Normalizer bridge field missing: {fname}. " f"Is plasticos_intake_normalizer installed?",
            )

    def test_geo_fields_present(self):
        """plasticos_geolocalize adds lat/lon via intake_geo.py."""
        # lat and lon are defined on base intake, but geo module may add more
        self.assertIn("lat", self.fields)
        self.assertIn("lon", self.fields)

    def test_offer_bridge_fields_present(self):
        """plasticos_offer adds offer_ids via intake_offers_bridge.py."""
        self.assertIn(
            "offer_ids",
            self.fields,
            "offer_ids missing — is plasticos_offer installed?",
        )

    def test_match_engine_fields_present(self):
        """plasticos_buyer_match_engine adds fields via intake_extension.py."""
        engine_fields = ["match_status"]
        for fname in engine_fields:
            self.assertIn(
                fname,
                self.fields,
                f"Match engine field missing: {fname}. " f"Is plasticos_buyer_match_engine installed?",
            )


@tagged("post_install", "-at_install", "contract")
class TestTransactionBridgeWiring(TransactionCase):
    """Verify all transaction bridge fields are installed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fields = cls.env["plasticos.transaction"]._fields

    def test_claims_bridge_fields(self):
        """plasticos_claims adds claim_ids via transaction_claims_bridge.py."""
        self.assertIn(
            "claim_ids",
            self.fields,
            "claim_ids missing — is plasticos_claims installed?",
        )

    def test_logistics_bridge_fields(self):
        """plasticos_logistics adds load_ids via transaction_inherit.py."""
        self.assertIn(
            "load_ids",
            self.fields,
            "load_ids missing — is plasticos_logistics installed?",
        )

    def test_documents_bridge_fields(self):
        """plasticos_documents adds document fields."""
        for fname in ("document_ids", "document_count"):
            self.assertIn(
                fname,
                self.fields,
                f"Document bridge field missing: {fname}. " f"Is plasticos_documents installed?",
            )
