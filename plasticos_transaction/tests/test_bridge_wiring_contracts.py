"""Contract tests for bridge model wiring.

Bridge models use _inherit to add fields/methods to core models.
These tests verify that the bridges are properly installed and
the fields they add are present on the target models.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "contract")
class TestIntakeBridgeWiring(PlasticosTestCase):
    """Verify all intake bridge fields are actually installed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fields = cls.env["plasticos.intake"]._fields

    def test_normalizer_fields_present(self):
        """plasticos_intake_normalizer adds these via intake_normalizer.py.

        match_status was previously contributed by plasticos_buyer_match_engine's
        intake_extension.py; that module was retired in M7 / TASK-051 and the
        normalizer now owns the field.

        The normalizer stamps its last run on normalization_ts (not normalized_date) and reads one
        global plasticos.normalizer.config via get_config() instead of a per-intake config link
        (plasticos_intake_normalizer/models/intake_normalizer.py:30-63, 72).
        """
        normalizer_fields = [
            "normalized",
            "normalization_ts",
            "match_status",
        ]
        for fname in normalizer_fields:
            self.assertIn(
                fname,
                self.fields,
                f"Normalizer bridge field missing: {fname}. Is plasticos_intake_normalizer installed?",
            )
        self.assertEqual(self.fields["normalization_ts"].type, "datetime")
        self.assertTrue(callable(getattr(self.env["plasticos.normalizer.config"], "get_config", None)))

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


@tagged("post_install", "-at_install", "contract")
class TestTransactionBridgeWiring(PlasticosTestCase):
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
        """plasticos_logistics adds load_ids. Each load stores its own transaction_id."""
        self.assertNotIn("load_id", self.fields)
        self.assertIn("load_ids", self.fields)
        self.assertEqual(self.fields["load_ids"].type, "one2many")
        self.assertEqual(self.fields["load_ids"].comodel_name, "plasticos.load")
        self.assertEqual(self.fields["load_ids"].inverse_name, "transaction_id")
        self.assertIn("load_count", self.fields)

    def test_documents_bridge_fields(self):
        """plasticos_documents adds document fields."""
        for fname in ("document_ids", "document_count"):
            self.assertIn(
                fname,
                self.fields,
                f"Document bridge field missing: {fname}. Is plasticos_documents installed?",
            )
