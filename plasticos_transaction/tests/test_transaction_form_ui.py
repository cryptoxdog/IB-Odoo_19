"""Transaction form, list, and search as the registry renders them, inheritance applied.

Runs under ``odoo --test-enable --test-tags /plasticos_transaction`` on a database
that carries the PlasticOS stack. ``get_view`` resolves every installed inherit
view against the base arch, so a broken xpath in plasticos_claims or
plasticos_logistics fails here rather than in the browser.
"""

from __future__ import annotations

from lxml import etree

from odoo.tests import TransactionCase, tagged

TRANSACTION = "plasticos.transaction"
BULK_WIZARD = "plasticos.tx.bulk.wizard"


def _names(nodes):
    return [node.get("name") for node in nodes]


@tagged("post_install", "-at_install")
class TestTransactionFormUi(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Transaction = cls.env[TRANSACTION]
        cls.form = etree.fromstring(cls.Transaction.get_view(view_type="form")["arch"])
        cls.listing = etree.fromstring(cls.Transaction.get_view(view_type="list")["arch"])
        cls.search = etree.fromstring(cls.Transaction.get_view(view_type="search")["arch"])

    def _installed(self, module):
        return bool(self.env["ir.module.module"].search_count([("name", "=", module), ("state", "=", "installed")]))

    def _group(self, name):
        groups = self.form.xpath(f"//group[@name='{name}']")
        self.assertEqual(len(groups), 1, name)
        return groups[0]

    # ── form ─────────────────────────────────────────────────────────────

    def test_profit_snapshot_is_the_only_margin_presentation(self):
        snapshot = self._group("profit_snapshot")
        self.assertEqual(
            _names(snapshot.xpath("./field")),
            [
                "revenue_total",
                "purchase_cost_total",
                "freight_cost_total",
                "cost_total",
                "gross_margin",
                "commission_amount",
                "net_margin",
            ],
        )
        self.assertEqual(snapshot.xpath("./field[@name='purchase_cost_total']")[0].get("string"), "Material Cost")
        net_margin = snapshot.xpath("./field[@name='net_margin']")[0]
        self.assertIn("o_plasticos_net_margin", net_margin.get("class", ""))
        # F232-1: sign-aware colour survives view post-processing; the renderer maps these
        # to text-success / text-danger (web/static/src/views/utils.js getClassNameFromDecoration).
        self.assertEqual(net_margin.get("decoration-success"), "net_margin > 0")
        self.assertEqual(net_margin.get("decoration-danger"), "net_margin < 0")
        for name in ("revenue_total", "purchase_cost_total", "freight_cost_total", "cost_total", "gross_margin"):
            field = snapshot.xpath(f"./field[@name='{name}']")[0]
            self.assertFalse([a for a in field.attrib if a.startswith("decoration-")], name)
        # gross_margin is shown once; the former banners and the gross-margin stat are gone.
        self.assertEqual(len(self.form.xpath("//field[@name='gross_margin']")), 1)
        self.assertFalse(self.form.xpath("//div[contains(@class, 'alert-success')]"))
        self.assertFalse(self.form.xpath("//div[contains(@class, 'alert-danger')]//field[@name='gross_margin']"))
        # net_margin: the snapshot row plus the Net Margin stat button, nothing else.
        self.assertEqual(len(self.form.xpath("//field[@name='net_margin']")), 2)
        stat = self.form.xpath("//button[contains(@class, 'oe_stat_button')]//field[@name='net_margin']")
        self.assertEqual(len(stat), 1)

    def test_orders_group_puts_counterparties_and_material_first(self):
        orders = self._group("orders")
        self.assertEqual(
            _names(orders.xpath("./field")),
            ["user_id", "product_id", "supplier_id", "buyer_id", "sale_order_id", "purchase_order_ids"],
        )
        self.assertEqual(orders.xpath("./field[@name='purchase_order_ids']")[0].get("widget"), "many2many_tags_open")
        for name in ("vendor_bill_ids", "freight_bill_ids"):
            field = self.form.xpath(f"//field[@name='{name}']")
            self.assertEqual(len(field), 1, name)
            self.assertEqual(field[0].get("widget"), "many2many_tags_open")

    def test_freight_and_material_groups(self):
        freight = self._group("freight")
        self.assertEqual(_names(freight.xpath("./field")), ["freight_chargebacks", "other_expenses"])
        material = self._group("material")
        names = _names(material.xpath("./field"))
        self.assertEqual(names[:2], ["final_weight", "lightweight_penalties"])
        self.assertNotIn("material_unit_cost", names)
        if self._installed("plasticos_claims"):
            self.assertIn("has_quality_claim", names)
            self.assertEqual(self.form.xpath("//field[@name='has_quality_claim']")[0].get("string"), "Quality Claim")

    def test_delivery_group_carries_carrier_freight_and_load(self):
        delivery = self._group("delivery_order")
        names = _names(delivery.xpath("./field"))
        self.assertEqual(names[:3], ["carrier_id", "freight_actual", "delivery_order_id"])
        self.assertEqual(len(self.form.xpath("//field[@name='carrier_id']")), 1)
        if self._installed("plasticos_logistics"):
            self.assertEqual(names[3], "load_count")
            self.assertEqual(names[4], "load_ids")
            self.assertFalse(self.form.xpath("//field[@name='load_id']"))
        self.assertEqual(names[-1], "do_number")

    def test_every_form_field_exists_on_the_model(self):
        # Fields inside an inline sub-view (line_ids) belong to the comodel; skip them.
        own_fields = self.form.xpath("//field[not(ancestor::field)]")
        missing = sorted({name for name in _names(own_fields) if name and name not in self.Transaction._fields})
        self.assertEqual(missing, [])

    # ── list ─────────────────────────────────────────────────────────────

    def test_default_list_is_the_transaction_list_not_the_wizard_list(self):
        real = self.env.ref("plasticos_transaction.view_transaction_tree")
        wizard = self.env.ref("plasticos_transaction.view_plasticos_transaction_bulk_wizard_tree")
        self.assertEqual(wizard.priority, 99)
        self.assertLess(real.priority, wizard.priority)
        self.assertEqual(self.env["ir.ui.view"].default_view(TRANSACTION, "list"), real.id)
        action = self.env.ref("plasticos_transaction.action_transaction")
        self.assertFalse(action.view_id)
        views = self.Transaction.get_views([(False, "list")])["views"]["list"]
        rendered = etree.fromstring(views["arch"])
        self.assertIn("historical_margin", _names(rendered.xpath("//field")))
        self.assertIn("compliance_status", _names(rendered.xpath("//field")))

    def test_list_keeps_lifecycle_decorations_and_margin_highlight(self):
        listing = self.listing
        self.assertEqual(listing.tag, "list")
        self.assertEqual(listing.get("decoration-info"), "state == 'draft'")
        self.assertEqual(listing.get("decoration-muted"), "state in ('closed', 'cancelled')")
        self.assertEqual(listing.get("decoration-danger"), "gross_margin < 0")
        names = _names(listing.xpath("./field"))
        for name in (
            "supplier_id",
            "buyer_id",
            "product_id",
            "purchase_order_ids",
            "historical_sale_total",
            "historical_purchase_total",
            "historical_margin",
            "revenue_total",
            "cost_total",
            "gross_margin",
            "state",
        ):
            self.assertIn(name, names)
        optional = {f.get("name"): f.get("optional") for f in listing.xpath("./field[@optional]")}
        self.assertEqual(optional["purchase_order_ids"], "hide")
        self.assertEqual(optional["revenue_total"], "hide")
        self.assertEqual(optional["historical_margin"], "show")
        self.assertEqual(listing.xpath("./field[@name='state']")[0].get("widget"), "badge")

    def test_bulk_wizard_keeps_its_own_list(self):
        wizard_tree = self.env.ref("plasticos_transaction.view_plasticos_transaction_bulk_wizard_tree")
        arch = etree.fromstring(self.Transaction.get_view(view_id=wizard_tree.id, view_type="list")["arch"])
        self.assertEqual(_names(arch.xpath("./field")), ["name", "supplier_id", "buyer_id", "state"])
        # The server embeds the x2many list resolved from list_view_ref into the form arch
        # (ir.ui.view._get_x2many_missing_view_archs), which is what the client renders.
        wizard_form = etree.fromstring(self.env[BULK_WIZARD].get_view(view_type="form")["arch"])
        embedded = wizard_form.xpath("//field[@name='transaction_ids']/list")
        self.assertEqual(len(embedded), 1)
        self.assertEqual(_names(embedded[0].xpath("./field")), ["name", "supplier_id", "buyer_id", "state"])
        self.assertNotIn("historical_margin", _names(embedded[0].xpath(".//field")))

    # ── search ───────────────────────────────────────────────────────────

    def test_search_keeps_negative_margin_filter_and_carrier_grouping(self):
        negative = self.search.xpath("//filter[@name='filter_negative_margin']")
        self.assertEqual(len(negative), 1)
        self.assertEqual(negative[0].get("domain"), "[('gross_margin', '<', 0)]")
        carrier = self.search.xpath("//filter[@name='group_carrier']")
        self.assertEqual(len(carrier), 1)
        self.assertIn("'group_by': 'carrier_id'", carrier[0].get("context"))
