"""Export display alignment (C13 OP12-E02).

(a) The cargo allocation pivot never adds planned quantities across units:
    ``planned_quantity`` has no aggregator, and the pivot measure is the planned
    weight in lb converted through the native unit of measure. A unit that is
    not a weight is excluded and flagged by its weight basis.
(b) Slots order numerically: ``40HC-10`` follows ``40HC-9`` in ``_order``, in
    the slot commands and in the legacy report.
(c) The Commit Cargo screen defaults the planned unit to lb.
(d) ``supplier_count`` is the same for every reader, consistent with the
    operator's see-all rule for cargo allocations (S7, 2026-11-12).
"""

from lxml import etree

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import new_test_user, tagged

from ..models.booking_allocation import (
    WEIGHT_BASIS_NOT_WEIGHT,
    WEIGHT_BASIS_UNKNOWN,
    WEIGHT_BASIS_WEIGHT,
    slot_order,
)
from .test_booking_and_revision import LINK, ExportFixtureMixin

COMMIT = "plasticos.export.slot.commit.cargo"
SLOT = "plasticos.export.booking.slot"


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestDisplayAlignment(ExportFixtureMixin, PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_export_fixture()
        cls.kg = cls.env.ref("uom.product_uom_kgm")
        cls.ton = cls.env.ref("uom.product_uom_ton")
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.short_ton = cls.env["uom.uom"].create(
            {"name": "S12 Short Ton", "relative_uom_id": cls.lb.id, "relative_factor": 2000.0}
        )
        rep_groups = "base.group_user,plasticos_security_base.group_sales_rep"
        cls.rep = new_test_user(
            cls.env,
            login="s12_display_rep",
            groups=rep_groups,
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )

    def _po_line(self, supplier=None, quantity=200000, unit=None):
        order = self.env["purchase.order"].create(
            {
                "partner_id": (supplier or self.suppliers[0]).id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": quantity,
                            "product_uom_id": (unit or self.lb).id,
                        },
                    )
                ],
            }
        )
        return order.order_line

    def _commit(self, slot, revision, quantity=None, unit=None, supplier=None):
        # A PO line kept in Units carries a Units quantity; a weight unit plans on a pound line (S8 guard).
        line_unit = unit if unit == self.unit else None
        outcome = slot.with_user(self.actor).action_commit_cargo(
            {"purchase_line_id": self._po_line(supplier, unit=line_unit).id},
            quantity,
            unit.id if unit else None,
            revision.id,
            self.key("s12"),
        )
        self.assertEqual(outcome["status"], "applied", outcome)
        return self.env[LINK].browse(outcome["record_id"])

    # ── (a) pivot ────────────────────────────────────────────

    def test_e02a_planned_quantity_has_no_cross_unit_aggregate(self):
        """OP12-E02a: planned_quantity offers no sum; the pivot measure is the lb weight, split by weight basis."""
        description = self.env[LINK].fields_get(["planned_quantity", "planned_weight_lb"], ["aggregator"])
        self.assertFalse(description["planned_quantity"].get("aggregator"), "no sum across units")
        self.assertEqual(description["planned_weight_lb"].get("aggregator"), "sum")
        pivot = etree.fromstring(self.env.ref("plasticos_export.view_export_cargo_link_pivot").arch)
        measures = [node.get("name") for node in pivot.iter("field") if node.get("type") == "measure"]
        self.assertEqual(measures, ["planned_weight_lb"])
        self.assertIn("planned_weight_basis", [node.get("name") for node in pivot.iter("field")])
        self.assertNotIn("planned_quantity", measures)

    def test_e02a_lb_weight_converts_kg_lb_ton_and_short_ton(self):
        """OP12-E02a positive: every weight unit converts to lb and the pound total is their true sum."""
        booking, revision = self.accepted_booking(confirmed=4)
        slots = booking.slot_ids.sorted(slot_order)
        # Odoo 19 uom data: 1 lb = 16 oz x 28.3495 g = 453.592 g, so 1 kg = 2.2046244 lb.
        cases = [(self.lb, 40000, 40000.0), (self.kg, 1000, 2204.62442), (self.ton, 10, 22046.2442)]
        cases.append((self.short_ton, 20, 40000.0))
        links = self.env[LINK]
        for slot, (unit, quantity, pounds) in zip(slots, cases):
            link = self._commit(slot, revision, quantity, unit)
            self.assertEqual(link.planned_weight_basis, WEIGHT_BASIS_WEIGHT, unit.name)
            self.assertAlmostEqual(link.planned_weight_lb, pounds, places=2, msg=unit.name)
            links |= link
        ((total,),) = self.env[LINK]._read_group([("id", "in", links.ids)], [], ["planned_weight_lb:sum"])
        self.assertAlmostEqual(total, sum(pounds for _u, _q, pounds in cases), places=2)

    def test_e02a_negative_non_weight_unit_is_excluded_and_flagged(self):
        """OP12-E02a negative: a quantity in Units adds nothing to the lb total and says why; unknown says unknown."""
        booking, revision = self.accepted_booking(confirmed=3)
        first, second, third = booking.slot_ids.sorted(slot_order)
        weighed = self._commit(first, revision, 40000, self.lb)
        counted = self._commit(second, revision, 12, self.unit)
        unknown = self._commit(third, revision)
        self.assertEqual((counted.planned_weight_lb, counted.planned_weight_basis), (0.0, WEIGHT_BASIS_NOT_WEIGHT))
        self.assertEqual((unknown.planned_weight_lb, unknown.planned_weight_basis), (0.0, WEIGHT_BASIS_UNKNOWN))
        rows = self.env[LINK]._read_group(
            [("booking_id", "=", booking.id)], ["planned_weight_basis"], ["planned_weight_lb:sum"]
        )
        by_basis = dict(rows)
        self.assertEqual(by_basis[WEIGHT_BASIS_WEIGHT], 40000.0)
        self.assertEqual(by_basis[WEIGHT_BASIS_NOT_WEIGHT], 0.0, "Units are visible in their own column, not summed")
        self.assertEqual(weighed.planned_weight_lb, 40000.0)

    # ── (b) numeric slot order ───────────────────────────────

    def test_e02b_twelve_slots_order_one_to_twelve(self):
        """OP12-E02b positive: slot 10 follows slot 9 in the model order and in every sort helper."""
        booking, _revision = self.accepted_booking(confirmed=12)
        expected = [f"40HC-{number}" for number in range(1, 13)]
        self.assertEqual(booking.slot_ids.mapped("slot_key"), expected, "the One2many reads in _order")
        self.assertEqual(self.env[SLOT].search([("booking_id", "=", booking.id)]).mapped("slot_key"), expected)
        self.assertEqual(booking.slot_ids.sorted(slot_order).mapped("slot_key"), expected)
        self.assertEqual(booking.slot_ids.mapped("slot_number"), list(range(1, 13)))

    def test_e02b_negative_string_order_would_misplace_slot_ten(self):
        """OP12-E02b negative: plain key order is the defect being fixed (10, 11, 12 before 2)."""
        booking, _revision = self.accepted_booking(confirmed=12)
        by_string = booking.slot_ids.sorted("slot_key").mapped("slot_key")
        self.assertEqual(by_string[:4], ["40HC-1", "40HC-10", "40HC-11", "40HC-12"])
        self.assertNotEqual(by_string, booking.slot_ids.mapped("slot_key"))

    def test_e02b_reduction_retires_the_highest_numbered_free_slot(self):
        """OP12-E02b: capacity 12 → 10 retires slots 12 and 11, not 9 and 8 (string order would)."""
        booking, _revision = self.accepted_booking(confirmed=12)
        roll = self.candidate(booking, terms=self.terms(confirmed=10, erd_local="2026-10-09 08:00"))
        self.assertEqual(
            self.accept(booking, roll["record_id"], expected=booking.current_revision_id.id)["status"], "applied"
        )
        self.assertEqual(booking.slot_ids.mapped("slot_key"), [f"40HC-{number}" for number in range(1, 11)])

    # ── (c) lb default ───────────────────────────────────────

    def test_e02c_commit_screen_defaults_the_unit_to_lb(self):
        """OP12-E02c: the planned unit defaults to lb; the commit records lb."""
        booking, revision = self.accepted_booking(confirmed=1)
        slot = booking.slot_ids
        action = slot.with_user(self.actor).action_open_commit_cargo()
        screen = (
            self.env[COMMIT]
            .with_user(self.actor)
            .with_context(**action["context"])
            .create({"purchase_line_id": self._po_line().id, "planned_quantity_known": True, "planned_quantity": 4})
        )
        self.assertEqual(screen.uom_id, self.lb)
        screen.action_confirm()
        link = self.env[LINK].search([("slot_id", "=", slot.id)])
        self.assertEqual((link.uom_id, link.planned_weight_lb), (self.lb, 4.0))
        self.assertEqual(link.booking_id.current_revision_id, revision)

    # ── (d) supplier_count and see-all ───────────────────────

    def test_e02d_supplier_count_is_the_same_for_every_reader(self):
        """OP12-E02d: a Sales Rep sees the slot's full supplier count, the count Logistics sees (S7 see-all)."""
        booking, revision = self.accepted_booking(confirmed=1)
        slot = booking.slot_ids
        self._commit(slot, revision, supplier=self.suppliers[0])
        self._commit(slot, revision, supplier=self.suppliers[1])
        self._commit(slot, revision, supplier=self.suppliers[1])
        self.env.invalidate_all()
        as_logistics = self.env[SLOT].with_user(self.actor).browse(slot.id).supplier_count
        as_rep = self.env[SLOT].with_user(self.rep).browse(slot.id).supplier_count
        self.assertEqual((as_logistics, as_rep), (2, 2), "two distinct suppliers, counted once each, for both")
        self.assertEqual(
            self.env[SLOT].with_user(self.rep).search_count([("id", "=", slot.id), ("supplier_count", "=", 2)]), 1
        )
