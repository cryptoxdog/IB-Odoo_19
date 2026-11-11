from odoo.tests.common import TransactionCase, tagged

from ..services.rejection import response


@tagged("post_install", "-at_install", "broker_intelligence")
class TestRejectionSafety(TransactionCase):
    def test_unresolved_alias_cannot_create_business_fact(self):
        answer = response("R-01", None)
        self.assertTrue(answer["abstain"])
        self.assertIsNone(answer["proposed_code"])
        self.assertFalse(answer["automatic_exclusion"])

    def test_manual_classification_is_not_verified(self):
        self.assertFalse(response("No film wash this week", "NO_FILM_PROGRAM")["verified_classification"])
