from odoo.tests.common import TransactionCase


class TestMultiCurrency(TransactionCase):
    def _get_or_create_account(self, code, name, account_type, reconcile=False):
        account = self.env["account.account"].search([("code", "=", code)], limit=1)
        if not account:
            account = self.env["account.account"].create(
                {
                    "name": name,
                    "code": code,
                    "account_type": account_type,
                    "reconcile": reconcile,
                }
            )
        return account

    def setUp(self):
        super().setUp()
        # Create journals
        self.env["account.journal"].search([("type", "=", "sale")]) or self.env["account.journal"].create(
            {"name": "Sale Journal", "code": "SALE", "type": "sale"}
        )

        # Create accounts
        self.account_income = self._get_or_create_account("400000", "Income", "income")
        self.account_receivable = self._get_or_create_account("120000", "Receivable", "asset_receivable", True)
        self.account_payable = self._get_or_create_account("210000", "Payable", "liability_payable", True)

        # Create test partner with proper accounts
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner Multi Currency",
                "property_account_receivable_id": self.account_receivable.id,
                "property_account_payable_id": self.account_payable.id,
            }
        )

    def test_margin_computation_multi_currency(self):
        """Test that margin computation works with non-default currency."""
        currency = self.env.ref("base.EUR")

        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "currency_id": currency.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test Product EUR",
                            "quantity": 1,
                            "price_unit": 500.0,
                            "account_id": self.account_income.id,
                        },
                    )
                ],
            }
        )

        tx = self.env["plasticos.transaction"].create(
            {
                "customer_invoice_id": invoice.id,
            }
        )

        self.assertIsNotNone(tx.gross_margin)
        self.assertEqual(tx.revenue_total, 500.0)
