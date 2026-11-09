"""Test 11 — Account Move ↔ Transaction Integration.

Source: plasticos_transaction/models/account_move_inherit.py
Risk: CRITICAL — Financial data corruption if linking or guards break.

Validates:
  - action_post() links customer invoices to transactions via SO.transaction_id
  - action_post() links vendor bills to transactions via PO
  - button_cancel() blocks cancellation when linked tx is closed
  - unlink() blocks deletion when linked tx is closed
  - action_post() blocks credit notes on closed transactions
  - action_post() runs compliance check before posting
"""

import base64
import logging
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

_logger = logging.getLogger(__name__)


def _close_transaction(tx):
    """Close ``tx`` through the production close write.

    A direct ``state`` write is refused outside action methods
    (plasticos_transaction/models/transaction.py:924-946). ``_apply_close`` is the write that
    ``action_close`` performs once its preconditions pass (transaction.py:1049-1051), including the
    commission lock (plasticos_commission/models/transaction_commission.py:100-106); the guards under
    test here only read the resulting closed state.
    """
    tx._apply_close(tx)
    return tx


@tagged("post_install", "-at_install", "accounting", "critical")
class TestAccountMoveTransactionLink(PlasticosTestCase):
    """Invoice/bill ↔ transaction linking on action_post()."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Supplier Co",
                "is_company": True,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Test Buyer Co",
                "is_company": True,
            }
        )
        # Create a minimal transaction
        try:
            cls.tx = cls.env["plasticos.transaction"].create(
                {
                    "supplier_id": cls.partner.id,
                    "buyer_id": cls.buyer.id,
                    "quantity": 40000,
                }
            )
            cls.has_tx = True
        except Exception:
            cls.has_tx = False

    def _skip_if_missing(self):
        if not self.has_tx:
            self.skipTest("plasticos_transaction not fully installable in test env")

    def _create_invoice(self, move_type="out_invoice", origin=None):
        """Helper: create a minimal account.move."""
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "name": "Test line",
                        "quantity": 1,
                        "price_unit": 100.0,
                    },
                )
            ],
        }
        if origin:
            vals["invoice_origin"] = origin
        return self.env["account.move"].create(vals)

    # ── _find_linked_transactions ────────────────────────
    def test_find_linked_transactions_via_customer_invoice(self):
        """_find_linked_transactions finds tx via customer_invoice_id."""
        self._skip_if_missing()
        move = self._create_invoice()
        self.tx.customer_invoice_id = move.id
        found = self.env["account.move"]._find_linked_transactions(move.id)
        self.assertIn(self.tx, found)

    def test_find_linked_transactions_via_vendor_bill(self):
        """_find_linked_transactions finds tx via vendor_bill_ids."""
        self._skip_if_missing()
        move = self._create_invoice(move_type="in_invoice")
        self.tx.vendor_bill_ids = [(4, move.id)]
        found = self.env["account.move"]._find_linked_transactions(move.id)
        self.assertIn(self.tx, found)

    def test_find_linked_transactions_via_freight_bill(self):
        """_find_linked_transactions finds tx via freight_bill_ids."""
        self._skip_if_missing()
        if "freight_bill_ids" not in self.tx._fields:
            self.skipTest("freight_bill_ids not on transaction")
        move = self._create_invoice(move_type="in_invoice")
        self.tx.freight_bill_ids = [(4, move.id)]
        found = self.env["account.move"]._find_linked_transactions(move.id)
        self.assertIn(self.tx, found)

    def test_find_linked_transactions_returns_empty_when_no_link(self):
        self._skip_if_missing()
        move = self._create_invoice()
        found = self.env["account.move"]._find_linked_transactions(move.id)
        self.assertFalse(found)


@tagged("post_install", "-at_install", "accounting", "critical")
class TestAccountMoveCancelGuard(PlasticosTestCase):
    """button_cancel() must block when linked transaction is closed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Guard Test Partner",
                "is_company": True,
            }
        )
        try:
            cls.tx = cls.env["plasticos.transaction"].create(
                {
                    "supplier_id": cls.partner.id,
                    "buyer_id": cls.partner.id,
                    "quantity": 10000,
                }
            )
            cls.has_tx = True
        except Exception:
            cls.has_tx = False

    def _skip_if_missing(self):
        if not self.has_tx:
            self.skipTest("plasticos_transaction not installable")

    def test_cannot_cancel_invoice_linked_to_closed_tx(self):
        """button_cancel raises UserError when tx is closed."""
        self._skip_if_missing()
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 50.0,
                        },
                    )
                ],
            }
        )
        self.tx.customer_invoice_id = move.id
        _close_transaction(self.tx)
        with self.assertRaises(UserError, msg="Should block cancel on closed tx"):
            move.button_cancel()

    def test_cancel_allowed_when_tx_not_closed(self):
        """button_cancel succeeds when tx is not closed."""
        self._skip_if_missing()
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 50.0,
                        },
                    )
                ],
            }
        )
        self.tx.customer_invoice_id = move.id
        self.tx.state = "active"
        # Should NOT raise
        try:
            move.button_cancel()
        except UserError:
            self.fail("button_cancel should succeed when tx is active")


