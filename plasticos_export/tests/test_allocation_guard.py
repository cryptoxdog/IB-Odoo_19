"""The allocation guard of BRS-EXP-08-R006 on native Enterprise fixtures (S8, OP8-E01).

AC-EXP-08-006: one four-load PO has four traceable executed quantities, each
linked to a separate booking; a received load cannot be allocated twice; no
allocation exceeds the authoritative PO or SO line quantity; corrections and
splits are attributed and keep their history; and a second commitment that
slips past the command check is refused by the model and by the database.
"""

import psycopg2

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from ..models.booking import guard
from .native_fixture import PO_LOADS, SO_LOADS, NativeExportFixtureMixin
from .test_booking_and_revision import LINK

DOUBLE = "already committed on another live cargo link"


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestAllocationGuard(NativeExportFixtureMixin, PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_native_fixture()

    def _slots(self, count):
        booking, _revision = self.accepted_booking(confirmed=count)
        return booking.slot_ids.sorted("slot_key")

    def test_four_executed_loads_traced_to_four_bookings(self):
        """AC-EXP-08-006 (BRS-EXP-08-R006), positive: four executed PO quantities, four separate bookings."""
        links = self.env[LINK]
        for _week in range(PO_LOADS):
            received = self.receive_week()
            slot = self._slots(1)
            applied = self.commit_cargo(slot, self.stock_refs(received, sale_line_id=self.sale_line.id))
            self.assertEqual(applied["status"], "applied", applied)
            links |= self.env[LINK].browse(applied["record_id"])
        self.assertEqual(len(links.booking_id), PO_LOADS)
        self.assertEqual(len(links.stock_move_line_id), PO_LOADS)
        self.assertEqual(links.purchase_line_id, self.purchase_line)
        self.assertEqual(sum(links.mapped("planned_quantity")), self.purchase_line.qty_received)
        self.assertEqual(links.stock_move_line_id.picking_id, self.purchase.picking_ids)

    def test_received_load_cannot_be_allocated_twice(self):
        """AC-EXP-08-006 (BRS-EXP-08-R006), negative: the same stock quantity never satisfies two sales orders."""
        received = self.receive_week()
        first, second = self._slots(2)
        applied = self.commit_cargo(first, self.stock_refs(received, sale_line_id=self.sale_line.id))
        self.assertEqual(applied["status"], "applied", applied)
        other_sale = self.env["sale.order"].create(
            {
                "partner_id": self.buyer.id,
                "order_line": [(0, 0, {"product_id": self.load_product.id, "product_uom_qty": 5})],
            }
        )
        again = self.commit_cargo(second, self.stock_refs(received, sale_line_id=other_sale.order_line.id))
        self.assertEqual(again["status"], "blocked")
        self.assertIn(DOUBLE, again["reason"])
        # Same Logistics load, two containers: refused too.
        load = self.make_load()
        self.assertEqual(
            self.commit_cargo(
                first, {"source_load_id": load.id, "physical_source_kind": "logistics_load"}, None, False
            )["status"],
            "applied",
        )
        twice = self.commit_cargo(
            second, {"source_load_id": load.id, "physical_source_kind": "logistics_load"}, None, False
        )
        self.assertEqual(twice["status"], "blocked")
        self.assertIn("this load is " + DOUBLE, twice["reason"])
        # A released link frees its source for a new commitment.
        released = first.with_user(self.actor).action_release_cargo(
            applied["record_id"], first.booking_id.current_revision_id.id, self.key(), "wrong container"
        )
        self.assertEqual(released["status"], "applied")
        moved = self.commit_cargo(second, self.stock_refs(received, sale_line_id=other_sale.order_line.id))
        self.assertEqual(moved["status"], "applied", moved)

    def test_replaced_link_frees_its_source(self):
        """AC-EXP-08-006 (BRS-EXP-08-R006): a replaced link frees its load and move line; the indexes count live links."""
        received = self.receive_week()
        load = self.make_load()
        first, second = self._slots(2)
        refs = self.stock_refs(received, source_load_id=load.id)
        original = self.commit_cargo(first, refs)
        self.assertEqual(original["status"], "applied", original)
        moved = self.commit_cargo(
            second, {**refs, "replaces_link_id": original["record_id"], "correction_reason": "loaded on the other box"}
        )
        self.assertEqual(moved["status"], "applied", moved)
        links = self.env[LINK].browse([original["record_id"], moved["record_id"]])
        self.assertEqual(links.mapped("state"), ["released", "committed"])
        self.assertEqual(links[1].replaces_link_id, links[0])
        self.assertEqual((links.source_load_id, links.stock_move_line_id), (load, received))
        # The partial indexes exist and exclude exactly the non-live state the guard excludes.
        self.env.cr.execute(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = %s AND indexname LIKE %s",
            ("plasticos_export_booking_cargo_link", "%one_live_link_per%"),
        )
        definitions = dict(self.env.cr.fetchall())
        self.assertEqual(len(definitions), 2, definitions)
        for definition in definitions.values():
            self.assertIn("UNIQUE", definition)
            self.assertIn("'released'", definition)

    def test_planned_quantity_never_exceeds_the_order_line(self):
        """AC-EXP-08-006 (BRS-EXP-08-R006), negative: no allocation beyond the PO or SO line quantity."""
        slots = self._slots(3)
        po_refs = {"purchase_line_id": self.purchase_line.id}
        self.assertEqual(self.commit_cargo(slots[0], po_refs, PO_LOADS - 1)["status"], "applied")
        over = self.commit_cargo(slots[1], po_refs, 2.0)
        self.assertEqual(over["status"], "blocked")
        self.assertIn("would exceed the PO line quantity 4", over["reason"])
        self.assertEqual(self.commit_cargo(slots[1], po_refs, 1.0)["status"], "applied", "exactly the balance fits")
        so_refs = {"sale_line_id": self.sale_line.id}
        self.assertEqual(self.commit_cargo(slots[2], so_refs, SO_LOADS)["status"], "applied")
        so_over = self.commit_cargo(slots[2], so_refs, 1.0)
        self.assertEqual(so_over["status"], "blocked")
        self.assertIn("SO line quantity 30", so_over["reason"])
        # Units convert natively; a unit that does not convert to the line's unit is refused.
        dozen_over = self.commit_cargo(slots[0], po_refs, 1.0, self.env.ref("uom.product_uom_dozen"))
        self.assertEqual(dozen_over["status"], "blocked")
        self.assertIn("planned 16 Units would exceed", dozen_over["reason"])
        foreign_unit = self.commit_cargo(slots[0], po_refs, 1.0, self.lb)
        self.assertEqual(foreign_unit["status"], "blocked")
        self.assertIn("does not convert", foreign_unit["reason"])
        # An unknown planned quantity claims no number.
        self.assertEqual(self.commit_cargo(slots[0], po_refs, None, False)["status"], "applied")

    def test_commits_on_one_order_line_serialize_on_one_claim_row(self):
        """AC-EXP-08-006 (BRS-EXP-08-R006, review B3): every commit that plans on a PO or SO line bumps that
        line's one Export-owned claim row before it counts the line, so a concurrent second commit fails to
        serialize on that row and its retry sees the first one's quantity. No native row is written."""
        Claim = self.env["plasticos.export.source.line.claim"]
        first, second, third = self._slots(3)
        refs = {"purchase_line_id": self.purchase_line.id, "sale_line_id": self.sale_line.id}
        po_stamp = self.stamps(self.purchase, self.purchase_line, self.sale, self.sale_line)
        self.assertEqual(self.commit_cargo(first, refs, PO_LOADS - 1)["status"], "applied")
        po_claim = Claim.search([("purchase_line_id", "=", self.purchase_line.id)])
        so_claim = Claim.search([("sale_line_id", "=", self.sale_line.id)])
        self.assertEqual((len(po_claim), len(so_claim)), (1, 1))
        self.assertEqual((po_claim.claim_count, so_claim.claim_count), (1, 1))
        self.assertEqual(po_claim.company_id, self.company)
        over = self.commit_cargo(second, refs, 2.0)
        self.assertEqual(over["status"], "blocked", "the second commit counts the first one's 3 loads")
        self.assertIn("would exceed the PO line quantity 4", over["reason"])
        self.assertEqual(self.commit_cargo(third, refs, 1.0)["status"], "applied")
        po_claim.invalidate_recordset()
        so_claim.invalidate_recordset()
        # The same row each time: one row per line, bumped by every commit that planned on it.
        self.assertEqual(Claim.search([("purchase_line_id", "=", self.purchase_line.id)]), po_claim)
        self.assertEqual((po_claim.claim_count, so_claim.claim_count), (3, 3))
        self.assertEqual(self.stamps(self.purchase, self.purchase_line, self.sale, self.sale_line), po_stamp)
        # An unknown quantity claims no number, so it takes no claim.
        self.assertEqual(
            self.commit_cargo(first, {"purchase_line_id": self.purchase_line.id}, None, False)["status"], "applied"
        )
        po_claim.invalidate_recordset()
        self.assertEqual(po_claim.claim_count, 3)
        # The claim row is Export's own and written only by the command: the Export actor has no write right.
        self.assertFalse(Claim.with_user(self.actor).has_access("write"))

    def test_correction_and_split_are_attributed(self):
        """AC-EXP-08-006 (BRS-EXP-08-R006): corrections and splits write replaces_link_id and are attributed."""
        first, second, third = self._slots(3)
        po_refs = {"purchase_line_id": self.purchase_line.id}
        original = self.commit_cargo(first, po_refs, PO_LOADS)
        original_link = self.env[LINK].browse(original["record_id"])
        unexplained = self.commit_cargo(second, {**po_refs, "replaces_link_id": original_link.id}, 2.0)
        self.assertEqual(unexplained["status"], "blocked")
        self.assertIn("correction_reason", unexplained["reason"])
        reason = "two loads move to the second container"
        part_one = self.commit_cargo(
            second, {**po_refs, "replaces_link_id": original_link.id, "correction_reason": reason}, 2.0
        )
        self.assertEqual(part_one["status"], "applied", part_one)
        self.assertEqual(original_link.state, "released", "the replaced link is released, never edited")
        self.assertEqual(original_link.planned_quantity, PO_LOADS)
        part_two = self.commit_cargo(
            third, {**po_refs, "replaces_link_id": original_link.id, "correction_reason": reason}, 2.0
        )
        self.assertEqual(part_two["status"], "applied", part_two)
        note = first.booking_id.message_ids[:1]
        parts = self.env[LINK].browse([part_one["record_id"], part_two["record_id"]])
        self.assertEqual(parts.replaces_link_id, original_link)
        self.assertEqual(parts.create_uid, self.actor)
        self.assertIn(reason, note.body)
        self.assertIn(original_link.allocation_key, note.body)
        self.assertIn(self.actor.name, note.body)
        self.assertEqual(note.author_id, self.actor.partner_id)
        # The split may not over-allocate: the PO line is now fully planned.
        third_part = self.commit_cargo(
            first, {**po_refs, "replaces_link_id": original_link.id, "correction_reason": reason}, 1.0
        )
        self.assertEqual(third_part["status"], "blocked")
        # A plain release is history, not something to replace.
        released = self.commit_cargo(first, po_refs, None, False)
        first.with_user(self.actor).action_release_cargo(
            released["record_id"], first.booking_id.current_revision_id.id, self.key(), "not ready"
        )
        stray = self.commit_cargo(
            first,
            {"sale_line_id": self.sale_line.id, "replaces_link_id": released["record_id"], "correction_reason": "x"},
        )
        self.assertEqual(stray["status"], "blocked")
        self.assertIn("released, not replaced", stray["reason"])

    def test_correction_across_bookings_checks_the_other_booking(self):
        """AC-EXP-08-006 (BRS-EXP-08-R006, review N4): replacing cargo on another booking locks that booking
        and requires its current revision; a stale or missing revision changes nothing."""
        source_booking, source_revision = self.accepted_booking(confirmed=1)
        target_booking, _target_revision = self.accepted_booking(confirmed=1)
        refs = {"purchase_line_id": self.purchase_line.id}
        original = self.commit_cargo(source_booking.slot_ids, refs, 2.0)
        link = self.env[LINK].browse(original["record_id"])
        correction = {**refs, "replaces_link_id": link.id, "correction_reason": "moved to the next sailing"}
        missing = self.commit_cargo(target_booking.slot_ids, correction, 2.0)
        self.assertEqual(missing["status"], "stale", missing)
        self.assertEqual(link.state, "committed", "a stale correction releases nothing")
        roll = self.candidate(source_booking, terms=self.terms(confirmed=1, erd_local="2026-10-09 08:00"))
        self.assertEqual(
            self.accept(source_booking, roll["record_id"], expected=source_revision.id)["status"], "applied"
        )
        stale = self.commit_cargo(
            target_booking.slot_ids, {**correction, "replaced_booking_revision_id": source_revision.id}, 2.0
        )
        self.assertEqual(stale["status"], "stale", stale)
        self.assertEqual(link.state, "committed")
        current = source_booking.current_revision_id.id
        moved = self.commit_cargo(target_booking.slot_ids, {**correction, "replaced_booking_revision_id": current}, 2.0)
        self.assertEqual(moved["status"], "applied", moved)
        self.assertEqual(link.state, "released")
        self.assertEqual(self.env[LINK].browse(moved["record_id"]).replaces_link_id, link)

    def test_double_commit_past_the_command_is_refused(self):
        """AC-EXP-08-006 (BRS-EXP-08-R006): concurrency backstop: the model and a unique index refuse a twin."""
        received = self.receive_week()
        first, second = self._slots(2)
        applied = self.commit_cargo(first, self.stock_refs(received))
        link = self.env[LINK].browse(applied["record_id"])
        values = {
            "slot_id": second.id,
            "allocation_key": self.key("twin"),
            "state": "committed",
            "physical_source_kind": "native_stock",
            "stock_move_line_id": received.id,
        }
        with self.assertRaises(UserError), self.env.cr.savepoint():
            guard(self.env[LINK]).create(values)
        over = {**values, "stock_move_line_id": False, "physical_source_kind": "pending"}
        over.update(purchase_line_id=self.purchase_line.id, planned_quantity=PO_LOADS, planned_quantity_known=True)
        over["uom_id"] = self.unit.id
        with self.assertRaises(UserError), self.env.cr.savepoint():
            guard(self.env[LINK]).create(over)
        # A second transaction that never ran the ORM check meets the partial unique index.
        self.env.flush_all()
        with self.assertRaises(psycopg2.errors.UniqueViolation), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            self.env.cr.execute(
                """
                INSERT INTO plasticos_export_booking_cargo_link
                    (slot_id, company_id, allocation_key, state, physical_source_kind,
                     stock_move_line_id, planned_quantity_known)
                VALUES (%s, %s, %s, 'committed', 'native_stock', %s, false)
                """,
                (second.id, self.company.id, self.key("raw-twin"), link.stock_move_line_id.id),
            )
