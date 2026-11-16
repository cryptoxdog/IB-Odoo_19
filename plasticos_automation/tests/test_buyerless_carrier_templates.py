"""Carrier mail names the load's own company, never a sale order or env.company (S4, D5).

RP-03-E010 / RP-03-E015, BRS-EXP-08-R001, BRS-EXP-10-R003. A buyerless load has no
sale order, so the issuer, phone and sender must come from ``load.company_id``.
Rendering a template is not sending: no mail is queued by these checks.
"""

from odoo.tests.common import TransactionCase, tagged

CARRIER_TEMPLATES = (
    "plasticos_automation.email_template_delivery_order",
    "plasticos_automation.email_template_bol_pickup",
    "plasticos_automation.email_template_bol_delivery",
    "plasticos_automation.email_template_dispatch_packet",
)
EXPECTED_REPORTS = {
    "plasticos_automation.email_template_delivery_order": {"plasticos_logistics.action_report_delivery_order"},
    "plasticos_automation.email_template_bol_pickup": {"plasticos_logistics.action_report_bol_pickup"},
    "plasticos_automation.email_template_bol_delivery": {"plasticos_logistics.action_report_bol_delivery"},
    "plasticos_automation.email_template_dispatch_packet": {
        "plasticos_logistics.action_report_delivery_order",
        "plasticos_logistics.action_report_bol_pickup",
        "plasticos_logistics.action_report_bol_delivery",
    },
}
FORBIDDEN_LITERALS = ("PlasticOS Logistics", "docs@company.com", "{{", "}}")


@tagged("post_install", "-at_install", "plasticos", "logistics")
class TestBuyerlessCarrierTemplates(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.issuer = cls.env["res.company"].create(
            {
                "name": "S4 Buyerless Issuer Co",
                "email": "yard@s4-issuer.example",
                "phone": "+1 555 0104",
                "street": "4 Issuer Yard",
            }
        )
        cls.supplier = cls.env["res.partner"].create(
            {"name": "S4 Mill", "is_company": True, "supplier_rank": 1, "city": "Houston"}
        )
        cls.terminal = cls.env["res.partner"].create({"name": "S4 Ramp", "is_company": True, "city": "Dallas"})
        cls.carrier = cls.env["res.partner"].create(
            {"name": "S4 Drayage", "is_company": True, "email": "dispatch@s4-dray.example"}
        )
        cls.buyer = cls.env["res.partner"].create({"name": "S4 Buyer", "is_company": True, "customer_rank": 1})

    def _load(self, **values):
        base = {
            "pickup_partner_id": self.supplier.id,
            "delivery_partner_id": self.terminal.id,
            "carrier_id": self.carrier.id,
            "rate_amount": 875.0,
        }
        base.update(values)
        return self.env["plasticos.load"].create(base)

    def _render(self, xmlid, load):
        template = self.env.ref(xmlid)
        return {
            name: template._render_field(name, load.ids)[load.id] or ""
            for name in ("subject", "body_html", "email_from", "email_to")
        }

    def _assert_issuer(self, rendered, company):
        self.assertEqual(rendered["email_from"], company.email_formatted)
        body = str(rendered["body_html"])
        self.assertIn(company.name, body)
        if company.phone:
            self.assertIn(company.phone, body)
        for literal in FORBIDDEN_LITERALS:
            self.assertNotIn(literal, body)
        self.assertEqual(rendered["email_to"], self.carrier.email)

    def test_buyerless_load_in_a_second_company_names_that_company(self):
        load = self._load(company_id=self.issuer.id)
        self.assertFalse(load.sale_order_id)
        self.assertNotEqual(self.env.company, self.issuer)
        mails_before = self.env["mail.mail"].search_count([])
        for xmlid in CARRIER_TEMPLATES:
            with self.subTest(template=xmlid):
                rendered = self._render(xmlid, load)
                self._assert_issuer(rendered, self.issuer)
                self.assertNotIn(self.env.company.name, str(rendered["body_html"]))
                self.assertIn(load.name, str(rendered["body_html"]))
                self.assertIn(self.issuer.email, str(rendered["body_html"]))
        self.assertEqual(self.env["mail.mail"].search_count([]), mails_before, "rendering never queues mail")

    def test_sale_backed_load_keeps_its_own_company(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        load = self._load(sale_order_id=order.id)
        self.assertEqual(load.company_id, order.company_id)
        for xmlid in CARRIER_TEMPLATES:
            with self.subTest(template=xmlid):
                self._assert_issuer(self._render(xmlid, load), load.company_id)

    def test_company_without_email_renders_no_invented_address(self):
        silent = self.env["res.company"].create({"name": "S4 No Mail Co"})
        load = self._load(company_id=silent.id)
        for xmlid in CARRIER_TEMPLATES:
            with self.subTest(template=xmlid):
                rendered = self._render(xmlid, load)
                body = str(rendered["body_html"])
                self.assertIn(silent.name, body)
                self.assertNotIn("Send all completed docs to", body)
                self.assertNotIn(self.env.company.email or "\x00", rendered["email_from"])
                for literal in FORBIDDEN_LITERALS:
                    self.assertNotIn(literal, body)

    def test_each_template_addresses_the_carrier_itself(self):
        """The carrier is the recipient: default record recipients would leave a load mail with none."""
        load = self._load(company_id=self.issuer.id)
        for xmlid in CARRIER_TEMPLATES:
            with self.subTest(template=xmlid):
                template = self.env.ref(xmlid)
                self.assertFalse(template.use_default_to)
                self.assertEqual(template._render_field("email_to", load.ids)[load.id], self.carrier.email)

    def test_follow_up_templates_address_their_counterparty(self):
        """Review item 2: these records have no default counterparty, so email_to must not be replaced."""
        trucker = self.env.ref("plasticos_automation.email_template_trucker_followup")
        confirmation = self.env.ref("plasticos_automation.email_template_supplier_confirmation")
        self.assertFalse(trucker.use_default_to)
        self.assertFalse(confirmation.use_default_to)
        warehouse = self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": warehouse.out_type_id.id,
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "partner_id": self.buyer.id,
                "carrier_id": self.carrier.id,
            }
        )
        self.assertEqual(trucker._render_field("email_to", picking.ids)[picking.id], self.carrier.email)
        supplier = self.env["res.partner"].create(
            {"name": "S4 Confirming Mill", "is_company": True, "supplier_rank": 1, "email": "ready@s4-mill.example"}
        )
        transaction = self.env["plasticos.transaction"].create({"name": "TX-S4-CONFIRM", "supplier_id": supplier.id})
        self.assertEqual(confirmation._render_field("email_to", transaction.ids)[transaction.id], supplier.email)

    def test_each_template_attaches_only_its_carrier_reports(self):
        for xmlid, expected in EXPECTED_REPORTS.items():
            with self.subTest(template=xmlid):
                reports = self.env.ref(xmlid).report_template_ids
                self.assertEqual(set(reports.get_external_id().values()), expected)