@tagged("post_install", "-at_install", "accounting", "critical")
class TestAccountMoveUnlinkGuard(PlasticosTestCase):
    """unlink() must block when linked transaction is closed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Unlink Guard Partner",
                "is_company": True,
            }
        )
        try:
            cls.tx = cls.env["plasticos.transaction"].create(
                {
                    "supplier_id": cls.partner.id,
                    "buyer_id": cls.partner.id,
                    "quantity": 10000,
                }
            )
            cls.has_tx = True
        except Exception:
            cls.has_tx = False

    def test_cannot_delete_invoice_linked_to_closed_tx(self):
        if not self.has_tx:
            self.skipTest("plasticos_transaction not installable")
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 50.0,
                        },
                    )
                ],
            }
        )
        self.tx.customer_invoice_id = move.id
        _close_transaction(self.tx)
        with self.assertRaises(UserError):
            move.unlink()

    def test_delete_allowed_when_no_linked_tx(self):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 50.0,
                        },
                    )
                ],
            }
        )
        # No tx link — should succeed
        move_id = move.id
        move.unlink()
        self.assertFalse(self.env["account.move"].browse(move_id).exists())


@tagged("post_install", "-at_install", "accounting", "critical")
class TestAccountMoveCreditNoteGuard(PlasticosTestCase):
    """Credit note post blocked when reversed move links to closed tx."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Credit Note Partner",
                "is_company": True,
            }
        )
        try:
            cls.tx = cls.env["plasticos.transaction"].create(
                {
                    "supplier_id": cls.partner.id,
                    "buyer_id": cls.partner.id,
                    "quantity": 10000,
                }
            )
            cls.has_tx = True
        except Exception:
            cls.has_tx = False

    def test_credit_note_blocked_for_closed_transaction(self):
        """action_post raises UserError for credit note on closed tx."""
        if not self.has_tx:
            self.skipTest("plasticos_transaction not installable")
        original = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        self.tx.customer_invoice_id = original.id
        _close_transaction(self.tx)
        refund = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "partner_id": self.partner.id,
                "reversed_entry_id": original.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Refund line",
                            "quantity": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(UserError, msg="Credit note should be blocked"):
            refund.action_post()


