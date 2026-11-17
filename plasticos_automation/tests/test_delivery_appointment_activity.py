"""SO confirmation asks Logistics once and sends no dock-appointment mail (ADR-135 §4)."""

import re

from odoo.tests import TransactionCase, tagged

_SUMMARY = "Request delivery appointment"


@tagged("post_install", "-at_install")
class TestDeliveryAppointmentActivity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.buyer = cls.env["res.partner"].create(
            {"name": "Appointment Buyer Co", "is_company": True, "customer_rank": 1}
        )
        cls.site = cls.env["res.partner"].create(
            {
                "name": "North Receiving Site",
                "parent_id": cls.buyer.id,
                "type": "delivery",
                "default_delivery_term": "appointment",
            }
        )
        cls.product = cls.env["product.product"].create({"name": "Dock Rule Resin", "type": "consu", "sale_ok": True})
        logistics = cls.env.ref("plasticos_security_base.group_logistics")
        cls.env["res.users"].create(
            {
                "name": "Dock Logistics User",
                "login": "dock.logistics.activity",
                "group_ids": [(6, 0, [logistics.id])],
                "notification_type": "inbox",
            }
        )

    def test_sale_order_default_is_appointment(self):
        defaults = self.env["sale.order"].default_get(["delivery_term"])
        self.assertEqual(defaults["delivery_term"], "appointment")
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        self.assertEqual(order.delivery_term, "appointment")

    def test_confirmation_creates_one_activity_and_sends_no_mail(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.buyer.id,
                "partner_shipping_id": self.site.id,
                "delivery_term": "appointment",
                "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1.0, "price_unit": 1.0})],
            }
        )
        order.action_confirm()
        activities = self.env["mail.activity"].search(
            [("res_model", "=", "sale.order"), ("res_id", "=", order.id), ("summary", "=", _SUMMARY)]
        )
        self.assertEqual(len(activities), 1)
        activity = activities
        self.assertTrue(activity.user_id.has_group("plasticos_security_base.group_logistics"))
        note = activity.note or ""
        self.assertIn("North Receiving Site", note)
        self.assertIn("Expected ready date:", note)
        self.assertIsNone(re.search(r"Expected ready date:\s*\S", note))
        self.assertFalse(order.appointment_requested)
        self.assertFalse(order.appointment_requested_on)
        self.assertFalse(
            self.env["mail.mail"].search(
                [
                    ("model", "=", "sale.order"),
                    ("res_id", "=", order.id),
                    ("subject", "ilike", "Dock Appointment"),
                ]
            )
        )
        order._plasticos_request_delivery_appointment_activity()
        self.assertEqual(
            self.env["mail.activity"].search_count(
                [("res_model", "=", "sale.order"), ("res_id", "=", order.id), ("summary", "=", _SUMMARY)]
            ),
            1,
        )
