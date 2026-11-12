"""Six report grains, QWeb, drilldowns and filters (RP-07-E061, V15).

Native Odoo list, pivot, graph and QWeb only. Each report has one grain, so a
container with two feeders is one availability row and two manifest rows. No
outbound mail.

BRS-EXP-14-R011: NOT_RUN (blocked). Its comparison fixture is the operator's
``booking report.xlsx`` and its 43-column mapping, both in the campaign pack
(EXPORT_BRS/SOURCES/). Module tests may not read the campaign pack
(tests/test_no_campaign_file_dependency.py) and the addon does not ship the
fixture, so this rule runs once a copy is registered as module test data.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged
from odoo.tools.safe_eval import safe_eval

from ..models.booking_allocation import slot_order
from .test_booking_and_revision import BOOKING, LINK, SLOT, ExportFixtureMixin

SIX_REPORTS = {
    "action_export_report_availability": ("Booking Space Availability", SLOT),
    "action_export_report_manifest": ("Booking Allocation / Container Manifest", LINK),
    "action_export_report_fulfillment": ("Open Supplier PO / Customer SO Fulfillment", LINK),
    "action_export_report_register": ("Container Shipment Register", SLOT),
    "action_export_report_exceptions": ("Cutoff & Booking Exceptions", BOOKING),
    "action_export_report_missing_documents": ("Missing Export Documents", "plasticos.document"),
}


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestViewsAndReports(ExportFixtureMixin, PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_export_fixture()

    def _scenario(self):
        """Two-slot booking: two feeders and a bound container on slot 1, then a roll."""
        booking, first = self.accepted_booking(confirmed=2)
        slot = booking.slot_ids.sorted(slot_order)[0]
        orders = self.env["purchase.order"].create(
            [
                {
                    "partner_id": supplier.id,
                    "order_line": [
                        (0, 0, {"product_id": self.product.id, "product_qty": 20000, "product_uom_id": self.lb.id})
                    ],
                }
                for supplier in self.suppliers[:2]
            ]
        )
        self.assertEqual(
            slot.with_user(self.actor).action_commit_cargo(
                {"purchase_line_id": orders[0].order_line.id}, 20000, self.lb.id, first.id, self.key()
            )["status"],
            "applied",
        )
        self.assertEqual(
            slot.with_user(self.actor).action_commit_cargo(
                {"purchase_line_id": orders[1].order_line.id}, None, None, first.id, self.key()
            )["status"],
            "applied",
        )
        journey = (
            self.env["plasticos.iso.journey"]
            .with_user(self.actor)
            .action_register_iso_journey(
                self.company.id, self.key("cycle"), "40HC", False, "MSKU1234565", "SL-9", self.key()
            )
        )
        bound = slot.with_user(self.actor).action_bind_journey(journey["record_id"], first.id, self.key(), "receipt")
        self.assertEqual(bound["status"], "applied")
        roll = self.candidate(
            booking, revision_key="rev-roll", terms=self.terms(confirmed=2, erd_local="2026-10-12 08:00")
        )
        self.assertEqual(self.accept(booking, roll["record_id"], expected=first.id)["status"], "applied")
        pending = self.candidate(
            booking, revision_key="rev-unreviewed", terms=self.terms(confirmed=9, pol_text="Nowhere")
        )
        self.assertEqual(pending["status"], "applied")
        return booking, first, slot

    def test_six_reports_have_their_actions_menus_and_grain(self):
        """BRS-EXP-14-R001, BRS-EXP-14-R017, BRS-EXP-14-R021, BRS-EXP-14-R022, BRS-EXP-04-R005: six native entries."""
        for model in (BOOKING, SLOT, LINK, "plasticos.export.booking.revision"):
            self.assertTrue(self.env[model]._auto, model)
            self.assertFalse(self.env[model]._table_query, model)
        reporting = self.env.ref("plasticos_export.menu_export_reporting")
        self.assertEqual(
            sorted(reporting.child_id.mapped("name")), sorted(name for name, _model in SIX_REPORTS.values())
        )
        for xmlid, (name, model) in SIX_REPORTS.items():
            action = self.env.ref(f"plasticos_export.{xmlid}")
            self.assertEqual((action.name, action.res_model), (name, model), xmlid)
        root = self.env.ref("plasticos_export.menu_export_root")
        self.assertEqual(
            root.child_id.sorted("sequence").mapped("name"),
            ["Overview", "Bookings", "Allocations", "Cargo", "Shipments", "Deadlines", "Reporting"],
        )
        names = " ".join(self.env["ir.ui.menu"].search([("id", "child_of", root.id)]).mapped("name")).lower()
        self.assertNotIn("findteu", names)
        self.assertNotIn("aes", names)

    def test_report_rows_are_not_inflated_by_joins(self):
        """V15, BRS-EXP-14-R002, BRS-EXP-14-R003, BRS-EXP-14-R009, BRS-EXP-02-R005: one grain; derived exceptions."""
        booking, _first, slot = self._scenario()
        Slot = self.env[SLOT].with_user(self.actor)
        counts = dict(Slot._read_group([("booking_id", "=", booking.id)], ["allocation_state"], ["__count"]))
        self.assertEqual(counts, {"committed": 1, "available": 1})
        manifest = self.env.ref("plasticos_export.action_export_report_manifest")
        self.assertEqual(self.env[LINK].search_count([("booking_id", "=", booking.id)]), 2)
        self.assertEqual(manifest.context, "{'search_default_filter_live': 1, 'search_default_group_booking': 1}")
        register = self.env.ref("plasticos_export.action_export_report_register")
        self.assertEqual(Slot.search(safe_eval(register.domain)), slot)
        exceptions = self.env.ref("plasticos_export.action_export_report_exceptions")
        self.assertIn(booking, self.env[BOOKING].search(safe_eval(exceptions.domain)))
        self.assertFalse(booking.current_cargo_cutoff_utc)  # date-only cutoff: an exception, never a guessed instant
        unaccepted = self.make_booking()
        self.assertIn(unaccepted, self.env[BOOKING].search(safe_eval(exceptions.domain)))
        missing = self.env.ref("plasticos_export.action_export_report_missing_documents")
        self.assertIn("booking_confirmation", missing.domain)

    def test_views_load_and_filters_evaluate(self):
        """BRS-EXP-14-R004, BRS-EXP-14-R005, BRS-EXP-14-R018, BRS-EXP-14-R019, BRS-EXP-13-R009: native views."""
        form = self.env.ref("plasticos_export.view_export_booking_form")
        from lxml import etree as _etree

        pages = [page.get("name") for page in _etree.fromstring(form.arch).iter("page")]
        self.assertEqual(pages, ["revisions", "shipments"])
        booking, _first, _slot = self._scenario()
        for model, types in (
            (BOOKING, ["list", "form", "search", "calendar"]),
            (SLOT, ["list", "form", "search", "pivot", "graph"]),
            (LINK, ["list", "form", "search", "pivot"]),
            ("plasticos.export.booking.revision", ["list", "form"]),
        ):
            views = self.env[model].with_user(self.actor).get_views([(False, view_type) for view_type in types])
            self.assertEqual(set(views["views"]), set(types), model)
        search = self.env.ref("plasticos_export.view_export_booking_search")
        Booking = self.env[BOOKING].with_user(self.actor)
        from lxml import etree

        arch = etree.fromstring(search.arch)
        for node in arch.iter("filter"):
            if node.get("domain"):
                Booking.search(safe_eval(node.get("domain")))
        self.assertIn(booking, Booking.search([("slot_ids.journey_id.iso_number", "ilike", "MSKU1234565")]))
        self.assertIn(booking, Booking.search([("slot_ids.supplier_count", ">", 1)]))

    def test_booking_summary_renders_currentness_and_never_an_unreviewed_candidate(self):
        """BRS-EXP-14-R010, BRS-EXP-13-R010, BRS-EXP-03-R004, BRS-EXP-11-R012, BRS-EXP-14-R006: source and history."""
        booking, first, _slot = self._scenario()
        html, _kind = (
            self.env["ir.actions.report"]
            .with_user(self.actor)
            ._render_qweb_html("plasticos_export.report_booking_summary", booking.ids)
        )
        text = html.decode()
        self.assertIn("Export-generated summary, not the carrier", text)
        self.assertIn("rev-roll", text)
        self.assertIn("superseded", text)
        self.assertIn(first.source_revision_key, text)
        self.assertIn("not accepted", text)
        self.assertNotIn("Nowhere", text)
        self.assertIn("2026-10-12 08:00", text)
        self.assertIn("America/New_York", text)
        self.assertIn("booking-confirmation.pdf", text)  # which original supplied the current terms
        self.assertIn("not stated", text)  # no steamship line in the source: shown as such, never fabricated

    def test_container_manifest_renders_two_feeders_and_no_inferred_movement(self):
        """BRS-EXP-14-R002, BRS-EXP-07-R008, BRS-EXP-13-R005: one container, two planned sources."""
        booking, _first, _slot = self._scenario()
        html, _kind = (
            self.env["ir.actions.report"]
            .with_user(self.actor)
            ._render_qweb_html("plasticos_export.report_container_manifest", booking.ids)
        )
        text = html.decode()
        self.assertIn("MSKU1234565", text)
        self.assertIn("SL-9", text)
        self.assertEqual(text.count("o_manifest_link"), 2)
        self.assertIn("unknown", text)
        self.assertIn("Planned cargo only", text)
        for inferred in ("gate-in", "Gate In", "sailed", "Sailed", "shipped weight"):
            self.assertNotIn(inferred, text)

    def test_date_only_cutoff_appears_on_the_deadline_calendar(self):
        """C05 review D4, BRS-EXP-14-R019, BRS-EXP-02-R003: the stated local date, never a guessed instant."""
        from datetime import date

        from lxml import etree

        booking, _revision = self.accepted_booking(confirmed=1)
        self.assertFalse(booking.current_cargo_cutoff_utc)
        self.assertEqual(booking.current_cargo_cutoff_date, date(2026, 10, 2))
        calendar = etree.fromstring(self.env.ref("plasticos_export.view_export_booking_calendar").arch)
        self.assertEqual(calendar.get("date_start"), "current_cargo_cutoff_date")
        deadlines = self.env.ref("plasticos_export.action_export_booking_deadlines")
        on_day = (
            self.env[BOOKING]
            .with_user(self.actor)
            .search([*safe_eval(deadlines.domain), ("current_cargo_cutoff_date", "=", "2026-10-02")])
        )
        self.assertIn(booking, on_day)

    def test_late_local_cutoff_stays_on_its_local_day(self):
        """C05 review R2, BRS-EXP-02-R003, BRS-EXP-14-R019: 22:00 in Los Angeles is that local day, not the next UTC day."""
        from datetime import date

        booking = self.make_booking()
        terms = self.terms(
            confirmed=1,
            cargo_cutoff_local="2026-10-02 22:00",
            cargo_cutoff_tz="America/Los_Angeles",
            cargo_cutoff_precision="datetime",
        )
        recorded = self.candidate(booking, terms=terms)
        self.assertEqual(self.accept(booking, recorded["record_id"])["status"], "applied")
        self.assertEqual(str(booking.current_cargo_cutoff_utc), "2026-10-03 05:00:00")
        self.assertEqual(booking.current_cargo_cutoff_date, date(2026, 10, 2))

    def test_planned_quantities_are_never_summed_across_units(self):
        """C05 review D5, BRS-EXP-14-R008: no list total and a per-unit pivot column."""
        from lxml import etree

        listing = etree.fromstring(self.env.ref("plasticos_export.view_export_cargo_link_list").arch)
        planned = [node for node in listing.iter("field") if node.get("name") == "planned_quantity"]
        self.assertTrue(planned)
        self.assertFalse([node for node in planned if node.get("sum") or node.get("avg")])
        pivot = etree.fromstring(self.env.ref("plasticos_export.view_export_cargo_link_pivot").arch)
        columns = [node.get("name") for node in pivot.iter("field") if node.get("type") == "col"]
        self.assertEqual(columns[:1], ["uom_id"])
