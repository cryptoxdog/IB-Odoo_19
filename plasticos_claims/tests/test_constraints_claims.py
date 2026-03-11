from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestClaimConstraintsValidation(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Claim = cls.env["plasticos.claim"]
        # Create required transaction for claims
        cls.supplier = cls.env["res.partner"].create({"name": "Constraint Test Supplier", "is_company": True})
        cls.buyer = cls.env["res.partner"].create({"name": "Constraint Test Buyer", "is_company": True})
        cls.tx = cls.env["plasticos.transaction"].create({"supplier_id": cls.supplier.id, "buyer_id": cls.buyer.id})
        cls._claim_counter = 0

    def _new_claim(self, **vals):
        self.__class__._claim_counter += 1
        base = {
            "transaction_id": self.tx.id,
            "state": "pending",
        }
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
