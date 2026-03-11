from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestClaimDepends(PlasticosTestCase):
    """@api.depends fields on plasticos.claim."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Claim = cls.env["plasticos.claim"]
        cls.supplier = cls.env["res.partner"].create({"name": "Depends Test Supplier", "is_company": True})
        cls.buyer = cls.env["res.partner"].create({"name": "Depends Test Buyer", "is_company": True})
        cls.tx = cls.env["plasticos.transaction"].create({"supplier_id": cls.supplier.id, "buyer_id": cls.buyer.id})

    def _claim(self, **vals):
        base = {
            "transaction_id": self.tx.id,
            "state": "pending",
        }
        base.update(vals)
        return self.Claim.create(base)

    def test_days_open_and_overdue_flag(self):
        claim = self._claim()
        claim._compute_days_open()
        self.assertGreaterEqual(claim.days_open, 0)
        self.assertIn(claim.is_overdue, (True, False))

    def test_recovery_rate_computed(self):
        claim = self._claim(claimed_amount=1000.0, recovery_amount=400.0)
        self.assertAlmostEqual(claim.recovery_rate, 40.0)
        claim.write({"recovery_amount": 1000.0})
        self.assertAlmostEqual(claim.recovery_rate, 100.0)

    def test_related_transaction_fields(self):
        """Test that related transaction fields are accessible."""
        claim = self._claim()
        self.assertEqual(claim.transaction_id, self.tx)
