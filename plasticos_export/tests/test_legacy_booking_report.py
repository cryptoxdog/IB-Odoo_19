"""The 43-column legacy booking report as a conformance fixture (S10 OP10-E04, BRS-EXP-14-R011).

The fixture ``data/synthetic_booking_report.xlsx`` is synthetic: its generator
``data/generate_synthetic_booking_report.py`` invents every value and never
opens the private original. The test inventories the 43 headings, mirrors the
synthetic bookings through the frozen Export commands, and compares the
projection's booking grouping and its explicit missing/unknown cells with the
workbook. The projection only reads: no booking, stock, invoice or document
record is written by it.
"""

import csv
from collections import Counter

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged
from odoo.tools.misc import file_open

from ..models.legacy_report import (
    LEGACY_BOOKING_REPORT_COLUMNS,
    LEGACY_BOOKING_REPORT_HEADINGS,
    MISSING,
    NOT_MAPPED,
    UNASSIGNED_BUYER,
    UNKNOWN,
)
from ..models.owner_facts import NO_CONTAINER_BOUND
from .test_booking_and_revision import LINK, ExportFixtureMixin

WORKBOOK = "plasticos_export/tests/data/synthetic_booking_report.xlsx"
INVENTORY = "plasticos_export/tests/data/booking_report_heading_inventory.csv"


def _workbook_rows():
    import openpyxl  # noqa: PLC0415 - Odoo ships openpyxl; imported only by this test

    with file_open(WORKBOOK, "rb") as handle:
        sheet = openpyxl.load_workbook(handle, read_only=True).active
        rows = [
            tuple("" if value is None else str(value) for value in row) for row in sheet.iter_rows(values_only=True)
        ]
    return rows[0], [dict(zip(rows[0], row)) for row in rows[1:]]


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestLegacyBookingReport(ExportFixtureMixin, PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_export_fixture()

    def test_14_r011_all_43_headings_are_inventoried(self):
        """BRS-EXP-14-R011: the workbook, the inventory and the projection carry the same 43 headings in order."""
        headings, rows = _workbook_rows()
        with file_open(INVENTORY) as handle:
            inventory = [row["legacy_heading"] for row in csv.DictReader(handle)]
        self.assertEqual(len(headings), 43)
        self.assertEqual(list(headings), inventory)
        self.assertEqual(tuple(inventory), LEGACY_BOOKING_REPORT_HEADINGS)
        self.assertEqual(len(set(inventory)), 43)
        self.assertTrue(rows)
        for row in rows:
            for value in row.values():
                self.assertFalse(value and not self._synthetic(value), f"non-synthetic value {value!r}")
        statuses = {status for _heading, _owner, status in LEGACY_BOOKING_REPORT_COLUMNS}
        self.assertLessEqual(statuses, {"mapped", "not_recorded", "requires_owner_proof", "phase_2"})

    @staticmethod
    def _synthetic(value):
        """Every fixture value is invented: a SYN prefix, the word Synthetic, a synthetic place or a 2030 date."""
        return value.startswith(("SYN", "SV", "Synthetic", "Port ", "synthetic.")) or value.startswith("2030-")

    def _mirror(self, rows):
        """Each synthetic booking through the frozen commands; one cargo link per workbook row."""
        by_booking = {}
        for row in rows:
            by_booking.setdefault(row["Booking No"], []).append(row)
        for number, booking_rows in by_booking.items():
            first = booking_rows[0]
            extra = {"ets": first["ETS"]} if first["ETS"] else {}
            terms = self.terms(
                confirmed=len(booking_rows), number=number, pod_text=first["POD"] or None, additional_terms=extra
            )
            booking = self.make_booking()
            recorded = self.candidate(booking, terms=terms)
            self.assertEqual(recorded["status"], "applied", recorded)
            self.assertEqual(self.accept(booking, recorded["record_id"])["status"], "applied")
            for slot, row in zip(booking.slot_ids.sorted("slot_key"), booking_rows):
                purchase = self.env["purchase.order"].create(
                    {
                        "partner_id": self.suppliers[0].id,
                        "order_line": [(0, 0, {"product_id": self.product.id, "product_qty": 1})],
                    }
                )
                refs = {"purchase_line_id": purchase.order_line.id}
                if row["Customer"]:
                    sale = self.env["sale.order"].create(
                        {
                            "partner_id": self.buyer.id,
                            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1})],
                        }
                    )
                    refs["sale_line_id"] = sale.order_line.id
                outcome = slot.with_user(self.actor).action_commit_cargo(
                    refs, None, None, booking.current_revision_id.id, self.key("legacy")
                )
                self.assertEqual(outcome["status"], "applied", outcome)

    def test_14_r011_grouping_and_explicit_missing_or_unknown(self):
        """BRS-EXP-14-R011 positive: booking grouping matches; missing POD, ETS or buyer is explicit."""
        _headings, rows = _workbook_rows()
        self._mirror(rows)
        numbers = sorted({row["Booking No"] for row in rows})
        groups = (
            self.env[LINK]
            .with_user(self.actor)
            ._legacy_booking_report_groups([("booking_id.carrier_booking_no", "in", numbers)])
        )
        self.assertEqual(
            {number: len(group) for number, group in groups.items()}, dict(Counter(row["Booking No"] for row in rows))
        )
        projected = [row for group in groups.values() for row in group]
        for row in projected:
            self.assertEqual(tuple(row), LEGACY_BOOKING_REPORT_HEADINGS)
            for heading, value in row.items():
                self.assertTrue(value and str(value).strip(), f"{heading} is blank instead of explicit")
        expected = Counter(
            (row["Booking No"], row["POD"] or UNKNOWN, row["ETS"] or UNKNOWN, bool(row["Customer"])) for row in rows
        )
        seen = Counter(
            (row["Booking No"], row["POD"], row["ETS"], row["Customer"] != UNASSIGNED_BUYER) for row in projected
        )
        self.assertEqual(seen, expected)
        sample = projected[0]
        self.assertEqual(sample["Container No"], MISSING, "no container is bound yet")
        self.assertEqual(sample["Source Wks"], NOT_MAPPED)
        self.assertEqual(sample["Eq Tare Wt"], NO_CONTAINER_BOUND, "no container is bound, so no tare fact applies")
        self.assertNotIn(sample["PO No"], (MISSING, UNKNOWN), "the supplier PO comes from the native order")

    def test_14_r011_negative_projection_writes_no_owner_record(self):
        """BRS-EXP-14-R011 negative: the report reads; it never overwrites booking, stock, invoice or documents."""
        _headings, rows = _workbook_rows()
        self._mirror(rows[:3])
        watched = (
            "plasticos.export.booking",
            "plasticos.export.booking.revision",
            LINK,
            "stock.move",
            "stock.move.line",
            "account.move",
            "sale.order",
            "purchase.order",
            "plasticos.document",
        )
        before = {model: self.env[model].search_count([]) for model in watched}
        stamps = {model: max(self.env[model].search([]).mapped("write_date") or [False]) for model in watched}
        self.env[LINK].with_user(self.actor)._legacy_booking_report_groups()
        self.env.invalidate_all()
        self.assertEqual({model: self.env[model].search_count([]) for model in watched}, before)
        self.assertEqual(
            {model: max(self.env[model].search([]).mapped("write_date") or [False]) for model in watched}, stamps
        )
