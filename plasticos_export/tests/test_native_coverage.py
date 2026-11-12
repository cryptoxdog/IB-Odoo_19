"""Deferred Export rules witnessed on native Enterprise fixtures (S8, OP8-E02).

One test per rule; each docstring names its acceptance case. The native
fixture (``native_fixture.py``) builds a 30-load customer SO, two 4-load
supplier POs, weekly receipts with backorders, a partial delivery, a posted
invoice and a verified document through their native owners. Export only
commits planned cargo through its frozen commands; these witnesses prove it
writes none of the owners' facts. No outbound mail: Linda stays ``off``.
"""

import base64

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import new_test_user, tagged

from ..models.booking_allocation import slot_order
from .native_fixture import PO_LOADS, SO_LOADS, SUPPLIER_PRICE, NativeExportFixtureMixin
from .test_booking_and_revision import BOOKING, LINK, REVISION, SLOT

EXPORT_MODELS = (BOOKING, REVISION, SLOT, LINK)


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestNativeCoverage(NativeExportFixtureMixin, PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_native_fixture()

    def _export_field_names(self):
        return {
            name
            for model in EXPORT_MODELS
            for name, field in self.env[model]._fields.items()
            if field.store and not field.related
        }

    def test_single_fact_owner_export_stores_no_second_fact(self):
        """AC-EXP-01-002 (BRS-EXP-01-R002), negative: no second verified, stock, freight or mail fact in Export."""
        received = self.receive_week()
        load = self.make_load()
        verdict = self.verified_document(load)
        self.deliver()
        invoice = self.post_invoice()
        booking, _revision = self.accepted_booking(confirmed=2)
        mails = self.env["mail.mail"].search_count([])
        applied = self.commit_cargo(booking.slot_ids[0], self.stock_refs(received))
        self.assertEqual(applied["status"], "applied", applied)
        self.assertEqual(self.env["mail.mail"].search_count([]), mails, "Export sent mail outside Linda")
        # Positive: each fact is read from its one owner.
        link = self.env[LINK].browse(applied["record_id"])
        self.assertEqual(link.stock_move_line_id.quantity, 1.0)
        self.assertTrue(verdict.verified)
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(self.sale_line.qty_invoiced, 1.0)
        # Negative: no Export column stores a verdict, stock quantity, freight ledger, weight or mail.
        forbidden = ("verif", "qty_", "received", "delivered", "invoice", "freight", "weight", "mail_", "email")
        stored = self._export_field_names()
        self.assertFalse(sorted(name for name in stored if any(word in name for word in forbidden)), stored)

    def test_acceptance_writes_no_order_stock_or_load(self):
        """AC-EXP-01-004 (BRS-EXP-01-R004): accepting a booking revision writes no PO, SO, stock or load state."""
        received = self.receive_week()
        load = self.make_load()
        booking, first = self.accepted_booking(confirmed=2)
        self.assertEqual(
            self.commit_cargo(booking.slot_ids[0], self.stock_refs(received, source_load_id=load.id))["status"],
            "applied",
        )
        self.env.flush_all()
        pickings = self.sale.picking_ids | self.purchases.picking_ids
        watched = (
            self.sale,
            self.sale.order_line,
            self.purchases,
            self.purchases.order_line,
            pickings,
            pickings.move_ids,
            pickings.move_line_ids,
            self.sale.transaction_id,
            load,
        )
        before = self.stamps(*watched)
        moves_before = self.env["stock.move"].search_count([])
        roll = self.candidate(booking, terms=self.terms(confirmed=3, erd_local="2026-10-09 08:00"))
        self.assertEqual(self.accept(booking, roll["record_id"], expected=first.id)["status"], "applied")
        self.env.flush_all()
        self.assertEqual(self.stamps(*watched), before)
        self.assertEqual(self.env["stock.move"].search_count([]), moves_before)
        self.assertEqual(load.state, "draft")

    def test_stamps_detect_any_stored_field_write(self):
        """Self-test of the AC-EXP-01-004 / AC-EXP-02-006 witnesses: a non-state write is detected."""
        before = self.stamps(self.sale, self.sale_line, self.purchase, self.purchase_line)
        self.assertEqual(self.stamps(self.sale, self.sale_line, self.purchase, self.purchase_line), before)
        # Neither field is ``state`` and neither moves ``write_date`` inside this transaction.
        self.sale.note = "<p>S8 stamp self-test</p>"
        self.purchase.note = "<p>S8 stamp self-test</p>"
        after = self.stamps(self.sale, self.sale_line, self.purchase, self.purchase_line)
        self.assertNotEqual(after[("sale.order", self.sale.id)], before[("sale.order", self.sale.id)])
        self.assertNotEqual(after[("purchase.order", self.purchase.id)], before[("purchase.order", self.purchase.id)])

    def test_export_never_writes_an_order_incoterm(self):
        """AC-EXP-02-006 (BRS-EXP-02-R006), negative: a trade label is displayed, the order Incoterm never written."""
        fca = self.env.ref("account.incoterm_FCA")
        self.purchase.incoterm_id = fca
        self.purchase_line.name = "S8 MRP Regrind, FOB buyer pickup at mill"
        self.env.flush_all()
        watched = (self.purchase, self.purchase_line, self.sale, self.sale_line)
        stamp = self.stamps(*watched)
        booking, _revision = self.accepted_booking(confirmed=1)
        applied = self.commit_cargo(booking.slot_ids, {"purchase_line_id": self.purchase_line.id})
        self.assertEqual(applied["status"], "applied", applied)
        display = self.env[LINK].with_user(self.actor).browse(applied["record_id"]).po_constraint_display
        # Positive: the formal term and the industry label stay distinct, both read live.
        self.assertIn("Delivery terms: FCA", display)
        self.assertIn("FOB buyer pickup", display)
        self.env.flush_all()
        self.assertEqual(self.purchase.incoterm_id, fca)
        self.assertFalse(self.sale.incoterm)
        self.assertEqual(self.stamps(*watched), stamp)
        self.assertFalse([name for name in self._export_field_names() if "incoterm" in name])

    def test_company_and_audience_isolation_on_native_sources(self):
        """AC-EXP-06-001 (BRS-EXP-06-R001): no cross-company read, no supplier price in Export output."""
        received = self.receive_week()
        booking, _revision = self.accepted_booking(confirmed=1)
        applied = self.commit_cargo(booking.slot_ids, self.stock_refs(received))
        self.assertEqual(applied["status"], "applied", applied)
        # Company: the other company sees no booking, slot or link, and cannot read the native sources.
        foreign = self.foreign_actor
        for model in EXPORT_MODELS:
            self.assertFalse(self.env[model].with_user(foreign).search([("company_id", "=", self.company.id)]))
        for record in (self.purchase_line, received, self.sale):
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                record.with_user(foreign).check_access("read")
        # The internal claim row names company A's PO line: company B neither finds nor reads it (C08 OP8-E04).
        Claim = self.env["plasticos.export.source.line.claim"]
        claim = Claim.search([("purchase_line_id", "=", self.purchase_line.id)])
        self.assertEqual(len(claim), 1, "the committed planned quantity took its claim row")
        foreign_claims = Claim.with_user(foreign)
        self.assertFalse(foreign_claims.search([]))
        self.assertFalse(foreign_claims.search_read([], ["purchase_line_id", "sale_line_id", "company_id"]))
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            foreign_claims.browse(claim.id).read(["purchase_line_id", "sale_line_id", "company_id"])
        self.assertEqual(Claim.with_user(self.actor).search([("id", "=", claim.id)]), claim)
        refused = self.commit_cargo(booking.slot_ids, self.stock_refs(received), user=foreign, key=self.key())
        self.assertEqual(refused["status"], "not_available")
        # Audience: the forwarder-facing sheet and the PO display carry no supplier buy price.
        html = (
            self.env["ir.actions.report"]
            .with_user(self.actor)
            ._render_qweb_html("plasticos_export.report_booking_summary", booking.ids)[0]
            .decode()
        )
        link = self.env[LINK].with_user(self.actor).browse(applied["record_id"])
        for text in (html, link.po_constraint_display):
            for rendering in ("987.65", "987,65", "987.6", "988"):
                self.assertNotIn(rendering, text)
        self.assertEqual(self.purchase_line.price_unit, SUPPLIER_PRICE)
        # A Logistics reader without purchase rights sees that a PO exists, not its terms.
        reader = new_test_user(
            self.env,
            login="s8_logistics_reader",
            groups="base.group_user,plasticos_security_base.group_logistics",
            company_id=self.company.id,
            company_ids=[(6, 0, [self.company.id])],
        )
        self.assertFalse(reader.has_group("purchase.group_purchase_user"))
        self.assertEqual(
            self.env[LINK].with_user(reader).browse(applied["record_id"]).po_constraint_display,
            "PO not readable for your role.",
        )
        # Negative: that Export reader opens no native Documents original and no supplier invoice.
        original = self.env["documents.document"].create(
            {
                "name": "supplier-invoice-original.pdf",
                "datas": base64.b64encode(b"supplier invoice original"),
                "access_internal": "none",
                "company_id": self.company.id,
            }
        )
        self.purchase.action_create_invoice()
        bill = self.purchase.invoice_ids
        self.assertEqual(bill.move_type, "in_invoice")
        for record in (original, bill):
            with self.assertRaises(AccessError, msg=record._name), self.env.cr.savepoint():
                record.with_user(reader).check_access("read")

    def test_order_shipment_and_invoice_states_stay_scoped(self):
        """AC-EXP-06-003 (BRS-EXP-06-R003): one week's receipt keeps three PO loads and 29 SO loads open."""
        received = self.receive_week()
        self.deliver()
        self.post_invoice()
        booking, _revision = self.accepted_booking(confirmed=4)
        self.assertEqual(self.commit_cargo(booking.slot_ids[0], self.stock_refs(received))["status"], "applied")
        self.assertEqual(self.purchase_line.qty_received, 1.0)
        self.assertEqual(self.purchase.receipt_status, "partial")
        self.assertEqual(len(self._open_picking(self.purchase)), 1, "native backorder keeps the rest open")
        self.assertEqual(self._open_picking(self.purchase).move_ids.product_uom_qty, PO_LOADS - 1)
        self.assertEqual(self.sale_line.qty_delivered, 1.0)
        self.assertEqual(self.sale.delivery_status, "partial")
        self.assertEqual(self.sale_line.qty_invoiced, 1.0)
        self.assertEqual(self.sale_line.product_uom_qty - self.sale_line.qty_invoiced, SO_LOADS - 1)
        self.assertNotIn(self.sale.transaction_id.state, ("delivered", "invoiced", "closed"))
        # The second PO and its sibling loads are untouched.
        self.assertEqual(self.purchases[1].order_line.qty_received, 0.0)

    def test_slot_carries_no_payload_or_vgm(self):
        """AC-EXP-07-006 (BRS-EXP-07-R006), negative: 40HC never implies a payload, VGM or invoice weight."""
        booking, _revision = self.accepted_booking(confirmed=1)
        slot = booking.slot_ids
        self.assertEqual(slot.equipment_class, "40HC")
        words = ("payload", "vgm", "tare", "gross", "max_", "weight", "capacity")
        stored = self._export_field_names()
        self.assertFalse(sorted(name for name in stored if any(word in name for word in words)), stored)
        applied = self.commit_cargo(slot, {"sale_line_id": self.sale_line.id})
        link = self.env[LINK].browse(applied["record_id"])
        self.assertEqual((link.planned_quantity, link.uom_id), (1.0, self.unit), "only the stated planned quantity")
        self.assertFalse(self.sale.invoice_ids, "Export wrote no invoice")

    def test_one_customer_commitment_with_smaller_supplier_orders(self):
        """AC-EXP-08-002 (BRS-EXP-08-R002): one 30-load SO and 4-load supplier POs coexist natively."""
        self.assertEqual(self.sale_line.product_uom_qty, SO_LOADS)
        self.assertEqual(self.sale.partner_id, self.buyer)
        self.assertEqual(self.purchases.mapped("order_line.product_qty"), [PO_LOADS, PO_LOADS])
        self.assertEqual(self.purchases.partner_id, self.suppliers[:2])
        self.assertNotIn(self.buyer, self.purchases.partner_id, "the buyer PO is never the supplier PO")
        orders = (self.env["sale.order"].search_count([]), self.env["purchase.order"].search_count([]))
        booking, _revision = self.accepted_booking(confirmed=2)
        for week, slot in enumerate(booking.slot_ids.sorted(slot_order), start=1):
            received = self.receive_week()
            refs = self.stock_refs(received, sale_line_id=self.sale_line.id)
            self.assertEqual(self.commit_cargo(slot, refs)["status"], "applied", week)
        self.assertEqual(
            (self.env["sale.order"].search_count([]), self.env["purchase.order"].search_count([])),
            orders,
            "a weekly truck creates no new SO or PO",
        )

    def test_partial_purchase_fulfilment_through_native_backorders(self):
        """AC-EXP-08-003 (BRS-EXP-08-R003): four weekly receipts on one PO, each committed to cargo through
        Export; three remain after week 1, and Export issues no PO and keeps no receipt counter."""
        purchases_before = self.env["purchase.order"].search_count([])
        po_lines_before = self.env["purchase.order.line"].search_count([])
        booking, _revision = self.accepted_booking(confirmed=PO_LOADS)
        slots = booking.slot_ids.sorted(slot_order)
        for week, slot in enumerate(slots, start=1):
            received = self.receive_week()
            self.assertEqual(received.picking_id.state, "done")
            facts = (self.purchase_line.product_qty, self.purchase_line.qty_received, self.purchase_line.price_unit)
            stamp = self.stamps(self.purchase, self.purchase_line, self.purchase.picking_ids)
            applied = self.commit_cargo(slot, self.stock_refs(received))
            self.assertEqual(applied["status"], "applied", applied)
            # The commitment changed no PO, PO line or receipt row, and created no PO.
            self.assertEqual(self.stamps(self.purchase, self.purchase_line, self.purchase.picking_ids), stamp)
            self.assertEqual(
                (self.purchase_line.product_qty, self.purchase_line.qty_received, self.purchase_line.price_unit), facts
            )
            self.assertEqual(self.env["purchase.order"].search_count([]), purchases_before, week)
            self.assertEqual(self.env["purchase.order.line"].search_count([]), po_lines_before, week)
            remaining = self.purchase_line.product_qty - self.purchase_line.qty_received
            self.assertEqual(remaining, PO_LOADS - week)
            if week == 1:
                self.assertEqual(remaining, 3)
                self.assertEqual(self.purchase.receipt_status, "partial")
                self.assertEqual(len(self._open_picking(self.purchase)), 1, "native backorder, not a new PO")
        self.assertEqual(self.purchase.receipt_status, "full")
        self.assertEqual(len(self.purchase.picking_ids), PO_LOADS, "one native receipt per weekly load")
        links = self.env[LINK].search([("booking_id", "=", booking.id)])
        self.assertEqual(links.stock_move_line_id.picking_id, self.purchase.picking_ids)
        counters = ("qty_received", "qty_done", "received", "remaining", "backorder", "quantity_done")
        stored = self._export_field_names()
        self.assertFalse(sorted(name for name in stored if any(word in name for word in counters)), stored)

    def test_partial_sale_fulfilment_and_unvalidated_booking_association(self):
        """AC-EXP-08-004 (BRS-EXP-08-R004): one shipment leaves 29 loads open; committing a reserved,
        not yet delivered move line to a booking validates no picking and changes no reservation."""
        self.receive_week()
        self.receive_week()
        self.deliver()
        self.assertEqual(self.sale_line.qty_delivered, 1.0)
        self.assertEqual(self.sale_line.product_uom_qty - self.sale_line.qty_delivered, SO_LOADS - 1)
        delivery = self._open_picking(self.sale)
        delivery.action_assign()
        self.assertEqual(delivery.state, "assigned", "the backorder holds the second received load")
        reserved = delivery.move_line_ids
        self.assertEqual(len(reserved), 1)
        self.assertEqual(reserved.quantity, 1.0)
        facts = (delivery.state, delivery.move_ids.quantity, reserved.quantity, self.sale_line.qty_delivered)
        stamp = self.stamps(self.sale, self.sale_line, delivery, delivery.move_ids, reserved)
        booking, _revision = self.accepted_booking(confirmed=1)
        applied = self.commit_cargo(
            booking.slot_ids,
            {
                "sale_line_id": self.sale_line.id,
                "stock_move_line_id": reserved.id,
                "physical_source_kind": "native_stock",
            },
        )
        self.assertEqual(applied["status"], "applied", applied)
        self.assertEqual(self.stamps(self.sale, self.sale_line, delivery, delivery.move_ids, reserved), stamp)
        self.assertEqual(
            (delivery.state, delivery.move_ids.quantity, reserved.quantity, self.sale_line.qty_delivered), facts
        )
        self.assertEqual(self.sale_line.product_uom_qty - self.sale_line.qty_delivered, SO_LOADS - 1)

    def test_no_direct_state_write_on_load_or_transaction(self):
        """AC-EXP-09-007 (BRS-EXP-09-R007), negative: no direct load or transaction state write."""
        load = self.make_load()
        transaction = self.sale.transaction_id
        self.assertTrue(transaction, "SO confirmation compiles the transaction")
        booking, _revision = self.accepted_booking(confirmed=1)
        received = self.receive_week()
        self.assertEqual(
            self.commit_cargo(booking.slot_ids, self.stock_refs(received, source_load_id=load.id))["status"],
            "applied",
        )
        for record, state in ((load, "delivered"), (transaction, "delivered"), (transaction, "invoiced")):
            for user in (self.actor, self.env.user):
                with self.assertRaises(UserError, msg=f"{record._name} {state}"), self.env.cr.savepoint():
                    record.with_user(user).write({"state": state})
        self.assertEqual(load.state, "draft")
        self.assertNotIn(transaction.state, ("delivered", "invoiced"))
        # Other PO loads stay open: native receipt of one load is not PO fulfilment.
        self.assertEqual(self.purchase_line.product_qty - self.purchase_line.qty_received, PO_LOADS - 1)

    def test_shipment_guard_and_native_po_remaining_balance(self):
        """AC-EXP-11-010 (BRS-EXP-11-R010): one recognised load; the PO keeps its native remaining balance."""
        received = self.receive_week()
        booking, _revision = self.accepted_booking(confirmed=PO_LOADS)
        slots = booking.slot_ids.sorted(slot_order)
        self.assertEqual(self.commit_cargo(slots[0], self.stock_refs(received))["status"], "applied")
        self.assertEqual(self.purchase_line.qty_received, 1.0)
        self.assertEqual(self.purchase_line.product_qty - self.purchase_line.qty_received, PO_LOADS - 1)
        self.assertNotEqual(self.purchase.receipt_status, "full")
        self.assertFalse(self.sale.invoice_ids, "no sale invoice posts from a shipment")
        self.assertEqual(slots[1:].mapped("allocation_state"), ["available"] * (PO_LOADS - 1))
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.sale.transaction_id.with_user(self.actor).write({"state": "closed"})
