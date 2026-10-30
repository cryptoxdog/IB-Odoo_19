"""Closed-by-default historical creation and one-record Manager reopen."""

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

_REOPEN_ID = "plasticos_historical_reopen_id"
_REOPEN_REASON = "plasticos_historical_reopen_reason"


@tagged("post_install", "-at_install", "transaction")
class TestHistoricalReopen(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Historical Reopen Partner", "is_company": True, "customer_rank": 1, "supplier_rank": 1}
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Historical Reopen Manager",
                "login": "hist_reopen_manager",
                "group_ids": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("plasticos_transaction.group_plasticos_manager").id,
                        ]
                    )
                ],
            }
        )
        cls.user = cls.env["res.users"].create(
            {
                "name": "Historical Reopen User",
                "login": "hist_reopen_user",
                "group_ids": [Command.set([cls.env.ref("base.group_user").id])],
            }
        )
        cls.product = cls.env["product.product"].create({"name": "Historical Reopen Product", "type": "consu"})

    def _historical(self, name, status="WORK", state="closed"):
        return self.env["plasticos.transaction"].create(
            {
                "name": name,
                "buyer_id": self.partner.id,
                "supplier_id": self.partner.id,
                "legacy_erp_history": True,
                "legacy_erp_status": status,
                "state": state,
            }
        )

    def test_creation_values_are_closed_for_every_source_status(self):
        sale = self.env["sale.order"].create({"partner_id": self.partner.id, "origin": "WS-X"})
        for status in ("WORK", "NEW", "I", "C", "", "VOID?", "X"):
            vals = sale.with_context(erp_raw_status_by_origin={"WS-X": status})._transaction_vals(True, "WS-X")
            self.assertEqual(vals["state"], "closed", status)
            self.assertTrue(vals["legacy_erp_history"], status)
            self.assertEqual(vals["legacy_erp_status"], status)
        live = sale._transaction_vals(False, "")
        self.assertNotIn("state", live)
        self.assertNotIn("legacy_erp_history", live)

    def test_manager_reopen_posts_an_audit_and_leaves_provenance(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [Command.create({"name": "Archived", "quantity": 1, "price_unit": 10})],
            }
        )
        tx = self.env["plasticos.transaction"].create(
            {
                "name": "WS-OPEN",
                "buyer_id": self.partner.id,
                "supplier_id": self.partner.id,
                "legacy_erp_history": True,
                "legacy_erp_status": "I",
                "state": "closed",
                "customer_invoice_id": invoice.id,
            }
        )
        payments = self.env["account.payment"].search_count([])
        tx.with_user(self.manager).action_reopen_historical("  yard still has the load  ")
        self.assertEqual(tx.state, "active")
        self.assertEqual(tx.legacy_erp_status, "I")
        self.assertTrue(tx.legacy_erp_history)
        self.assertEqual(tx.customer_invoice_id, invoice)
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(self.env["account.payment"].search_count([]), payments)
        note = tx.message_ids.filtered(lambda message: "Historical reopen" in (message.body or ""))
        self.assertTrue(note)
        self.assertIn("yard still has the load", note[0].body)
        self.assertIn(self.manager.name, note[0].body)
        self.assertIn("WS-OPEN", note[0].body)
        other = self._historical("WS-WIZ", "NEW")
        with self.assertRaises(AccessError):
            self.env["plasticos.transaction.reopen.wizard"].with_user(self.user).create(
                {"transaction_id": other.id, "reason": "no"}
            )
        wizard = (
            self.env["plasticos.transaction.reopen.wizard"]
            .with_user(self.manager)
            .create({"transaction_id": other.id, "reason": "wizard reason"})
        )
        wizard.action_reopen()
        self.assertEqual(other.state, "active")
        self.assertEqual(other.legacy_erp_status, "NEW")

    def test_reopen_rejects_the_negative_cases(self):
        historical = self._historical("WS-NEG", "C")
        live = self.env["plasticos.transaction"].create(
            {"name": "WS-LIVE", "buyer_id": self.partner.id, "supplier_id": self.partner.id}
        )
        active = self._historical("WS-ACT", "NEW", state="active")
        with self.assertRaisesRegex(UserError, "Only Plasticos Managers"):
            historical.with_user(self.user).action_reopen_historical("because")
        with self.assertRaisesRegex(UserError, "Only an imported historical"):
            live.with_user(self.manager).action_reopen_historical("because")
        with self.assertRaisesRegex(UserError, "Only a Closed historical"):
            active.with_user(self.manager).action_reopen_historical("because")
        with self.assertRaisesRegex(UserError, "A reopen reason is required"):
            historical.with_user(self.manager).action_reopen_historical("   ")
        with self.assertRaisesRegex(UserError, "one historical transaction"):
            (historical | active).with_user(self.manager).action_reopen_historical("because")
        with self.assertRaisesRegex(UserError, "separately approved operations migration"):
            historical.with_user(self.manager).write({"state": "active"})
        forged = {
            _REOPEN_ID: historical.id,
            _REOPEN_REASON: "forged",
        }
        with self.assertRaisesRegex(UserError, "separately approved operations migration"):
            historical.with_user(self.user).with_context(**forged).write({"state": "active"})
        with self.assertRaisesRegex(UserError, "source identity and status are immutable"):
            historical.with_user(self.manager).with_context(**forged).write(
                {"state": "active", "legacy_erp_status": "CHANGED"}
            )
        with self.assertRaisesRegex(UserError, "separately approved operations migration"):
            historical.with_user(self.manager).with_context(
                **{_REOPEN_ID: active.id, _REOPEN_REASON: "wrong id"}
            ).write({"state": "active"})
        with self.assertRaisesRegex(UserError, "separately approved operations migration"):
            historical.with_user(self.manager).with_context(bypass_state_guard=True).write({"state": "active"})
        self.assertEqual(historical.state, "closed")
        self.assertEqual(historical.legacy_erp_status, "C")
        self.assertEqual(live.state, "draft")
        self.assertEqual(active.state, "active")

    def test_replay_does_not_reclose_a_reopened_transaction(self):
        tx = self._historical("WS-REPLAY", "X")
        tx.with_user(self.manager).action_reopen_historical("still moving")
        sale = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "origin": "WS-REPLAY",
                "order_line": [Command.create({"product_id": self.product.id, "product_uom_qty": 1, "price_unit": 1})],
            }
        )
        sale.with_context(import_mode=True, erp_raw_status_by_origin={"WS-REPLAY": "X"}).action_confirm()
        self.assertEqual(tx.state, "active")
        self.assertEqual(tx.legacy_erp_status, "X")
        self.assertEqual(self.env["plasticos.transaction"].search_count([("name", "=", "WS-REPLAY")]), 1)
        self.assertEqual(sale.state, "sale")
