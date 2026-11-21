"""F-003 / DEC-006: the Sales dashboard reads commission state from the real records.

Locked amount comes from ``plasticos.transaction.commission_locked_amount`` once the
commission is locked. Pay status is the state of the newest non-cancelled
``plasticos.commission.payout`` linked through ``commission_payout_tx_rel``; with no
such payout it is ``unpaid``. ``plasticos.transaction.commission_payout_state`` is not
read and not written (RISK-003).
"""

from __future__ import annotations

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSalesDashboardPayoutProjection(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        rep_group = cls.env.ref("plasticos_security_base.group_sales_rep")
        cls.rep = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {"name": "Projection Rep", "login": "f003_projection_rep", "group_ids": [Command.set([rep_group.id])]}
            )
        )

    def _deal(self, locked_amount=None):
        tx = self.env["plasticos.transaction"].create({"user_id": self.rep.id})
        if locked_amount is not None:
            tx.write({"commission_locked": True, "commission_locked_amount": locked_amount})
        return tx

    def _payout(self, tx, state):
        today = fields.Date.today()
        payout = self.env["plasticos.commission.payout"].create(
            {
                "sales_rep_id": self.rep.id,
                "period_start": today,
                "period_end": today,
                "transaction_ids": [Command.set(tx.ids)],
            }
        )
        if state in ("confirmed", "paid"):
            payout.action_confirm()
        if state == "paid":
            payout.write({"payment_date": today})
            payout.action_mark_paid()
        if state == "cancelled":
            payout.action_cancel()
        self.assertEqual(payout.state, state)
        return payout

    def _row(self, tx):
        self.env.flush_all()
        row = self.env["plasticos.sales.dashboard"].with_user(self.rep).search([("transaction_id", "=", tx.id)])
        self.assertEqual(len(row), 1)
        row.invalidate_recordset()
        return row

    def test_no_payout_is_unpaid(self):
        row = self._row(self._deal())
        self.assertEqual(row.commission_payout_state, "unpaid")
        self.assertFalse(row.commission_locked)

    def test_draft_payout_is_shown_as_draft(self):
        tx = self._deal(locked_amount=50.0)
        self._payout(tx, "draft")
        self.assertEqual(self._row(tx).commission_payout_state, "draft")

    def test_confirmed_payout_is_awaiting_payment(self):
        tx = self._deal(locked_amount=75.0)
        self._payout(tx, "confirmed")
        self.assertEqual(self._row(tx).commission_payout_state, "confirmed")

    def test_paid_payout_shows_paid_and_locked_amount(self):
        tx = self._deal(locked_amount=123.45)
        self._payout(tx, "paid")
        row = self._row(tx)
        self.assertEqual(row.commission_payout_state, "paid")
        self.assertTrue(row.commission_locked)
        self.assertAlmostEqual(row.commission_locked_amount, 123.45)

    def test_cancelled_newer_payout_falls_back_to_prior_state(self):
        tx = self._deal(locked_amount=10.0)
        self._payout(tx, "paid")
        self._payout(tx, "cancelled")
        self.assertEqual(self._row(tx).commission_payout_state, "paid")

    def test_only_cancelled_payout_is_unpaid(self):
        tx = self._deal(locked_amount=10.0)
        self._payout(tx, "cancelled")
        self.assertEqual(self._row(tx).commission_payout_state, "unpaid")

    def test_newest_non_cancelled_payout_wins(self):
        tx = self._deal(locked_amount=10.0)
        self._payout(tx, "confirmed")
        self._payout(tx, "draft")
        self.assertEqual(self._row(tx).commission_payout_state, "draft")

    def test_transaction_payout_state_field_is_not_the_source(self):
        tx = self._deal(locked_amount=10.0)
        tx.write({"commission_payout_state": "paid"})
        self.assertEqual(self._row(tx).commission_payout_state, "unpaid")
