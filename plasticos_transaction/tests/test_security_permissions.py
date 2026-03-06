from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError


class TestSecurityPermissions(PlasticosTestCase):
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
                "name": "Test Partner Security",
                "property_account_receivable_id": self.account_receivable.id,
                "property_account_payable_id": self.account_payable.id,
            }
        )

        # Create a non-manager user for testing
        base_user_group = self.env.ref("base.group_user", raise_if_not_found=False)
        group_ids = [(6, 0, [base_user_group.id])] if base_user_group else []
        self.non_manager_user = self.env["res.users"].create(
            {
                "name": "Test Non-Manager User",
                "login": "test_non_manager_plasticos",
                "email": "nonmanager@test.plasticos.com",
                "group_ids": group_ids,
            }
        )

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

    def test_only_manager_can_close(self):
        """Test that non-manager users cannot close transactions."""
        invoice = self._create_posted_invoice()
        tx = self.env["plasticos.transaction"].create(
            {
                "customer_invoice_id": invoice.id,
            }
        )
        tx.action_activate()

        # Attempt to close as non-manager should fail
        with self.assertRaises(UserError):
            tx.with_user(self.non_manager_user).action_close()
