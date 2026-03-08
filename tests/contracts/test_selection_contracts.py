"""Contract tests for selection field values across PlastOS models.

When modules depend on specific selection values for state machines,
domain filters, or business logic, those values become part of the
contract. This file validates them all in one place.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


def _get_selection_values(model, field_name):
    """Extract selection keys from a model field."""
    field = model._fields.get(field_name)
    if not field or field.type != "selection":
        return []
    sel = field.selection
    if callable(sel):
        # Dynamic selection — can't validate statically
        return None
    return [s[0] for s in sel]


@tagged("post_install", "-at_install", "contract")
class TestIntakeStatusValues(PlasticosTestCase):
    def test_intake_status_complete(self):
        values = _get_selection_values(self.env["plasticos.intake"], "status")
        self.assertIsNotNone(values)
        required = ["draft", "matched", "offer_sent", "processing", "won", "lost", "expired"]
        for v in required:
            self.assertIn(v, values, f"Intake missing status: {v}")

    def test_intake_deal_type_values(self):
        values = _get_selection_values(self.env["plasticos.intake"], "deal_type")
        self.assertIsNotNone(values)
        for v in ("spot", "contract", "recurring"):
            self.assertIn(v, values)

    def test_intake_origin_sector_values(self):
        values = _get_selection_values(self.env["plasticos.intake"], "origin_sector")
        self.assertIsNotNone(values)
        for v in ("automotive", "food", "industrial", "packaging"):
            self.assertIn(v, values)


@tagged("post_install", "-at_install", "contract")
class TestClaimStateValues(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.Claim = cls.env["plasticos.claim"]
            cls.skip = False
        except KeyError:
            cls.skip = True

    def test_claim_state_values(self):
        if self.skip:
            self.skipTest("plasticos_claims not installed")
        values = _get_selection_values(self.Claim, "state")
        self.assertIsNotNone(values, "claim.state must be a selection field")
        # Verify minimum expected states
        for v in ("draft", "open", "closed"):
            self.assertIn(v, values, f"Claim missing state: {v}")


@tagged("post_install", "-at_install", "contract")
class TestLoadStateValues(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.Load = cls.env["plasticos.load"]
            cls.skip = False
        except KeyError:
            cls.skip = True

    def test_load_state_values(self):
        if self.skip:
            self.skipTest("plasticos_logistics not installed")
        values = _get_selection_values(self.Load, "state")
        self.assertIsNotNone(values)
        for v in ("draft", "scheduled", "in_transit", "delivered"):
            self.assertIn(v, values, f"Load missing state: {v}")


@tagged("post_install", "-at_install", "contract")
class TestOfferStateValues(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.Offer = cls.env["plasticos.offer"]
            cls.skip = False
        except KeyError:
            cls.skip = True

    def test_offer_state_values(self):
        if self.skip:
            self.skipTest("plasticos_offer not installed")
        values = _get_selection_values(self.Offer, "state")
        self.assertIsNotNone(values)
        for v in ("draft", "sent", "accepted", "rejected"):
            self.assertIn(v, values, f"Offer missing state: {v}")
