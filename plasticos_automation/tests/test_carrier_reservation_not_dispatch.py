"""Reservation is not permission to release a carrier dispatch packet."""

from odoo.tests.common import TransactionCase, tagged

CARRIER_EMAIL = "carrier-reservation@example.com"


@tagged("post_install", "-at_install", "plasticos", "integration", "logistics")
class TestCarrierReservationIsNotDispatch(TransactionCase):
    def test_legacy_reservation_automation_cannot_send(self):
        rule = self.env.ref("plasticos_automation.rule_trigger_carrier_dispatch")
        action = self.env.ref("plasticos_automation.action_auto_dispatch_carrier")
        self.assertFalse(rule.active, "a reserved picking never triggers carrier dispatch")
        self.assertEqual(action.model_id.model, "stock.picking")
        self.assertEqual(action.code.strip(), "pass", "even manual invocation must be inert")

    def test_assigned_picking_does_not_dispatch(self):
        """Native reservation with a carrier sends no packet and stamps no load."""
        rule = self.env.ref("plasticos_automation.rule_trigger_carrier_dispatch")
        action = self.env.ref("plasticos_automation.action_auto_dispatch_carrier")
        self.assertFalse(rule.active)
        carrier = self.env["res.partner"].create({"name": "Reserved Lane Carrier", "email": CARRIER_EMAIL})
        product = self.env["product.product"].create({"name": "Reservation Bale", "type": "consu", "is_storable": True})
        warehouse = self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)
        self.assertTrue(warehouse, "the company warehouse is the reservation fixture")
        customers = self.env.ref("stock.stock_location_customers")
        self.env["stock.quant"]._update_available_quantity(product, warehouse.lot_stock_id, 5)
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": warehouse.out_type_id.id,
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": customers.id,
                "carrier_id": carrier.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom": product.uom_id.id,
                            "product_uom_qty": 1,
                            "location_id": warehouse.lot_stock_id.id,
                            "location_dest_id": customers.id,
                        },
                    )
                ],
            }
        )
        stamped_before = self.env["plasticos.load"].search([("dispatch_sent", "!=", False)])
        picking.action_confirm()
        picking.action_assign()
        self.assertEqual(picking.state, "assigned")
        action.with_context(
            active_model="stock.picking",
            active_id=picking.id,
            active_ids=picking.ids,
        ).run()
        carrier_mails = self.env["mail.mail"].search([("email_to", "ilike", CARRIER_EMAIL)])
        self.assertFalse(carrier_mails)
        self.assertEqual(self.env["plasticos.load"].search([("dispatch_sent", "!=", False)]), stamped_before)
