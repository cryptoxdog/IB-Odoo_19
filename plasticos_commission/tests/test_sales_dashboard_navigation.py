"""F-010 / DEC-003: a dashboard row opens its transaction only where record rules allow.

Navigation never widens access: the button is computed from the user's own read
access to the transaction, and the action re-checks it server-side.
"""

from __future__ import annotations

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSalesDashboardTransactionNavigation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        rep_group = cls.env.ref("plasticos_security_base.group_sales_rep")
        ops_group = cls.env.ref("plasticos_security_base.group_operations_manager")
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.owner = Users.create(
            {"name": "Nav Owner Rep", "login": "f010_nav_owner", "group_ids": [Command.set([rep_group.id])]}
        )
        # Sees every dashboard row through the manager rule, but reads only own
        # transactions through the sales-rep transaction rule.
        cls.other = Users.create(
            {
                "name": "Nav Other Rep",
                "login": "f010_nav_other",
                "group_ids": [Command.set([rep_group.id, ops_group.id])],
            }
        )
        cls.tx = cls.env["plasticos.transaction"].create({"user_id": cls.owner.id})
        cls.env.flush_all()

    def _row(self, user):
        rows = self.env["plasticos.sales.dashboard"].with_user(user).search([("transaction_id", "=", self.tx.id)])
        self.assertEqual(len(rows), 1)
        return rows

    def test_owner_opens_the_transaction(self):
        row = self._row(self.owner)
        self.assertTrue(row.can_open_transaction)
        action = row.action_view_transaction()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "plasticos.transaction")
        self.assertEqual(action["res_id"], self.tx.id)

    def test_non_owner_has_no_button_and_cannot_open(self):
        self.assertFalse(self.tx.with_user(self.other).has_access("read"))
        row = self._row(self.other)
        self.assertFalse(row.can_open_transaction)
        with self.assertRaises(AccessError):
            row.action_view_transaction()
