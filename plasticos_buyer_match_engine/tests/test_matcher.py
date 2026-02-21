from odoo.tests.common import TransactionCase


class TestBuyerMatcher(TransactionCase):
    """Test suite for the deterministic buyer match engine.

    Expand with fixture data once the module is deployed.
    """

    def test_matcher_import(self):
        """Verify the matcher service can be imported."""
        from ..services.matcher import PlasticosMatcher  # noqa: F401

        self.assertTrue(True)

    def test_capability_model_exists(self):
        """Verify the buyer.capability model is registered."""
        self.assertIn(
            "plasticos.buyer.capability",
            self.env,
        )

    def test_capability_create(self):
        """Verify a capability record can be created (requires fixture data)."""
        # Placeholder — expand when test fixtures are available
        self.assertTrue(True)
