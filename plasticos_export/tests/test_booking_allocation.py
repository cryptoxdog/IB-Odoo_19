"""Slot capacity, cargo links and container binding (RP-07-E059).

E3/E4 of TECHNICAL_CONTRACT_v2.7: true slot count, two feeders on one slot,
concurrent commitments, planned-only quantities in native US units, journey
binding and the Logistics release hold. No outbound mail.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .test_booking_and_revision import LINK, SLOT, ExportFixtureMixin


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestBookingAllocation(ExportFixtureMixin, PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_export_fixture()

    def _po_line(self, supplier, qty=40000):
        order = self.env["purchase.order"].create(
            {
                "partner_id": supplier.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": qty, "product_uom_id": self.lb.id})
                ],
            }
        )
        return order.order_line

    def _commit(self, slot, refs, quantity=None, uom=None, key=None, expected=None, user=None):
        expected = expected if expected is not None else slot.booking_id.current_revision_id.id
        return slot.with_user(user or self.actor).action_commit_cargo(
            refs, quantity, uom.id if uom else None, expected, key or self.key("commit")
        )

    def _journey(self, equipment="40HC", iso="MSKU1234565", company=None, cycle=None):
        # Another company's journey is registered by Logistics of that company, here the superuser.
        Journey = self.env["plasticos.iso.journey"]
        Journey = Journey.sudo() if company else Journey.with_user(self.actor)
        outcome = Journey.action_register_iso_journey(
            (company or self.company).id, cycle or self.key("iso-cycle"), equipment, False, iso, "SEAL-1", self.key()
        )
        self.assertEqual(outcome["status"], "applied", outcome)
        return self.env["plasticos.iso.journey"].browse(outcome["record_id"])

    def test_phase1_gate_five_40hc_four_supplier_pos(self):
        """BRS-EXP-14-R014, BRS-EXP-14-R015, BRS-EXP-08-R005, BRS-EXP-13-R005: capacity is distinct slots, not links."""
        booking, _revision = self.accepted_booking(confirmed=5)
        slots = booking.slot_ids.sorted("slot_key")
        lines = [self._po_line(supplier) for supplier in self.suppliers]
        # Two feeder POs into the first container, then one PO each for the next two.
        for slot, line in zip([slots[0], slots[0], slots[1], slots[2]], lines):
            outcome = self._commit(slot, {"purchase_line_id": line.id}, 40000, self.lb)
            self.assertEqual(outcome["status"], "applied", outcome)
        self.assertEqual(booking.slot_confirmed_count, 5)
        self.assertEqual(booking.slot_committed_count, 3)
        self.assertEqual(booking.slot_available_count, 2)
        self.assertEqual(slots[0].supplier_count, 2)
        self.assertEqual(len(slots[0].cargo_link_ids), 2)
        links = self.env[LINK].search([("booking_id", "=", booking.id)])
        self.assertEqual(len(links), 4)
        self.assertEqual(set(links.mapped("supplier_id")), set(self.suppliers))
        self.assertEqual(set(links.mapped("uom_id")), {self.lb})

    def test_commit_replay_and_stale_revision(self):
        """V05, BRS-EXP-14-R016: one allocation key, one commitment; a moved revision is stale."""
        booking, first = self.accepted_booking(confirmed=2)
        slot = booking.slot_ids[0]
        line = self._po_line(self.suppliers[0])
        args = ({"purchase_line_id": line.id}, 1000.0, self.lb)
        applied = self._commit(slot, *args, key="alloc-1")
        again = self._commit(slot, *args, key="alloc-1")
        self.assertEqual(again, {"status": "already_applied", "record_id": applied["record_id"]})
        different = self._commit(slot, {"purchase_line_id": line.id}, 2000.0, self.lb, key="alloc-1")
        self.assertEqual(different["status"], "stale")
        roll = self.candidate(booking, terms=self.terms(confirmed=2, erd_local="2026-10-09 08:00"))
        self.assertEqual(self.accept(booking, roll["record_id"], expected=first.id)["status"], "applied")
        stale = self._commit(slot, {"purchase_line_id": line.id}, None, None, expected=first.id)
        self.assertEqual(stale["status"], "stale")

    def test_quantity_is_planned_only_in_native_units(self):
        """Operator units decision 2026-11-11, BRS-EXP-08-R005: native uom.uom lb; unknown is not zero."""
        booking, _revision = self.accepted_booking(confirmed=1)
        slot = booking.slot_ids
        line = self._po_line(self.suppliers[0])
        no_unit = self._commit(slot, {"purchase_line_id": line.id}, 500.0, None)
        self.assertEqual(no_unit, {"status": "blocked", "reason": "a known planned quantity needs its unit"})
        negative = self._commit(slot, {"purchase_line_id": line.id}, -5.0, self.lb)
        self.assertEqual(negative["status"], "blocked")
        unknown = self._commit(slot, {"purchase_line_id": line.id}, None, None)
        link = self.env[LINK].browse(unknown["record_id"])
        self.assertFalse(link.planned_quantity_known)
        self.assertEqual(link.planned_quantity, 0.0)
        self.assertFalse(link.uom_id)
        self.assertEqual(self.lb.name, "lb")
        self.assertFalse(
            self.env["ir.model.data"].search_count([("module", "=", "plasticos_export"), ("model", "=", "uom.uom")])
        )

    def test_sources_must_be_exact_and_same_company(self):
        """BRS-EXP-06-R002, BRS-EXP-14-R015: exact native sources only, never another company's."""
        booking, _revision = self.accepted_booking(confirmed=1)
        slot = booking.slot_ids
        nothing = self._commit(slot, {})
        self.assertEqual(nothing["status"], "blocked")
        foreign_order = (
            self.env["purchase.order"]
            .sudo()
            .create(
                {
                    "partner_id": self.suppliers[0].id,
                    "company_id": self.company_b.id,
                    "order_line": [(0, 0, {"product_id": self.product.id, "product_qty": 10})],
                }
            )
        )
        foreign = self._commit(slot, {"purchase_line_id": foreign_order.order_line.id})
        self.assertEqual(foreign["status"], "blocked")
        kind_without_subject = self._commit(
            slot, {"purchase_line_id": self._po_line(self.suppliers[1]).id, "physical_source_kind": "logistics_load"}
        )
        self.assertEqual(kind_without_subject["status"], "blocked")
        self.assertIn("source_load_id", kind_without_subject["reason"])

    def test_release_frees_the_slot_and_keeps_history(self):
        """BRS-EXP-14-R016: release is explicit, reasoned and audited; the link stays."""
        booking, revision = self.accepted_booking(confirmed=1)
        slot = booking.slot_ids
        applied = self._commit(slot, {"purchase_line_id": self._po_line(self.suppliers[0]).id})
        self.assertEqual(slot.allocation_state, "committed")
        no_reason = slot.with_user(self.actor).action_release_cargo(applied["record_id"], revision.id, self.key(), "")
        self.assertEqual(no_reason["status"], "blocked")
        released = slot.with_user(self.actor).action_release_cargo(
            applied["record_id"], revision.id, self.key(), "Supplier not ready"
        )
        self.assertEqual(released["status"], "applied")
        self.assertEqual(slot.allocation_state, "available")
        link = self.env[LINK].browse(applied["record_id"])
        self.assertEqual(link.state, "released")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            link.with_user(self.actor).unlink()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            link.with_user(self.actor).write({"state": "committed"})
        self.assertIn("Supplier not ready", booking.message_ids[:1].body)

    def test_journey_binding_is_exact_and_exclusive(self):
        """BRS-EXP-07-R004, BRS-EXP-07-R007, BRS-EXP-07-R008: one container per active slot; mismatch reported."""
        booking, revision = self.accepted_booking(confirmed=2)
        first, second = booking.slot_ids.sorted("slot_key")
        mismatch = first.with_user(self.actor).action_bind_journey(
            self._journey(equipment="20STD", iso="MSKU7654326").id, revision.id, self.key(), "in-gate receipt"
        )
        self.assertEqual(mismatch["status"], "blocked")
        self.assertIn("equipment mismatch", mismatch["reason"])
        journey = self._journey()
        no_basis = first.with_user(self.actor).action_bind_journey(journey.id, revision.id, self.key(), "")
        self.assertEqual(no_basis["status"], "blocked")
        bound = first.with_user(self.actor).action_bind_journey(journey.id, revision.id, self.key(), "in-gate receipt")
        self.assertEqual(bound["status"], "applied")
        self.assertEqual(first.iso_number, "MSKU1234565")
        self.assertEqual(first.seal_number, "SEAL-1")
        replay = first.with_user(self.actor).action_bind_journey(journey.id, revision.id, self.key(), "again")
        self.assertEqual(replay["status"], "already_applied")
        taken = second.with_user(self.actor).action_bind_journey(journey.id, revision.id, self.key(), "duplicate")
        self.assertEqual(taken["status"], "blocked")
        foreign = self._journey(company=self.company_b, iso="MSKU1111110")
        other_company = second.with_user(self.actor).action_bind_journey(foreign.id, revision.id, self.key(), "x")
        self.assertIn(other_company["status"], ("blocked", "not_available"))
        self.assertEqual(
            self.env[SLOT].search_count([("journey_id", "=", journey.id), ("journey_binding_state", "=", "active")]), 1
        )

    def test_held_slot_withholds_its_load_from_new_physical_instructions(self):
        """BRS-EXP-11-R011, BRS-EXP-10-R001, BRS-EXP-10-R005: a downsize holds the impacted load only."""
        booking, first = self.accepted_booking(confirmed=2)
        slot_a, slot_b = booking.slot_ids.sorted("slot_key")
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        load_a = self.env["plasticos.load"].create({"sale_order_id": order.id})
        load_b = self.env["plasticos.load"].create({"sale_order_id": order.id})
        for slot, load in ((slot_a, load_a), (slot_b, load_b)):
            outcome = self._commit(
                slot, {"source_load_id": load.id, "physical_source_kind": "logistics_load"}, 40000, self.lb
            )
            self.assertEqual(outcome["status"], "applied", outcome)
        Load = self.env["plasticos.load"]
        self.assertEqual(Load.assert_can_release_physical_operation(load_a.id, "dispatch")["status"], "applied")
        down = self.candidate(booking, terms=self.terms(confirmed=1))
        self.assertEqual(self.accept(booking, down["record_id"], expected=first.id)["status"], "applied")
        held = Load.assert_can_release_physical_operation(load_b.id, "dispatch")
        self.assertEqual(held["status"], "blocked")
        self.assertIn("is held", held["reason"])
        self.assertEqual(Load.assert_can_release_physical_operation(load_a.id, "schedule")["status"], "applied")

    def test_po_constraints_are_read_live_never_copied(self):
        """BRS-EXP-11-R007 (C05 E4): the PO line stays the authority; Export copies no financial value."""
        booking, _revision = self.accepted_booking(confirmed=1)
        line = self._po_line(self.suppliers[0], qty=42000)
        line.order_id.incoterm_id = self.env.ref("account.incoterm_FCA", raise_if_not_found=False) or False
        applied = self._commit(booking.slot_ids, {"purchase_line_id": line.id})
        link = self.env[LINK].browse(applied["record_id"]).with_user(self.actor)
        self.assertIn("Quantity: 42000 lb", link.po_constraint_display)
        self.assertIn(line.order_id.name, link.po_constraint_display)
        self.assertIn("S5B HDPE Regrind", link.po_constraint_display)
        line.product_qty = 38000
        link.invalidate_recordset()
        self.assertIn("Quantity: 38000 lb", link.po_constraint_display)
        self.assertFalse(link._fields["po_constraint_display"].store)
        exported = self.env["ir.model.fields"].search([("model", "=like", "plasticos.export.%")]).mapped("name")
        self.assertFalse([name for name in exported if "price" in name or "amount" in name or "cost" in name])