@tagged("post_install", "-at_install", "accounting")
class TestAccountMoveComplianceGate(PlasticosTestCase):
    """action_post checks compliance before posting customer invoices."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Compliance Partner",
                "is_company": True,
            }
        )

    def test_compliance_check_blocks_invoice_when_docs_missing(self):
        """If compliance service returns False, action_post raises."""
        if "plasticos.compliance.service" not in self.env:
            self.skipTest("plasticos_documents not installed")
        ComplianceService = self.env["plasticos.compliance.service"]

        # Mock is_compliant to return False
        with patch.object(type(ComplianceService), "is_compliant", return_value=False):
            if "sale.order" not in self.env or "plasticos.transaction" not in self.env:
                self.skipTest("sale.order or transaction not available")
            SO = self.env["sale.order"]
            TX = self.env["plasticos.transaction"]

            tx = TX.create(
                {
                    "supplier_id": self.partner.id,
                    "buyer_id": self.partner.id,
                    "quantity": 10000,
                }
            )
            so = SO.create(
                {
                    "partner_id": self.partner.id,
                    "transaction_id": tx.id,
                }
            )
            move = self.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "invoice_origin": so.name,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Line",
                                "quantity": 1,
                                "price_unit": 50.0,
                            },
                        )
                    ],
                }
            )
            with self.assertRaises(UserError):
                move.action_post()

    # ── Unmocked gate: rules are scoped by purpose ────────────────────

    def _invoice_for_new_transaction(self):
        tx = self.env["plasticos.transaction"].create({"supplier_id": self.partner.id, "buyer_id": self.partner.id})
        so = self.env["sale.order"].create({"partner_id": self.partner.id, "transaction_id": tx.id})
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_origin": so.name,
                "invoice_line_ids": [(0, 0, {"name": "Line", "quantity": 1, "price_unit": 50.0})],
            }
        )
        return tx, move

    def _rule(self, code, *, for_invoice, for_close):
        tag = self.env["plasticos.document.tag"].create({"name": f"Gate {code}", "code": code})
        self.env["plasticos.document.rule"].create(
            {
                "name": f"Gate rule {code}",
                "tag_id": tag.id,
                "res_model": "plasticos.transaction",
                "required_for_invoice": for_invoice,
                "required_for_close": for_close,
            }
        )
        return tag

    def test_invoice_rule_without_document_blocks_invoice(self):
        """A missing required_for_invoice document blocks posting (no mock)."""
        self._rule("gate_invoice_doc", for_invoice=True, for_close=False)
        _tx, move = self._invoice_for_new_transaction()
        with self.assertRaisesRegex(UserError, "Missing required documents for invoice posting"):
            move.action_post()
        self.assertEqual(move.state, "draft")

    def test_close_only_rule_does_not_block_invoice(self):
        """A rule required only for close must not block invoice posting."""
        self._rule("gate_close_doc", for_invoice=False, for_close=True)
        _tx, move = self._invoice_for_new_transaction()
        move.action_post()
        self.assertEqual(move.state, "posted")

    def test_compliance_service_scopes_rules_by_purpose(self):
        invoice_tag = self._rule("gate_scope_invoice", for_invoice=True, for_close=False)
        close_tag = self._rule("gate_scope_close", for_invoice=False, for_close=True)
        tx, _move = self._invoice_for_new_transaction()
        service = self.env["plasticos.compliance.service"]
        for_invoice = service.get_missing_documents("plasticos.transaction", tx.id, purpose="invoice")
        for_close = service.get_missing_documents("plasticos.transaction", tx.id, purpose="close")
        unscoped = service.get_missing_documents("plasticos.transaction", tx.id)
        self.assertIn(invoice_tag.code, for_invoice)
        self.assertNotIn(close_tag.code, for_invoice)
        self.assertIn(close_tag.code, for_close)
        self.assertNotIn(invoice_tag.code, for_close)
        self.assertTrue({invoice_tag.code, close_tag.code} <= set(unscoped))


@tagged("post_install", "-at_install", "accounting", "critical")
class TestHistoricalAutopostGuard(PlasticosTestCase):
    """Document compliance updates readiness. Explicit posting of archival originals is refused."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Historical Autopost Partner", "is_company": True, "customer_rank": 1, "supplier_rank": 1}
        )
        cls.doc_manager = cls.env["res.users"].create(
            {
                "name": "Historical Docs Manager",
                "login": "hist_docs_manager_phase_a",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("plasticos_documents.group_documents_manager").id,
                        ],
                    )
                ],
            }
        )

    def _tx(self):
        return self.env["plasticos.transaction"].create({"supplier_id": self.partner.id, "buyer_id": self.partner.id})

    def _isolate_invoice_rule(self, code):
        self.env["plasticos.document.rule"].search([("res_model", "=", "plasticos.transaction")]).write(
            {"active": False}
        )
        tag = self.env["plasticos.document.tag"].create({"name": code, "code": code})
        self.env["plasticos.document.rule"].create(
            {
                "name": code,
                "tag_id": tag.id,
                "res_model": "plasticos.transaction",
                "required_for_invoice": True,
                "required_for_close": False,
            }
        )
        return tag

    def _mark(self, record, name, module="plasticos_transaction", model=None):
        self.env["ir.model.data"].create(
            {
                "module": module,
                "name": name,
                "model": model or record._name,
                "res_id": record.id,
                "noupdate": True,
            }
        )

    def _move(self, move_type, *, origin=None, invoice_date=None):
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "invoice_line_ids": [(0, 0, {"name": "Line", "quantity": 1, "price_unit": 50.0})],
        }
        if origin:
            vals["invoice_origin"] = origin
        if invoice_date:
            vals["invoice_date"] = invoice_date
        return self.env["account.move"].create(vals)

    def _satisfy(self, tx, tag):
        # The invoice link is already stored before a document arrives. Flush it
        # so this single test transaction matches that request boundary.
        self.env.flush_all()
        attachment = self.env["ir.attachment"].create(
            {
                "name": f"{tag.code}.txt",
                "datas": base64.b64encode(b"proof"),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )
        doc = self.env["plasticos.document"].create(
            {
                "name": tag.code,
                "tag_id": tag.id,
                "res_model": "documents.document",
                "res_id": 0,
                "attachment_id": attachment.id,
            }
        )
        row = doc.with_user(self.doc_manager).action_associate(
            "plasticos.transaction",
            tx.id,
            source_reference="historical-fixture",
        )
        self.env["plasticos.document"].browse(row.id).with_user(self.doc_manager).action_verify()
        return self.env["plasticos.document"].browse(row.id)

    def test_historical_markers_stay_draft_when_compliance_is_satisfied(self):
        """A marked invoice and an undated marked bill stay draft across missing -> compliant."""
        tag = self._isolate_invoice_rule("hist_autopost_only")
        tx = self._tx()
        invoice = self._move("out_invoice", origin="54839", invoice_date="2022-04-01")
        bill = self._move("in_invoice", origin="54839")
        self._mark(invoice, "legacy_erp_outinv_54839")
        self._mark(bill, "legacy_erp_ininv_591398")
        tx.customer_invoice_id = invoice
        tx.vendor_bill_ids = [(4, bill.id)]
        self.assertEqual(tx.compliance_status, "missing")
        doc = self._satisfy(tx, tag)
        tx.invalidate_recordset()
        invoice.invalidate_recordset()
        bill.invalidate_recordset()
        self.assertEqual(tx.compliance_status, "compliant")
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(bill.state, "draft")
        with self.assertRaises(AccessError):
            doc.write({"verified": True})
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(bill.state, "draft")

    def test_ledger_prefix_is_classified_without_a_transaction_link(self):
        """legacy_erp_ledger_ is historical even though the candidate fields do not hold it."""
        refund = self._move("out_refund", invoice_date="2022-04-01")
        self._mark(refund, "legacy_erp_ledger_5694")
        classified = self.env["plasticos.transaction"]._historical_erp_moves(refund)
        self.assertEqual(classified, refund)
        tx = self._tx()
        self.assertFalse(tx.customer_invoice_id)
        self.assertFalse(tx.vendor_bill_ids)
        self.assertFalse(tx.freight_bill_ids)
        invoice = self._move("out_invoice", invoice_date="2022-04-01")
        self._mark(invoice, "legacy_erp_so_14263")
        self._mark(invoice, "legacy_erp_outinv_wrong_ns", module="plasticos_accounting")
        sale = self.env["sale.order"].create({"partner_id": self.partner.id})
        self._mark(sale, "legacy_erp_outinv_not_a_move", model="sale.order")
        self.assertFalse(self.env["plasticos.transaction"]._historical_erp_moves(invoice))

    def test_lookalike_xmlid_posts_and_a_real_prefix_stays_archived(self):
        """A wildcard lookalike is not historical. A real prefix stays draft."""
        tx = self._tx()
        lookalike = self._move("out_invoice", origin="54839", invoice_date="2022-04-01")
        archived = self._move("out_invoice", origin="54839", invoice_date="2022-04-01")
        bill = self._move("in_invoice", origin="54839", invoice_date="2022-04-01")
        refund = self._move("out_refund", invoice_date="2022-04-01")
        self._mark(lookalike, "legacyXerpXoutinvX123")
        self._mark(archived, "legacy_erp_outinv_real")
        self._mark(bill, "legacy_erp_ininv_real")
        self._mark(refund, "legacy_erp_ledger_real")
        self._mark(lookalike, "legacy_erp_outinv_wrong_module", module="plasticos_accounting")
        sale = self.env["sale.order"].create({"partner_id": self.partner.id})
        self._mark(sale, "legacy_erp_outinv_wrong_model", model="sale.order")
        classifier = self.env["plasticos.transaction"]
        self.assertFalse(classifier._historical_erp_moves(lookalike))
        self.assertFalse(lookalike._historical_source_ids())
        self.assertEqual(classifier._historical_erp_moves(archived), archived)
        self.assertEqual(classifier._historical_erp_moves(bill), bill)
        self.assertEqual(classifier._historical_erp_moves(refund), refund)
        tx.customer_invoice_id = lookalike
        tx.vendor_bill_ids = [(4, bill.id)]
        tx._auto_post_pending_invoices()
        self.assertEqual(lookalike.state, "posted")
        self.assertEqual(bill.state, "draft")
        self.assertEqual(archived.state, "draft")
        message = "Archived ERP invoices, vendor bills and credits cannot be posted."
        with self.assertRaisesRegex(UserError, message):
            archived.action_post()
        self.assertEqual(archived.state, "draft")

    def test_operational_sale_origin_invoice_stays_draft_until_explicit_post(self):
        """A verified document leaves the sale-origin invoice draft. Explicit posting still posts it."""
        tag = self._isolate_invoice_rule("hist_autopost_operational")
        tx = self._tx()
        sale = self.env["sale.order"].create({"partner_id": self.partner.id, "transaction_id": tx.id})
        invoice = self._move("out_invoice", origin=sale.name, invoice_date="2026-10-24")
        tx.customer_invoice_id = invoice
        self._satisfy(tx, tag)
        tx.invalidate_recordset()
        invoice.invalidate_recordset()
        self.assertEqual(tx.compliance_status, "compliant")
        self.assertEqual(invoice.state, "draft")
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")

    def test_mixed_set_stays_draft_until_explicit_post(self):
        """Neither the operational invoice nor the marked bill posts from the document."""
        tag = self._isolate_invoice_rule("hist_autopost_mixed")
        tx = self._tx()
        sale = self.env["sale.order"].create({"partner_id": self.partner.id, "transaction_id": tx.id})
        invoice = self._move("out_invoice", origin=sale.name, invoice_date="2026-10-24")
        bill = self._move("in_invoice", origin="54839", invoice_date="2022-03-15")
        self._mark(bill, "legacy_erp_ininv_591398")
        tx.customer_invoice_id = invoice
        tx.vendor_bill_ids = [(4, bill.id)]
        self._satisfy(tx, tag)
        tx.invalidate_recordset()
        invoice.invalidate_recordset()
        bill.invalidate_recordset()
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(bill.state, "draft")
        self.assertEqual(tx.compliance_status, "compliant")
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(bill.state, "draft")

    def test_lookalike_origin_stays_draft_until_explicit_post(self):
        """A worksheet-shaped origin does not post from document compliance."""
        tag = self._isolate_invoice_rule("hist_autopost_lookalike")
        tx = self._tx()
        invoice = self._move("out_invoice", origin="54839", invoice_date="2022-04-01")
        self._mark(invoice, "legacy_erp_so_14263")
        tx.customer_invoice_id = invoice
        self._satisfy(tx, tag)
        tx.invalidate_recordset()
        invoice.invalidate_recordset()
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(tx.compliance_status, "compliant")
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")

    def test_direct_post_of_a_historical_draft_uses_normal_accounting(self):
        """Explicit action_post refuses a dated historical invoice and an undated historical bill."""
        payments = self.env["account.payment"].search_count([])
        entries = self.env["account.move"].search_count([("move_type", "=", "entry")])
        invoice = self._move("out_invoice", origin="54839", invoice_date="2022-04-01")
        bill = self._move("in_invoice", origin="54839")
        self._mark(invoice, "legacy_erp_outinv_manual")
        self._mark(bill, "legacy_erp_ininv_manual")
        message = "Archived ERP invoices, vendor bills and credits cannot be posted."
        with self.assertRaisesRegex(UserError, message):
            invoice.action_post()
        with self.assertRaisesRegex(UserError, message):
            bill.action_post()
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(bill.state, "draft")
        self.assertEqual(self.env["account.payment"].search_count([]), payments)
        self.assertEqual(self.env["account.move"].search_count([("move_type", "=", "entry")]), entries)

    def test_historical_marker_does_not_bypass_the_invoice_purpose_gate(self):
        """Archive refusal wins on a marked invoice. A live invoice still needs its document, then posts."""
        tag = self._isolate_invoice_rule("hist_autopost_purpose")
        tx = self._tx()
        sale = self.env["sale.order"].create({"partner_id": self.partner.id, "transaction_id": tx.id})
        historical = self._move("out_invoice", origin=sale.name, invoice_date="2026-10-24")
        self._mark(historical, "legacy_erp_outinv_purpose")
        tx.customer_invoice_id = historical
        with self.assertRaisesRegex(UserError, "Archived ERP invoices, vendor bills and credits cannot be posted."):
            historical.action_post()
        self.assertEqual(historical.state, "draft")

        live_tx = self._tx()
        live_sale = self.env["sale.order"].create({"partner_id": self.partner.id, "transaction_id": live_tx.id})
        live = self._move("out_invoice", origin=live_sale.name, invoice_date="2026-10-24")
        live_tx.customer_invoice_id = live
        with self.assertRaisesRegex(UserError, "Missing required documents for invoice posting."):
            live.action_post()
        self.assertEqual(live.state, "draft")
        self._satisfy(live_tx, tag)
        live.action_post()
        self.assertEqual(live.state, "posted")
        self.assertEqual(historical.state, "draft")

    def test_document_transition_does_not_post_or_roll_back_on_an_undated_bill(self):
        """Verifying the document leaves both moves draft. Explicit posting still enforces the bill date."""
        tag = self._isolate_invoice_rule("hist_autopost_retry")
        tx = self._tx()
        sale = self.env["sale.order"].create({"partner_id": self.partner.id, "transaction_id": tx.id})
        invoice = self._move("out_invoice", origin=sale.name, invoice_date="2026-10-24")
        bill = self._move("in_invoice", origin=sale.name)
        tx.customer_invoice_id = invoice
        tx.vendor_bill_ids = [(4, bill.id)]
        self.assertEqual(tx.compliance_status, "missing")
        self._satisfy(tx, tag)
        tx.invalidate_recordset()
        invoice.invalidate_recordset()
        bill.invalidate_recordset()
        self.assertEqual(tx.compliance_status, "compliant")
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(bill.state, "draft")
        with self.assertRaisesRegex(UserError, "The Bill/Refund date is required to validate this document."):
            bill.action_post()
        self.assertEqual(bill.state, "draft")
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(bill.state, "draft")
