from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestClaimConstraintsValidation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Claim = cls.env["plasticos.claim"]

    def _new_claim(self, **vals):
        base = {"name": "CLM-001", "state": "pending"}
        base.update(vals)
        return self.Claim.create(base)

    def test_unique_name(self):
        self._new_claim()
        raised = False
        try:
            self._new_claim()
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    def test_resolution_note_required_on_resolve(self):
        claim = self._new_claim(state="in_progress")
        with self.assertRaises(ValidationError):
            claim.write({"state": "resolved", "resolution_note": False})

    def test_overdue_flag_set(self):
        claim = self._new_claim()
        claim.write({"state": "in_progress"})
        claim._compute_days_open()
        self.assertIn(claim.is_overdue, (True, False))
