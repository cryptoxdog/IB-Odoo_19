from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError


class TestConcurrency(PlasticosTestCase):
    def setUp(self):
        super().setUp()
        self.env["account.journal"].create(
            [
                {"name": "Sale Journal", "code": "SALE", "type": "sale"},
                {"name": "Purchase Journal", "code": "PUR", "type": "purchase"},
            ]
        )
        self.account_receivable = self.env["account.account"].create(
            {
                "name": "Receivable",
                "code": "120000",
                "account_type": "asset_receivable",
                "reconcile": True,
            }
        )
        self.account_payable = self.env["account.account"].create(
            {
                "name": "Payable",
                "code": "210000",
                "account_type": "liability_payable",
                "reconcile": True,
            }
        )

    def test_duplicate_vendor_bill_link(self):
        tx1 = self.env["plasticos.transaction"].create({})
        tx2 = self.env["plasticos.transaction"].create({})

        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "property_account_receivable_id": self.account_receivable.id,
                "property_account_payable_id": self.account_payable.id,
            }
        )
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
            }
        )

        tx1.vendor_bill_ids = [(4, bill.id)]

        with self.assertRaises(UserError):
            tx2.vendor_bill_ids = [(4, bill.id)]
