"""Six report grains, QWeb, drilldowns and filters (RP-07-E061, V15).

Native Odoo list, pivot, graph and QWeb only. Each report has one grain, so a
container with two feeders is one availability row and two manifest rows. No
outbound mail.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged
from odoo.tools.safe_eval import safe_eval

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
        slot = booking.slot_ids.sorted("slot_key")[0]
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
        """BRS-EXP-14-R017, BRS-EXP-14-R021, BRS-EXP-14-R022, BRS-EXP-04-R005: six stable report entries."""
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
        """V15, BRS-EXP-14-R002, BRS-EXP-14-R003, BRS-EXP-14-R009: slot grain counts containers once."""
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
        missing = self.env.ref("plasticos_export.action_export_report_missing_documents")
        self.assertIn("booking_confirmation", missing.domain)

    def test_views_load_and_filters_evaluate(self):
        """BRS-EXP-14-R004, BRS-EXP-14-R005, BRS-EXP-14-R018, BRS-EXP-14-R019: native views; saved filters run."""
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
        """BRS-EXP-14-R010, BRS-EXP-13-R010, BRS-EXP-03-R004: roll prints history; candidates are not terms."""
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
