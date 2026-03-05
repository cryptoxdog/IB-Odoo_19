"""State machine tests for plasticos.transaction.

States: draft → active → pending_supplier → supplier_ready → in_progress
        → in_transit → delivered → invoiced → closed | cancelled

Source: plasticos_transaction/models/transaction.py
"""

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestTransactionStateMachine(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Tx = cls.env["plasticos.transaction"]
        cls.partner = cls.env["res.partner"].create({"name": "SM Partner", "is_company": True})
        cls.manager_group = cls.env.ref("plasticos_transaction.group_plasticos_manager")
        cls.env.user.groups_id |= cls.manager_group

    def _tx(self, **kw):
        vals = {"partner_id": self.partner.id, "supplier_id": self.partner.id, "buyer_id": self.partner.id}
        vals.update(kw)
        return self.Tx.create(vals)

    # ── Initial state ────────────────────────────────────────
    def test_create_defaults_to_draft(self):
        tx = self._tx()
        self.assertEqual(tx.state, "draft")

    def test_sequence_auto_assigned(self):
        tx = self._tx()
        self.assertNotEqual(tx.name, "New")

    # ── draft → active ───────────────────────────────────────
    def test_activate_from_draft(self):
        tx = self._tx()
        tx.action_activate()
        self.assertEqual(tx.state, "active")

    # ── Write guard blocks raw state changes ─────────────────
    def test_raw_state_change_blocked(self):
        tx = self._tx()
        with self.assertRaises(UserError):
            tx.write({"state": "in_transit"})

    def test_name_immutable_after_create(self):
        tx = self._tx()
        with self.assertRaises(UserError):
            tx.write({"name": "TX-HACKED"})

    # ── close guards ─────────────────────────────────────────
    def test_close_requires_posted_invoice(self):
        tx = self._tx()
        tx.action_activate()
        with self.assertRaises(UserError):
            tx.action_close()

    def test_close_requires_manager_group(self):
        tx = self._tx()
        tx.action_activate()
        user_basic = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Basic",
                    "login": "basic_sm",
                    "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
                }
            )
        )
        with self.assertRaises(UserError):
            tx.with_user(user_basic).action_close()

    def test_close_requires_positive_margin(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
            }
        )
        invoice.action_post()
        tx = self._tx(customer_invoice_id=invoice.id)
        tx.action_activate()
        # gross_margin will be 0 or negative with no revenue
        with self.assertRaises(UserError):
            tx.action_close()

    def test_double_close_raises(self):
        tx = self._tx(state="closed", commission_locked=True, commission_locked_amount=0)
        # force closed state for test
        self.env.cr.execute("UPDATE plasticos_transaction SET state='closed' WHERE id=%s", (tx.id,))
        tx.invalidate_recordset()
        with self.assertRaises(UserError):
            tx.action_close()

    # ── Closed transaction immutability ──────────────────────
    def test_closed_tx_blocks_protected_fields(self):
        tx = self._tx()
        self.env.cr.execute("UPDATE plasticos_transaction SET state='closed' WHERE id=%s", (tx.id,))
        tx.invalidate_recordset()
        with self.assertRaises(UserError):
            tx.write({"sale_order_id": False})

    def test_closed_tx_blocks_commission_rule_change(self):
        tx = self._tx()
        self.env.cr.execute(
            "UPDATE plasticos_transaction SET state='closed', commission_locked=true WHERE id=%s", (tx.id,)
        )
        tx.invalidate_recordset()
        with self.assertRaises(UserError):
            tx.write({"commission_rule_id": False})

    # ── Delete guards ────────────────────────────────────────
    def test_delete_closed_tx_blocked(self):
        tx = self._tx()
        self.env.cr.execute("UPDATE plasticos_transaction SET state='closed' WHERE id=%s", (tx.id,))
        tx.invalidate_recordset()
        with self.assertRaises(UserError):
            tx.unlink()

    def test_delete_tx_with_invoice_blocked(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
            }
        )
        tx = self._tx(customer_invoice_id=invoice.id)
        with self.assertRaises(UserError):
            tx.unlink()

    def test_delete_draft_tx_ok(self):
        tx = self._tx()
        tx_id = tx.id
        tx.unlink()
        self.assertFalse(self.Tx.browse(tx_id).exists())
