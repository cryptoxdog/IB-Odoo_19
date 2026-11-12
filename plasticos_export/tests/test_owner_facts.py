"""Owner-fact displays and the commercial trade label (S10 OP10-E01, OP10-E02).

BRS-EXP-01-R002: Export shows one current document verdict, one freight status,
one stock movement and one posted invoice from their owners and stores none of
them. BRS-EXP-07-R006: package totals, package tare and the VGM verdict come
from native Stock and Documents; equipment never implies a weight. BRS-EXP-02-R006:
the quoted FOB/FAS/CNF usage is kept apart from the order Incoterm. A user
without rights sees a restricted marker, never an empty value or a zero
(BRS-EXP-14-R022).
"""

import base64
import itertools
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError
from odoo.tests.common import new_test_user, tagged

from ..models.document_inherit import VERIFIED_GROSS_MASS
from ..models.owner_facts import NO_CONTAINER_BOUND, RESTRICTED
from .test_booking_and_revision import LINK, ExportFixtureMixin, actor_groups, row_versions

_BYTES = itertools.count(1)
OWNER_FACT_FIELDS = {
    LINK: (
        "sale_incoterm_display",
        "purchase_incoterm_display",
        "owner_invoice_display",
        "owner_freight_status",
        "owner_document_verdict",
        "owner_stock_move_display",
        "owner_package_display",
    ),
    "plasticos.export.booking.slot": (
        "owner_package_summary",
        "owner_vgm_verdict",
        "owner_container_tare",
        "owner_container_vgm_weight",
        "owner_shipment_history",
    ),
    "plasticos.export.booking": ("owner_booking_confirmation_verdict",),
}


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestExportOwnerFacts(ExportFixtureMixin, PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_export_fixture()
        cls.verifier = new_test_user(
            cls.env,
            login="s10_owner_fact_verifier",
            groups="base.group_user,plasticos_documents.group_documents_user,purchase.group_purchase_user",
        )
        cls.sales_reader = new_test_user(
            cls.env,
            login="s10_owner_fact_sales",
            groups="base.group_user,plasticos_security_base.group_sales_rep",
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )
        cls.invoice_reader = new_test_user(
            cls.env,
            login="s10_owner_fact_invoice_reader",
            groups=actor_groups(cls.env, extra=("account.group_account_readonly",)),
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )
        cls.tag = cls.env["plasticos.document.tag"].search([("code", "=", "BOL")], limit=1)
        if not cls.tag:
            raise AssertionError("BLOCKED: BOL document tag is not installed")
        cls.fca = cls.env.ref("account.incoterm_FCA")
        cls.unit = cls.env["product.template"]._get_weight_uom_name_from_ir_config_parameter()

    # ── fixtures ─────────────────────────────────────────────

    def _orders(self, sales_user=None):
        sale = self.env["sale.order"].create(
            {
                "partner_id": self.buyer.id,
                "user_id": (sales_user or self.sales_reader).id,
                "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 40000})],
            }
        )
        purchase = self.env["purchase.order"].create(
            {
                "partner_id": self.suppliers[0].id,
                "incoterm_id": self.fca.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_qty": 40000, "product_uom_id": self.lb.id})
                ],
            }
        )
        if "incoterm" in sale._fields:
            sale.incoterm = self.fca
        return sale, purchase

    def _packaged_move_line(self, weight=18000.0, tare=40.0):
        package_type = self.env["stock.package.type"].create({"name": "S10 Bale", "base_weight": tare})
        package = self.env["stock.package"].create(
            {"name": f"S10-PKG-{next(_BYTES)}", "package_type_id": package_type.id, "shipping_weight": weight}
        )
        warehouse = self.env["stock.warehouse"].search([("company_id", "=", self.company.id)], limit=1)
        return self.env["stock.move.line"].create(
            {
                "product_id": self.product.id,
                "product_uom_id": self.product.uom_id.id,
                "quantity": 1.0,
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "result_package_id": package.id,
                "company_id": self.company.id,
            }
        )

    def _verified_vgm(self, load, expiry_date=None):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "vgm.pdf",
                "datas": base64.b64encode(f"vgm-{next(_BYTES)}".encode()),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )
        shell = self.env["plasticos.document"].create(
            {
                "name": "VGM",
                "tag_id": self.tag.id,
                "res_model": "documents.document",
                "res_id": 0,
                "attachment_id": attachment.id,
            }
        )
        row = shell.with_user(self.verifier)._associate_scope(
            "plasticos.load",
            load.id,
            "export VGM",
            obligation_kind=VERIFIED_GROSS_MASS,
            operation_revision_key="SYN-BKG/r1",
            coverage_key="container-1",
        )
        if expiry_date:
            row.write({"expiry_date": expiry_date})
        row.with_user(self.verifier).action_verify()
        return row

    def _posted_invoice(self, sale_line):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.buyer.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "sale_line_ids": [(6, 0, sale_line.ids)],
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def _shipment(self):
        """One committed 40HC slot fed by an SO, a PO, a load and a packaged native stock move."""
        booking, revision = self.accepted_booking(confirmed=1)
        slot = booking.slot_ids
        sale, purchase = self._orders()
        load = self.env["plasticos.load"].create({"sale_order_id": sale.id})
        move_line = self._packaged_move_line()
        outcome = slot.with_user(self.actor).action_commit_cargo(
            {
                "sale_line_id": sale.order_line.id,
                "purchase_line_id": purchase.order_line.id,
                "source_load_id": load.id,
                "stock_move_line_id": move_line.id,
                "physical_source_kind": "native_stock",
            },
            None,
            None,
            revision.id,
            self.key("s10-commit"),
        )
        self.assertEqual(outcome["status"], "applied", outcome)
        link = self.env[LINK].browse(outcome["record_id"])
        return booking, slot, link, sale, purchase, load, move_line

    # ── BRS-EXP-01-R002 ──────────────────────────────────────

    def test_01_r002_positive_one_fact_per_owner(self):
        """BRS-EXP-01-R002 positive: one document verdict, freight status, stock move and posted invoice, from owners."""
        _booking, _slot, link, sale, _purchase, load, move_line = self._shipment()
        self._verified_vgm(load)
        invoice = self._posted_invoice(sale.order_line)
        view = link.with_user(self.invoice_reader)
        self.assertIn("VGM: verified and current", view.owner_document_verdict)
        self.assertIn("Booking confirmation: missing", view.owner_document_verdict)
        state = dict(load._fields["state"]._description_selection(self.env))[load.state]
        self.assertEqual(view.owner_freight_status, f"{load.name}: {state}")
        self.assertIn(f"1 {move_line.product_uom_id.name}", view.owner_stock_move_display)
        self.assertIn(f"Customer invoices: {invoice.name} posted", view.owner_invoice_display)
        self.assertIn("Vendor bills: No posted invoice", view.owner_invoice_display)
        self.assertIn(f"Customer invoices: {RESTRICTED}", link.with_user(self.actor).owner_invoice_display)
        # The status follows the Logistics owner's validated transition; Export holds no copy.
        load._transition("awaiting_ready")
        self.env.invalidate_all()
        self.assertEqual(load.state, "awaiting_ready")
        self.assertIn("Awaiting Ready", link.with_user(self.invoice_reader).owner_freight_status)

    def test_01_r002_negative_export_stores_no_owner_fact(self):
        """BRS-EXP-01-R002 negative: no second verified flag, stock quantity, freight ledger or invoice is stored."""
        for model, names in OWNER_FACT_FIELDS.items():
            for name in names:
                field = self.env[model]._fields[name]
                self.assertFalse(field.store, f"{model}.{name} must not be stored")
                self.assertTrue(field.compute, f"{model}.{name} must be read live from its owner")
        self.env.cr.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'plasticos_export_booking_cargo_link'"
        )
        columns = {row[0] for row in self.env.cr.fetchall()}
        for forbidden in ("verified", "shipped_quantity", "actual_freight_cost", "invoice_state", "vgm_weight"):
            self.assertNotIn(forbidden, columns)
        _booking, _slot, link, _sale, _purchase, load, _move_line = self._shipment()
        tomorrow = fields.Date.today() + timedelta(days=1)
        self._verified_vgm(load, expiry_date=tomorrow)
        self.assertIn("VGM: verified and current", link.with_user(self.actor).owner_document_verdict)
        # The verdict follows the Documents owner live; Export kept no copy of the decision.
        later = fields.Date.today() + timedelta(days=5)
        self.env.invalidate_all()
        with patch.object(type(self.env["plasticos.document"]), "_evidence_today", return_value=later):
            self.assertIn("VGM: stale", link.with_user(self.actor).owner_document_verdict)

    def test_restricted_owner_fact_is_marked_never_blank(self):
        """BRS-EXP-14-R022: a role without the owner's rights sees a restricted marker, not a false empty value."""
        _booking, _slot, link, _sale, purchase, _load, _move_line = self._shipment()
        self.assertFalse(self.sales_reader.has_group("purchase.group_purchase_user"))
        with self.assertRaises(AccessError):
            purchase.with_user(self.sales_reader).check_access("read")
        reader_view = link.with_user(self.sales_reader)
        self.assertEqual(reader_view.purchase_incoterm_display, RESTRICTED)
        self.assertNotIn(reader_view.purchase_incoterm_display, (False, "", "0"))
        self.assertEqual(link.with_user(self.actor).purchase_incoterm_display, "FCA")

    # ── BRS-EXP-07-R006 ──────────────────────────────────────

    def test_07_r006_positive_package_totals_tare_and_vgm_from_owners(self):
        """BRS-EXP-07-R006 positive: 40HC shows Stock package totals and tare and the Documents VGM verdict."""
        _booking, slot, link, _sale, _purchase, load, _move_line = self._shipment()
        self.assertEqual(slot.equipment_class, "40HC")
        view = slot.with_user(self.actor)
        self.assertIn("Packages: 1", view.owner_package_summary)
        self.assertIn(f"Recorded shipping weight: 18000 {self.unit}", view.owner_package_summary)
        self.assertIn(f"Package type nominal weight: 40 {self.unit}", view.owner_package_summary)
        self.assertIn("not a certified VGM", view.owner_package_summary)
        self.assertEqual(view.owner_vgm_verdict, f"{load.name}: missing")
        self._verified_vgm(load)
        self.env.invalidate_all()
        self.assertEqual(slot.with_user(self.actor).owner_vgm_verdict, f"{load.name}: verified and current")
        self.assertEqual(view.owner_container_tare, NO_CONTAINER_BOUND)
        self.assertIn("shipping weight 18000", link.with_user(self.actor).owner_package_display)

    def test_07_r006_negative_equipment_never_implies_weight_or_vgm(self):
        """BRS-EXP-07-R006 negative: 40HC inserts no payload, self-certifies no VGM and writes no weight."""
        booking, _revision = self.accepted_booking(confirmed=1)
        slot = booking.slot_ids.with_user(self.actor)
        self.assertEqual(slot.owner_package_summary, "No package recorded by Stock")
        self.assertEqual(slot.owner_vgm_verdict, "No Logistics load committed")
        self.assertEqual(slot.owner_container_tare, NO_CONTAINER_BOUND)
        _booking, slot, _link, _sale, _purchase, _load, move_line = self._shipment()
        package = move_line.result_package_id
        package.shipping_weight = 0.0
        self.env.invalidate_all()
        summary = slot.with_user(self.actor).owner_package_summary
        self.assertIn("incomplete: 1 not recorded", summary)
        self.assertIn("not a certified VGM", summary)
        self.assertIn("missing", slot.with_user(self.actor).owner_vgm_verdict)
        self.assertEqual(package.shipping_weight, 0.0)

    # ── BRS-EXP-02-R006 ──────────────────────────────────────

    def test_02_r006_positive_trade_label_kept_apart_from_formal_incoterm(self):
        """BRS-EXP-02-R006 positive: industry FOB pickup and a formal FCA term are stored distinctly."""
        booking, _slot, link, sale, purchase, _load, _move_line = self._shipment()
        link.with_user(self.actor).write(
            {"commercial_trade_label": "fob", "commercial_trade_label_quote": "FOB supplier dock, buyer pickup"}
        )
        self.assertEqual(link.commercial_trade_label, "fob")
        self.assertEqual(purchase.incoterm_id, self.fca)
        self.assertEqual(link.with_user(self.actor).purchase_incoterm_display, "FCA")
        if "incoterm" in sale._fields:
            self.assertEqual(sale.incoterm, self.fca)
        notes = booking.message_ids.filtered(lambda message: "commercial trade label" in (message.body or ""))
        self.assertTrue(notes, "the label change is audited on the booking")
        action = link.with_user(self.actor).action_open_trade_label()
        self.assertEqual(action["res_id"], link.id)
        self.assertEqual(action["target"], "new")

    def test_02_r006_negative_fas_label_never_rewrites_an_incoterm(self):
        """BRS-EXP-02-R006 negative: FAS sets no ICC FAS term and turns on no freight; a reader cannot set it."""
        _booking, _slot, link, sale, purchase, load, _move_line = self._shipment()
        purchase.incoterm_id = False
        sale_incoterm = sale.incoterm if "incoterm" in sale._fields else None
        before = (
            row_versions(purchase),
            row_versions(purchase.order_line),
            row_versions(sale),
            row_versions(sale.order_line),
            row_versions(load),
        )
        link.with_user(self.actor).write({"commercial_trade_label": "fas"})
        self.assertFalse(purchase.incoterm_id)
        self.assertEqual(link.with_user(self.actor).purchase_incoterm_display, "No Incoterm on the order")
        self.assertEqual(
            (
                row_versions(purchase),
                row_versions(purchase.order_line),
                row_versions(sale),
                row_versions(sale.order_line),
                row_versions(load),
            ),
            before,
            "the label wrote no order, order line or load row",
        )
        if "incoterm" in sale._fields:
            self.assertEqual(sale.incoterm, sale_incoterm, "the SO Incoterm is unchanged")
        with self.assertRaises(AccessError):
            link.with_user(self.sales_reader).write({"commercial_trade_label": "cnf"})
        self.assertEqual(link.commercial_trade_label, "fas")

    def test_07_r006_package_type_weight_is_summed_per_package(self):
        """BRS-EXP-07-R006 (review B1): two packages of one type count twice; mixed types add up, per package."""
        Type = self.env["stock.package.type"]
        bale, gaylord = (
            Type.create({"name": "S10 Bale B1", "base_weight": 40}),
            Type.create({"name": "S10 Gaylord B1", "base_weight": 15}),
        )
        Package = self.env["stock.package"]
        same = Package.create(
            [{"name": f"S10-B1-{n}", "package_type_id": bale.id, "shipping_weight": 1000} for n in range(2)]
        )
        mixed = same | Package.create({"name": "S10-B1-G", "package_type_id": gaylord.id, "shipping_weight": 500})
        Slot = self.env["plasticos.export.booking.slot"]
        self.assertIn(f"Package type nominal weight: 80 {self.unit}", Slot._package_summary(same, self.unit))
        summary = Slot._package_summary(mixed, self.unit)
        self.assertIn("Packages: 3", summary)
        self.assertIn(f"Recorded shipping weight: 2500 {self.unit}", summary)
        self.assertIn(f"Package type nominal weight: 95 {self.unit}", summary)
        self.assertNotIn("incomplete", summary)
