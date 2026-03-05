from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestClaimDepends(TransactionCase):
    """@api.depends fields on plasticos.claim."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Claim = cls.env["plasticos.claim"]
        cls.partner = cls.env["res.partner"].create({"name": "Claim Partner"})

    def _claim(self, **vals):
        base = {
            "name": "CLM-DEPS",
            "partner_id": self.partner.id,
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
        claim = self._claim(claim_amount=1000.0, recovered_amount=400.0)
        self.assertAlmostEqual(claim.recovery_rate, 40.0)
        claim.write({"recovered_amount": 1000.0})
        self.assertAlmostEqual(claim.recovery_rate, 100.0)

    def test_related_partner_fields(self):
        claim = self._claim()
        self.assertTrue(claim.partner_name)
