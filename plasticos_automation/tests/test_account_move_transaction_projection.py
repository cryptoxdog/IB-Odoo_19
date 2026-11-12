"""account.move.transaction_id is a projection of the links plasticos.transaction owns."""

import importlib.util
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.modules.module import get_module_path
from odoo.tests import tagged

ACCOUNT_MOVE = "account.move"
LINK_RULE = "plasticos_automation.rule_trigger_penalty_on_transaction_link"


def _backfill():
    path = get_module_path("plasticos_automation") + "/migrations/19.0.2.1.11/post-migrate.py"
    spec = importlib.util.spec_from_file_location("plasticos_automation_backfill_1902111", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install", "plasticos", "automation")
class TestAccountMoveTransactionProjection(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Projection Counterparty", "is_company": True, "customer_rank": 1, "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].create({"name": "Projection Regrind", "type": "consu"})

    def _move(self, move_type="in_invoice"):
        return self.env[ACCOUNT_MOVE].create(
            {
                "move_type": move_type,
                "partner_id": self.partner.id,
                "invoice_date": "2026-11-01",
                "invoice_line_ids": [(0, 0, {"product_id": self.product.id, "quantity": 1, "price_unit": 100.0})],
            }
        )

    def _transaction(self, name):
        transaction = self._create_transaction(name=name)
        self.assertTrue(transaction, "plasticos.transaction is required by plasticos_automation")
        return transaction

    def _stored_transaction(self, move):
        self.env.flush_all()
        self.env.cr.execute("SELECT transaction_id FROM account_move WHERE id = %s", [move.id])
        return self.env.cr.fetchone()[0]

    # ── projection ───────────────────────────────────────────

    def test_field_is_a_readonly_stored_projection(self):
        field = self.env[ACCOUNT_MOVE]._fields["transaction_id"]
        self.assertTrue(field.compute and field.store and field.readonly and field.compute_sudo)
        self.assertEqual(field.ondelete, "restrict")

    def test_each_owned_link_projects_its_transaction_and_unlinking_clears_it(self):
        transaction = self._transaction("TX-PROJ-ONE")
        invoice, vendor_bill, freight_bill = self._move("out_invoice"), self._move(), self._move()
        unlinked = self._move()

        transaction.customer_invoice_id = invoice
        transaction.vendor_bill_ids = [(4, vendor_bill.id)]
        transaction.freight_bill_ids = [(4, freight_bill.id)]

        for move in (invoice, vendor_bill, freight_bill):
            self.assertEqual(move.transaction_id, transaction)
            self.assertEqual(self._stored_transaction(move), transaction.id)
        self.assertFalse(unlinked.transaction_id)

        transaction.vendor_bill_ids = [(3, vendor_bill.id)]
        transaction.freight_bill_ids = [(5, 0, 0)]

        for move in (vendor_bill, freight_bill):
            self.assertFalse(move.transaction_id)
            self.assertIsNone(self._stored_transaction(move))

        # The customer-invoice pointer is immutable by product contract
        # (plasticos_transaction refuses to reassign or clear it), so the
        # projection of that link has no reachable "cleared" state.
        with self.assertRaises(UserError):
            transaction.customer_invoice_id = False
        self.assertEqual(invoice.transaction_id, transaction)
        self.assertEqual(self._stored_transaction(invoice), transaction.id)

    def test_two_transactions_claiming_one_bill_project_nothing(self):
        """Falsifying: ambiguity is empty, never the first or the last claimant."""
        first, second = self._transaction("TX-PROJ-A"), self._transaction("TX-PROJ-B")
        bill = self._move()

        first.vendor_bill_ids = [(4, bill.id)]
        self.assertEqual(bill.transaction_id, first)
        second.freight_bill_ids = [(4, bill.id)]

        self.assertFalse(bill.transaction_id)
        self.assertIsNone(self._stored_transaction(bill))

        second.freight_bill_ids = [(3, bill.id)]
        self.assertEqual(bill.transaction_id, first, "one remaining owner is unambiguous again")

    def test_same_transaction_through_two_links_is_one_owner(self):
        transaction = self._transaction("TX-PROJ-TWICE")
        bill = self._move()
        transaction.vendor_bill_ids = [(4, bill.id)]
        transaction.freight_bill_ids = [(4, bill.id)]
        self.assertEqual(bill.transaction_id, transaction)

    def test_commission_amount_follows_the_projected_transaction(self):
        """The move follows the transaction's commission through the ORM dependency chain.

        The ORM marks dependents of a computed field when one of that field's own
        inputs is modified, so the commission is driven through real inputs: the
        lock fields plasticos_commission writes at close. Nothing is patched and
        the move is never recomputed by hand.
        """
        transaction = self._transaction("TX-PROJ-COMM")
        bill = self._move()
        self.assertEqual(bill.commission_amount, 0.0)
        transaction.vendor_bill_ids = [(4, bill.id)]
        self.assertEqual(bill.commission_amount, transaction.commission_amount or 0.0)

        if "commission_locked" not in transaction._fields:
            # Without plasticos_commission the transaction's commission is the
            # constant-zero stub with no inputs: there is no value to follow.
            self.assertEqual((transaction.commission_amount, bill.commission_amount), (0.0, 0.0))
            return

        transaction.write({"commission_locked_amount": 42.5, "commission_locked": True})

        self.assertEqual(transaction.commission_amount, 42.5)
        self.assertEqual(bill.commission_amount, 42.5)
        self.env.flush_all()
        self.env.cr.execute("SELECT commission_amount FROM account_move WHERE id = %s", [bill.id])
        self.assertEqual(self.env.cr.fetchone()[0], 42.5)

        transaction.write({"commission_locked_amount": 17.25})
        self.assertEqual(bill.commission_amount, 17.25, "a later change of the input is followed too")

        # Falsifying: a move the transaction no longer owns stops following it.
        transaction.vendor_bill_ids = [(3, bill.id)]
        self.assertEqual(transaction.commission_amount, 17.25)
        self.assertEqual(bill.commission_amount, 0.0)

    def test_linked_transaction_cannot_be_deleted(self):
        transaction = self._transaction("TX-PROJ-DEL")
        bill = self._move()
        transaction.vendor_bill_ids = [(4, bill.id)]
        self.env.flush_all()
        with self.assertRaises(UserError):
            transaction.unlink()
        self.assertTrue(bill.exists())

    # ── penalty trigger ──────────────────────────────────────

    def _counted_penalties(self):
        calls = []
        real = type(self.env[ACCOUNT_MOVE]).calculate_penalties

        def counted(moves):
            calls.append(moves.ids)
            return real(moves)

        return calls, patch.object(type(self.env[ACCOUNT_MOVE]), "calculate_penalties", counted)

    def test_link_rule_is_installed_with_its_precondition(self):
        rule = self.env.ref(LINK_RULE)
        self.assertTrue(rule.active)
        self.assertEqual(rule.trigger, "on_write")
        self.assertEqual(rule.filter_pre_domain, "[('transaction_id', '=', False)]")
        self.assertEqual(rule.trigger_field_ids.mapped("name"), ["transaction_id"])

    def test_posted_move_gaining_its_transaction_calculates_penalties_once(self):
        transaction = self._transaction("TX-PROJ-POSTED")
        bill = self._move()
        bill.action_post()
        self.assertEqual(bill.state, "posted")
        calls, counting = self._counted_penalties()

        with counting:
            transaction.vendor_bill_ids = [(4, bill.id)]
            self.env.flush_all()
            self.assertEqual(calls, [[bill.id]], "the link after posting runs the calculation exactly once")
            # Later unrelated recomputes and writes do not run it again.
            bill.write({"reconciliation_notes": "checked"})
            transaction.freight_bill_ids = [(4, bill.id)]
            self.env.flush_all()
            self.assertEqual(calls, [[bill.id]])

    def test_draft_move_gaining_its_transaction_calculates_nothing(self):
        """Falsifying: the link alone is not the trigger; the move must be posted."""
        transaction = self._transaction("TX-PROJ-DRAFT")
        bill = self._move()
        calls, counting = self._counted_penalties()
        with counting:
            transaction.vendor_bill_ids = [(4, bill.id)]
            self.env.flush_all()
        self.assertEqual(bill.transaction_id, transaction)
        self.assertEqual(calls, [])

    def test_posted_move_without_transaction_calculates_nothing(self):
        bill = self._move()
        calls, counting = self._counted_penalties()
        with counting:
            bill.action_post()
            self.env.flush_all()
        self.assertEqual(calls, [])

    # ── migration backfill ───────────────────────────────────

    def test_backfill_sets_single_owners_clears_the_rest_and_fires_nothing(self):
        owner, other = self._transaction("TX-PROJ-BF-A"), self._transaction("TX-PROJ-BF-B")
        single, ambiguous, stale = self._move(), self._move(), self._move()
        owner.vendor_bill_ids = [(4, single.id), (4, ambiguous.id)]
        other.freight_bill_ids = [(4, ambiguous.id)]
        self.env.flush_all()
        # Rebuild the pre-upgrade state: the column was never derived.
        self.env.cr.execute("UPDATE account_move SET transaction_id = NULL WHERE id IN %s", [(single.id, ambiguous.id)])
        self.env.cr.execute("UPDATE account_move SET transaction_id = %s WHERE id = %s", [other.id, ambiguous.id])
        self.env.cr.execute("UPDATE account_move SET transaction_id = %s WHERE id = %s", [owner.id, stale.id])
        calls, counting = self._counted_penalties()

        with counting:
            _backfill().migrate(self.env.cr, "19.0.2.1.10")

        self.env.invalidate_all()
        self.assertEqual(single.transaction_id, owner)
        self.assertFalse(ambiguous.transaction_id, "two claimants stay empty")
        self.assertFalse(stale.transaction_id, "a value no link supports is cleared")
        self.assertEqual(calls, [], "the backfill calculates no penalty")
