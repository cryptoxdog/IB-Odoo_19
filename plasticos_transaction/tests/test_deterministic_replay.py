import hashlib

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase


class TestDeterministicReplay(PlasticosTestCase):
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
        self.env["account.journal"].create(
            [
                {"name": "Sale Journal", "code": "SALE", "type": "sale"},
                {"name": "Purchase Journal", "code": "PUR", "type": "purchase"},
            ]
        )
        self.account_income = self._get_or_create_account("400000", "Income", "income")
        self.account_expense = self._get_or_create_account("600000", "Expense", "expense")
        self.account_receivable = self._get_or_create_account("120000", "Receivable", "asset_receivable", True)
        self.account_payable = self._get_or_create_account("210000", "Payable", "liability_payable", True)

        # Create a manager user and switch to it
        group_manager = self.env.ref("plasticos_transaction.group_plasticos_manager", raise_if_not_found=False)
        group_user = self.env.ref("base.group_user", raise_if_not_found=False)
        group_sale_manager = self.env.ref("sales_team.group_sale_manager", raise_if_not_found=False)
        group_account_manager = self.env.ref("account.group_account_manager", raise_if_not_found=False)

        groups = [g.id for g in [group_manager, group_user, group_sale_manager, group_account_manager] if g]
        # Optional: add documents group if module is installed
        group_documents_user = self.env.ref("plasticos_documents.group_documents_user", raise_if_not_found=False)
        if group_documents_user:
            groups.append(group_documents_user.id)

        self.manager_user = self.env["res.users"].create(
            {
                "name": "Plasticos Manager",
                "login": "plasticos_manager_test",
                "email": "manager@example.com",
                "group_ids": [(6, 0, groups)],
            }
        )
        self.env = self.env(user=self.manager_user)

    def _snapshot_hash(self, tx):
        payload = (
            tx.revenue_total,
            tx.cost_total,
            tx.gross_margin,
            tx.commission_amount,
            tx.net_margin,
            tx.commission_locked,
        )
        return hashlib.sha256(str(payload).encode()).hexdigest()

    def _build_transaction(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "property_account_receivable_id": self.account_receivable.id,
                "property_account_payable_id": self.account_payable.id,
            }
        )
        so = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
            }
        )

        tx = self.env["plasticos.transaction"].create(
            {
                "sale_order_id": so.id,
            }
        )

        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": so.partner_id.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Revenue",
                            "quantity": 1,
                            "price_unit": 1000,
                            "account_id": self.account_income.id,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        tx.customer_invoice_id = invoice.id

        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": so.partner_id.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Cost",
                            "quantity": 1,
                            "price_unit": 600,
                            "account_id": self.account_expense.id,
                        },
                    )
                ],
            }
        )
        bill.action_post()
        tx.vendor_bill_ids = [(4, bill.id)]

        tx.action_activate()
        tx.action_close()

        return tx

    def test_replay_is_deterministic(self):
        self.env.flush_all()
        self.env.cr.execute("SAVEPOINT replay_start")

        tx1 = self._build_transaction()
        h1 = self._snapshot_hash(tx1)

        self.env.cr.execute("ROLLBACK TO SAVEPOINT replay_start")
        self.env.invalidate_all()

        tx2 = self._build_transaction()
        h2 = self._snapshot_hash(tx2)

        self.assertEqual(h1, h2)
