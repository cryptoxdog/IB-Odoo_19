"""GMP-NC-B: the dashboard payout lookup honours the rep payout record rule.

Every group that can read the sales dashboard can already read payouts, so the
lookup needs no elevation. Runs under ``odoo --test-enable --test-tags /plasticos_commission``.
"""

from __future__ import annotations

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSalesDashboardPayoutAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        rep_group = cls.env.ref("plasticos_security_base.group_sales_rep")
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.rep_a = Users.create(
            {"name": "Payout Rep A", "login": "nc_b_payout_rep_a", "group_ids": [Command.set([rep_group.id])]}
        )
        cls.rep_b = Users.create(
            {"name": "Payout Rep B", "login": "nc_b_payout_rep_b", "group_ids": [Command.set([rep_group.id])]}
        )
        Tx = cls.env["plasticos.transaction"]
        cls.tx_foreign_payout = Tx.create({"user_id": cls.rep_a.id})
        cls.tx_own_payout = Tx.create({"user_id": cls.rep_a.id})
        Payout = cls.env["plasticos.commission.payout"]
        today = fields.Date.today()
        cls.payout_b = Payout.create(
            {
                "sales_rep_id": cls.rep_b.id,
                "period_start": today,
                "period_end": today,
                "transaction_ids": [Command.set(cls.tx_foreign_payout.ids)],
            }
        )
        cls.payout_a = Payout.create(
            {
                "sales_rep_id": cls.rep_a.id,
                "period_start": today,
                "period_end": today,
                "transaction_ids": [Command.set(cls.tx_own_payout.ids)],
            }
        )
        cls.env.flush_all()

    def _row(self, tx):
        return self.env["plasticos.sales.dashboard"].with_user(self.rep_a).browse(tx.id)

    def test_rep_does_not_learn_another_reps_payout(self):
        action = self._row(self.tx_foreign_payout).action_view_payout()
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertNotIn(str(self.payout_b.id), str(action))

    def test_rep_still_opens_own_payout(self):
        action = self._row(self.tx_own_payout).action_view_payout()
        self.assertEqual(action["res_model"], "plasticos.commission.payout")
        self.assertEqual(action["domain"], [("id", "in", self.payout_a.ids)])
