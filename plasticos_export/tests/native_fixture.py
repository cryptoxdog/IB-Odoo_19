"""Native Enterprise fixture builder for the Export coverage witnesses (S8).

One real buyer commitment and smaller supply orders, built through the native
Sale, Purchase, Stock and Accounting owners: a storable product sold as whole
loads (1 Unit = 1 load), a confirmed 30-load customer SO, two confirmed 4-load
supplier POs, weekly receipts that leave native backorders, a partial SO
delivery, a posted customer invoice and a verified ``plasticos.document``.
Export slots come from an accepted booking revision and cargo is committed
through the frozen ``action_commit_cargo`` command. Export writes none of the
native records; every helper here drives the native owner directly, as the
superuser fixture or as the named user.

The mixin is plain (no test methods), so importing it runs no test twice.
"""

import base64
import itertools

from odoo.tests.common import new_test_user

from .test_booking_and_revision import ExportFixtureMixin

_BYTES = itertools.count(1)
SO_LOADS = 30
PO_LOADS = 4
SUPPLIER_PRICE = 0.4321


class NativeExportFixtureMixin(ExportFixtureMixin):
    """Native SO/PO/stock/invoice/document fixture on top of the shared Export fixture."""

    @classmethod
    def _setup_native_fixture(cls):
        cls._setup_export_fixture()
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.load_product = cls.env["product.product"].create(
            {
                "name": "S8 MRP Regrind (load)",
                "type": "consu",
                "is_storable": True,
                "uom_id": cls.unit.id,
                "invoice_policy": "delivery",
                "purchase_method": "receive",
                "list_price": 1.0,
            }
        )
        cls.sale = cls.env["sale.order"].create(
            {
                "partner_id": cls.buyer.id,
                "company_id": cls.company.id,
                # The Export actor is a Sales user too; native Sale shows a salesman their own orders.
                "user_id": cls.actor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.load_product.id,
                            "product_uom_qty": SO_LOADS,
                            "product_uom_id": cls.unit.id,
                            "price_unit": 1.0,
                        },
                    )
                ],
            }
        )
        cls.sale.action_confirm()
        cls.sale_line = cls.sale.order_line
        cls.purchases = cls.env["purchase.order"]
        for supplier in cls.suppliers[:2]:
            order = cls.env["purchase.order"].create(
                {
                    "partner_id": supplier.id,
                    "company_id": cls.company.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": cls.load_product.id,
                                "product_qty": PO_LOADS,
                                "product_uom_id": cls.unit.id,
                                "price_unit": SUPPLIER_PRICE,
                            },
                        )
                    ],
                }
            )
            order.button_confirm()
            cls.purchases |= order
        cls.purchase = cls.purchases[0]
        cls.purchase_line = cls.purchase.order_line
        cls.document_verifier = new_test_user(
            cls.env,
            login="s8_document_verifier",
            groups="base.group_user,plasticos_documents.group_documents_user,purchase.group_purchase_user",
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )

    # ── native owners, driven directly ──────────────────────

    @staticmethod
    def _open_picking(order):
        return order.picking_ids.filtered(lambda picking: picking.state not in ("done", "cancel"))

    def _execute(self, picking, quantity):
        """Do ``quantity`` of one open picking through native Stock, keeping the backorder."""
        self.assertEqual(len(picking), 1, picking)
        if picking.state in ("confirmed", "waiting"):
            picking.action_assign()
        move = picking.move_ids
        move.quantity = quantity
        move.picked = True
        picking._action_done()
        self.assertEqual(picking.state, "done")
        return picking.move_line_ids

    def receive_week(self, order=None, quantity=1):
        """One weekly supplier receipt; native Stock opens the backorder for the rest."""
        return self._execute(self._open_picking(order or self.purchase), quantity)

    def deliver(self, quantity=1):
        """One partial customer delivery of the 30-load SO."""
        return self._execute(self._open_picking(self.sale), quantity)

    def post_invoice(self):
        """Invoice what native Sale says is delivered, and post it."""
        invoice = self.sale._create_invoices()
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        return invoice

    def make_load(self):
        return self.env["plasticos.load"].create({"sale_order_id": self.sale.id})

    def verified_document(self, load):
        """A verified gate receipt on ``load`` through the Documents owner."""
        tag = self.env["plasticos.document.tag"].search([("code", "=", "BOL")], limit=1)
        self.assertTrue(tag, "BOL document tag is not installed")
        attachment = self.env["ir.attachment"].create(
            {
                "name": "gate-receipt.pdf",
                "datas": base64.b64encode(f"gate receipt {next(_BYTES)}".encode()),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )
        shell = self.env["plasticos.document"].create(
            {
                "name": "Gate receipt",
                "tag_id": tag.id,
                "res_model": "documents.document",
                "res_id": 0,
                "attachment_id": attachment.id,
            }
        )
        row = shell.with_user(self.document_verifier)._associate_scope("plasticos.load", load.id, "S8 gate receipt")
        row.with_user(self.document_verifier).action_verify()
        return row

    # ── Export, through its frozen commands ─────────────────

    def commit_cargo(self, slot, refs, quantity=1.0, uom=None, key=None, user=None):
        uom = uom if uom is not None else self.unit
        return slot.with_user(user or self.actor).action_commit_cargo(
            refs,
            quantity,
            uom.id if uom else None,
            slot.booking_id.current_revision_id.id,
            key or self.key("s8-commit"),
        )

    def stock_refs(self, move_line, **extra):
        """Exact native-stock source refs for one executed receipt quantity."""
        return {
            "purchase_line_id": move_line.move_id.purchase_line_id.id,
            "stock_move_line_id": move_line.id,
            "physical_source_kind": "native_stock",
            **extra,
        }

    @staticmethod
    def stamps(*recordsets):
        """Write date and state of native records, to prove Export wrote none of them."""
        return {
            (record._name, record.id): (record.write_date, record["state"] if "state" in record._fields else None)
            for records in recordsets
            for record in records
        }
