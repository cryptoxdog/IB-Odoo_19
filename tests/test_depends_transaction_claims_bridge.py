from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestTransactionClaimsBridgeDepends(PlasticosTestCase):
    """Bridge model computations between transactions and claims."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Bridge = cls.env["plasticos.transaction.claim"]
        cls.Transaction = cls.env["plasticos.transaction"]
        cls.Claim = cls.env["plasticos.claim"]

        cls.partner = cls.env["res.partner"].create({"name": "Bridge Partner"})
        cls.tx = cls.Transaction.create(
            {
                "name": "TX-BRIDGE",
                "partner_id": cls.partner.id,
                "revenue_total": 1000.0,
                "purchase_cost_total": 600.0,
            }
        )
        cls.claim = cls.Claim.create(
            {
                "name": "CLM-BRIDGE",
                "partner_id": cls.partner.id,
                "claim_amount": 200.0,
            }
        )

    def test_claim_percent_of_revenue(self):
        bridge = self.Bridge.create(
            {
                "transaction_id": self.tx.id,
                "claim_id": self.claim.id,
            }
        )
        self.assertAlmostEqual(bridge.claim_pct_of_revenue, 20.0)

    def test_residual_margin_after_claim(self):
        bridge = self.Bridge.create(
            {
                "transaction_id": self.tx.id,
                "claim_id": self.claim.id,
            }
        )
        self.assertLess(bridge.residual_margin, self.tx.gross_margin)
