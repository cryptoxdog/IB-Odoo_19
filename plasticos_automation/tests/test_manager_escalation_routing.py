"""Follow-up and SLA escalations are owned by an Operations Manager (operator decision).

The supplier-readiness, trucker-receipt and load-SLA jobs never assign an escalation to the
record's own user or to the cron user. With no eligible manager the record carries one
"Not routed" note and the server log carries an error.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged

LOGGER = "odoo.addons.plasticos_base.models.res_users"
GROUP = "plasticos_security_base.group_operations_manager"
LONG_AGO = datetime(2000, 1, 1)


def _nobody(self, group_xmlid, company=None):
    return self.browse()


@tagged("post_install", "-at_install", "escalation_routing")
class TestManagerEscalationRouting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        internal = cls.env.ref("base.group_user")
        cls.sales = cls.env["res.users"].create(
            {"name": "auto.esc.sales", "login": "auto.esc.sales", "group_ids": [(6, 0, [internal.id])]}
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "auto.esc.manager",
                "login": "auto.esc.manager",
                "group_ids": [(6, 0, [internal.id, cls.env.ref(GROUP).id])],
            }
        )
        cls.cron_user = cls.env.ref("plasticos_base.user_system_cron")
        cls.users_cls = type(cls.env["res.users"])
        cls.supplier = cls.env["res.partner"].create(
            {"name": "Auto Esc Mill", "is_company": True, "supplier_rank": 1, "email": "mill@auto-esc.example"}
        )
        cls.buyer = cls.env["res.partner"].create({"name": "Auto Esc Buyer", "is_company": True, "customer_rank": 1})
        cls.carrier = cls.env["res.partner"].create(
            {"name": "Auto Esc Carrier", "is_company": True, "email": "truck@auto-esc.example"}
        )

    # ── helpers ──────────────────────────────────────────────────────────

    def _activities(self, record, summary):
        return self.env["mail.activity"].search(
            [("res_model", "=", record._name), ("res_id", "=", record.id), ("summary", "=", summary)]
        )

    def _notes(self, record):
        record.invalidate_recordset(["message_ids"])
        return record.message_ids.filtered(lambda message: "Not routed:" in (message.body or ""))

    def _assert_manager_owned(self, activities):
        self.assertEqual(len(activities), 1)
        self.assertTrue(activities.user_id.has_group(GROUP))
        self.assertNotIn(activities.user_id, self.sales | self.cron_user | self.env.user)

    def _recorded_companies(self, run):
        seen = []
        original = self.users_cls._plasticos_escalation_manager

        def recorder(self, group_xmlid, company=None):
            seen.append((group_xmlid, company))
            return original(self, group_xmlid, company)

        with patch.object(self.users_cls, "_plasticos_escalation_manager", recorder):
            run()
        return seen

    # ── supplier readiness (purchase.order) ──────────────────────────────

    def _order(self):
        order = self.env["purchase.order"].create({"partner_id": self.supplier.id, "user_id": self.sales.id})
        # Third follow-up due: the oldest clock sorts this order into the job's first page.
        order.write({"state": "purchase", "followup_count": 2, "last_followup_on": LONG_AGO})
        return order

    def _run_supplier_followup(self, order):
        self.env["purchase.order"].cron_supplier_followup()
        order.invalidate_recordset()
        # The job stamps "now"; age the clock so the next run follows up again.
        order.write({"last_followup_on": LONG_AGO})

    def test_supplier_readiness_goes_to_the_manager_once(self):
        order = self._order()
        summary = f"ESCALATION: Supplier readiness unconfirmed on {order.name}"
        seen = self._recorded_companies(lambda: self._run_supplier_followup(order))
        self.assertEqual(order.followup_count, 3)
        self.assertIn((GROUP, order.company_id), seen)
        self._assert_manager_owned(self._activities(order, summary))
        self._run_supplier_followup(order)
        self.assertEqual(order.followup_count, 4)
        self.assertEqual(len(self._activities(order, summary)), 1, "one open escalation per order")
        self.assertFalse(self._notes(order))

    def test_supplier_readiness_without_a_manager_is_logged_and_noted_once(self):
        order = self._order()
        with patch.object(self.users_cls, "_plasticos_escalation_manager", _nobody):
            with self.assertLogs(LOGGER, level="ERROR") as captured:
                self._run_supplier_followup(order)
            with self.assertLogs(LOGGER, level="ERROR"):
                self._run_supplier_followup(order)
        self.assertTrue(any("Not routed: supplier readiness escalation." in line for line in captured.output))
        self.assertEqual(len(self._notes(order)), 1)
        self.assertFalse(self._activities(order, f"ESCALATION: Supplier readiness unconfirmed on {order.name}"))

    # ── trucker receipt (stock.picking) ──────────────────────────────────

    def _picking(self):
        warehouse = self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": warehouse.out_type_id.id,
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "partner_id": self.buyer.id,
                "carrier_id": self.carrier.id,
                "user_id": self.sales.id,
            }
        )
        picking.write({"trucker_followup_count": 2, "trucker_notified_on": LONG_AGO})
        return picking

    def _run_trucker_followup(self, picking):
        self.env["stock.picking"].cron_trucker_followup()
        picking.invalidate_recordset()
        picking.write({"trucker_notified_on": LONG_AGO})

    def test_trucker_receipt_goes_to_the_manager_once(self):
        picking = self._picking()
        summary = f"ESCALATION: Trucker receipt unconfirmed on {picking.name}"
        seen = self._recorded_companies(lambda: self._run_trucker_followup(picking))
        self.assertEqual(picking.trucker_followup_count, 3)
        self.assertIn((GROUP, picking.company_id), seen)
        self._assert_manager_owned(self._activities(picking, summary))
        self._run_trucker_followup(picking)
        self.assertEqual(picking.trucker_followup_count, 4)
        self.assertEqual(len(self._activities(picking, summary)), 1, "one open escalation per picking")
        self.assertFalse(self._notes(picking))

    def test_trucker_receipt_without_a_manager_is_logged_and_noted_once(self):
        picking = self._picking()
        with patch.object(self.users_cls, "_plasticos_escalation_manager", _nobody):
            with self.assertLogs(LOGGER, level="ERROR") as captured:
                self._run_trucker_followup(picking)
            with self.assertLogs(LOGGER, level="ERROR"):
                self._run_trucker_followup(picking)
        self.assertTrue(any("Not routed: trucker receipt escalation." in line for line in captured.output))
        self.assertEqual(len(self._notes(picking)), 1)
        self.assertFalse(self._activities(picking, f"ESCALATION: Trucker receipt unconfirmed on {picking.name}"))

    # ── load SLA (plasticos.load) ────────────────────────────────────────

    def _stuck_load(self, hours):
        load = self.env["plasticos.load"].create(
            {
                "company_id": self.env.company.id,
                "pickup_partner_id": self.supplier.id,
                "delivery_partner_id": self.buyer.id,
                "carrier_id": self.carrier.id,
            }
        )
        self._age(load, hours)
        return load

    def _age(self, load, hours):
        # A stuck legacy row: the state and its clock are written directly.
        self.env.cr.execute(
            "UPDATE plasticos_load SET state = 'awaiting_ready', entered_state_at = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(hours=hours), load.id),
        )
        load.invalidate_recordset()

    def _sla_summary(self, load, level):
        return f"ESCALATION: SLA breach [{level}] on {load.name}"

    def test_sla_breach_creates_one_manager_activity_per_level(self):
        load = self._stuck_load(60)  # awaiting_ready limit is 48h: a warning
        cron = self.env["plasticos.load"]
        seen = self._recorded_companies(cron.cron_load_sla_check)
        self.assertIn((GROUP, load.company_id), seen)
        self.assertEqual(load.escalation_level, "warning")
        self.assertTrue(load.sla_breached)
        self._assert_manager_owned(self._activities(load, self._sla_summary(load, "WARNING")))
        cron.cron_load_sla_check()
        self.assertEqual(len(self._activities(load, self._sla_summary(load, "WARNING"))), 1)
        self.assertFalse(self._activities(load, self._sla_summary(load, "CRITICAL")))

        self._age(load, 120)  # past twice the limit: critical
        cron.cron_load_sla_check()
        cron.cron_load_sla_check()
        self.assertEqual(load.escalation_level, "critical")
        self._assert_manager_owned(self._activities(load, self._sla_summary(load, "CRITICAL")))
        self.assertEqual(len(self._activities(load, self._sla_summary(load, "WARNING"))), 1)
        self.assertFalse(self._notes(load))

    def test_both_sla_jobs_share_one_activity(self):
        load = self._stuck_load(60)
        self.env["plasticos.load"]._cron_escalation_check()
        self.env["plasticos.load"].cron_load_sla_check()
        self.assertEqual(len(self._activities(load, self._sla_summary(load, "WARNING"))), 1)

    def test_a_load_inside_its_sla_gets_no_activity(self):
        load = self._stuck_load(2)
        self.env["plasticos.load"].cron_load_sla_check()
        self.assertFalse(load.sla_breached)
        self.assertFalse(
            self.env["mail.activity"].search(
                [("res_model", "=", "plasticos.load"), ("res_id", "=", load.id), ("summary", "ilike", "SLA breach")]
            )
        )

    def test_sla_breach_without_a_manager_is_logged_and_noted_once(self):
        load = self._stuck_load(60)
        with patch.object(self.users_cls, "_plasticos_escalation_manager", _nobody):
            with self.assertLogs(LOGGER, level="ERROR") as captured:
                self.env["plasticos.load"].cron_load_sla_check()
            self.env["plasticos.load"].cron_load_sla_check()
        self.assertTrue(any("Not routed: SLA breach warning escalation." in line for line in captured.output))
        self.assertEqual(len(self._notes(load)), 1)
        self.assertFalse(self._activities(load, self._sla_summary(load, "WARNING")))
