"""Supplier-confirmation escalation is owned by an Operations Manager, never the salesperson.

Operator decision: an unresolved exception goes to manager-level personnel. With no eligible
manager it is logged and noted once on the transaction; it is never assigned to the
salesperson or to the acting user, and it is never dropped.
"""

from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

LOGGER = "odoo.addons.plasticos_base.models.res_users"
GROUP = "plasticos_security_base.group_operations_manager"


@tagged("post_install", "-at_install", "escalation_routing")
class TestSupplierConfirmationEscalation(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Escalation Routing Partner", "is_company": True, "customer_rank": 1, "supplier_rank": 1}
        )
        internal = cls.env.ref("base.group_user")
        cls.sales = cls.env["res.users"].create(
            {"name": "tx.esc.sales", "login": "tx.esc.sales", "group_ids": [(6, 0, [internal.id])]}
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "tx.esc.manager",
                "login": "tx.esc.manager",
                "group_ids": [(6, 0, [internal.id, cls.env.ref(GROUP).id])],
            }
        )
        cls.cron_user = cls.env.ref("plasticos_base.user_system_cron")

    def _transaction(self, name, **vals):
        values = {
            "name": name,
            "supplier_id": self.partner.id,
            "buyer_id": self.partner.id,
            "quantity": 44000,
            "user_id": self.sales.id,
        }
        values.update(vals)
        return self.env["plasticos.transaction"].create(values)

    def _activities(self, transaction):
        return self.env["mail.activity"].search(
            [
                ("res_model", "=", "plasticos.transaction"),
                ("res_id", "=", transaction.id),
                ("summary", "=", f"ESCALATION: Supplier confirmation pending on {transaction.name}"),
            ]
        )

    def _notes(self, transaction):
        transaction.invalidate_recordset(["message_ids"])
        return transaction.message_ids.filtered(lambda message: "Not routed:" in (message.body or ""))

    def test_manager_receives_and_the_salesperson_never_does(self):
        transaction = self._transaction("TX-ESC-ROUTE-MANAGER")
        self.assertEqual(transaction.user_id, self.sales)
        transaction._escalate_supplier_confirmation()
        activities = self._activities(transaction)
        self.assertEqual(len(activities), 1)
        self.assertTrue(activities.user_id.has_group(GROUP))
        self.assertNotIn(activities.user_id, self.sales | self.cron_user | self.env.user)
        self.assertFalse(self._notes(transaction))

    def test_rerun_on_the_same_day_adds_no_activity(self):
        transaction = self._transaction("TX-ESC-ROUTE-RERUN")
        transaction._escalate_supplier_confirmation()
        transaction._escalate_supplier_confirmation()
        self.assertEqual(len(self._activities(transaction)), 1)

    def test_the_order_company_scopes_the_manager(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        transaction = self._transaction("TX-ESC-ROUTE-COMPANY", sale_order_id=order.id)
        seen = []
        users = type(self.env["res.users"])
        original = users._plasticos_escalation_manager

        def recorder(self, group_xmlid, company=None):
            seen.append((group_xmlid, company))
            return original(self, group_xmlid, company)

        with patch.object(users, "_plasticos_escalation_manager", recorder):
            transaction._escalate_supplier_confirmation()
        self.assertEqual(seen, [(GROUP, order.company_id)])

    def test_no_manager_logs_notes_once_and_assigns_nobody(self):
        transaction = self._transaction("TX-ESC-ROUTE-NOBODY")
        users = type(self.env["res.users"])
        with patch.object(
            users, "_plasticos_escalation_manager", lambda self, group_xmlid, company=None: self.browse()
        ):
            with self.assertLogs(LOGGER, level="ERROR") as captured:
                transaction._escalate_supplier_confirmation()
            with self.assertLogs(LOGGER, level="ERROR"):
                transaction._escalate_supplier_confirmation()
        self.assertTrue(any("Not routed: supplier confirmation escalation." in line for line in captured.output))
        self.assertEqual(len(self._notes(transaction)), 1)
        self.assertFalse(
            self._activities(transaction), "neither the salesperson nor the acting user takes the escalation"
        )
