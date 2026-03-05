from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestCloseRace(TransactionCase):
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
                "name": "Test Partner Close Race",
                "property_account_receivable_id": self.account_receivable.id,
                "property_account_payable_id": self.account_payable.id,
            }
        )

        # Add user to manager group
        self.manager_group = self.env.ref("plasticos_transaction.group_plasticos_manager", raise_if_not_found=False)
        if self.manager_group:
            self.env.user.group_ids = [(4, self.manager_group.id)]

    def _create_posted_invoice(self):
        """Create a posted customer invoice for testing."""
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test Product",
                            "quantity": 1,
                            "price_unit": 100.0,
                            "account_id": self.account_income.id,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def test_double_close_attempt(self):
        """Test that closing an already-closed transaction raises UserError."""
        invoice = self._create_posted_invoice()
        tx = self.env["plasticos.transaction"].create(
            {
                "customer_invoice_id": invoice.id,
            }
        )
        tx.action_activate()
        tx.action_close()
        with self.assertRaises(UserError):
            tx.action_close()
