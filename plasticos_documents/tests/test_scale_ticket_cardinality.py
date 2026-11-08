"""Per-load scale tickets, fair cron pages, and the column-rename boundary."""

import importlib.util
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_logistics.models.load import (
    _FREIGHT_INTERNAL_WRITE,
    _FREIGHT_INTERNAL_WRITE_TOKEN,
)
from odoo.exceptions import UserError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _align_module():
    path = get_module_path("plasticos_documents") + "/migrations/19.0.2.2.0/pre-migrate.py"
    spec = importlib.util.spec_from_file_location("plasticos_documents_align_19220", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install")
class TestScaleTicketCardinality(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.buyer = cls.env["res.partner"].create({"name": "Scale Buyer", "customer_rank": 1})
        cls.supplier = cls.env["res.partner"].create({"name": "Scale Supplier", "supplier_rank": 1})
        cls.tag = cls.env["plasticos.document.tag"].search([("code", "=", "SCALE")], limit=1)
        if not cls.tag:
            cls.tag = cls.env["plasticos.document.tag"].create({"name": "Scale Ticket", "code": "SCALE"})

    def _delivered_load(self, name):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        tx = self.env["plasticos.transaction"].create(
            {
                "name": name,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "sale_order_id": order.id,
            }
        )
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        tx.with_context(bypass_state_guard=True).write({"state": "delivered"})
        when = fields.Datetime.now() - timedelta(days=30)
        load.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write(
            {"state": "delivered", "delivered_at": when, "dispatched_at": when}
        )
        return tx, load

    def test_locked_load_accepts_only_the_scale_ticket_status_write(self):
        _tx, load = self._delivered_load("TX-SCALE-LOCK")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            load.write({"scale_ticket_reminder_sent": True})
        self.assertFalse(load.scale_ticket_reminder_sent)
        load._write_scale_ticket_status({"scale_ticket_reminder_sent": True, "scale_ticket_escalated": True})
        self.assertTrue(load.scale_ticket_reminder_sent)
        self.assertTrue(load.scale_ticket_escalated)
        self.assertEqual(load.state, "delivered")

    def test_cron_pages_past_the_first_batch_and_replays(self):
        loads = []
        for index in range(5):
            _tx, load = self._delivered_load(f"TX-SCALE-PAGE-{index}")
            loads.append(load)
        cursor_key = "plasticos_documents.scale_ticket_scan_cursor"
        self.env["ir.config_parameter"].set_param(cursor_key, str(loads[0].id - 1))
        seen = self.env["plasticos.load"]
        model = self.env["plasticos.transaction"].with_context(scale_ticket_batch_size=2)
        for _page in range(3):
            seen |= model._next_scale_ticket_batch(2)
        self.assertTrue(set(load.id for load in loads).issubset(set(seen.ids)))
        self.env["ir.config_parameter"].set_param(cursor_key, str(loads[0].id - 1))
        empty_group = self.env["res.groups"].create({"name": "Empty Scale Managers"})
        cron = self.env["plasticos.transaction"].with_context(scale_ticket_batch_size=10)
        with patch.object(type(cron), "_scale_ticket_manager_group", lambda self: empty_group):
            result = cron.cron_check_scale_tickets()
        self.assertGreaterEqual(result["failures"], 1)
        self.assertTrue(all(load.scale_ticket_reminder_sent for load in loads))
        self.assertTrue(all(not load.scale_ticket_escalated for load in loads))
        noted = {load.id: len(load.message_ids) for load in loads}
        self.env["ir.config_parameter"].set_param(cursor_key, str(loads[0].id - 1))
        with patch.object(type(cron), "_scale_ticket_manager_group", lambda self: empty_group):
            cron.cron_check_scale_tickets()
        self.assertEqual({load.id: len(load.message_ids) for load in loads}, noted)

    def test_one_load_failure_does_not_stop_the_next_load(self):
        _tx_a, first = self._delivered_load("TX-SCALE-FAIL-A")
        _tx_b, second = self._delivered_load("TX-SCALE-FAIL-B")
        self.env["ir.config_parameter"].set_param(
            "plasticos_documents.scale_ticket_scan_cursor", str(min(first.id, second.id) - 1)
        )
        original = type(self.env["plasticos.transaction"])._record_scale_ticket_reminder

        def explode(self, load, bd_since_delivery):
            if load == first:
                raise UserError("reminder failed")
            return original(self, load, bd_since_delivery)

        model = self.env["plasticos.transaction"].with_context(scale_ticket_batch_size=10)
        manager = self.env["res.users"].create(
            {
                "name": "Scale Manager",
                "login": "scale.manager.cardinality",
                "group_ids": [(4, self.env.ref("plasticos_security_base.group_logistics").id)],
            }
        )
        with (
            patch.object(type(model), "_record_scale_ticket_reminder", explode),
            patch.object(type(model), "_get_logistics_manager", lambda self, group: manager),
        ):
            result = model.cron_check_scale_tickets()
        self.assertGreaterEqual(result["failures"], 1)
        self.assertTrue(second.scale_ticket_reminder_sent)
        self.assertFalse(first.scale_ticket_reminder_sent)
        retry_key = "plasticos_documents.scale_ticket_retry_ids"
        stored = self.env["ir.config_parameter"].get_param(retry_key) or ""
        self.assertIn(str(first.id), stored.split(","))
        model.cron_check_scale_tickets()
        self.assertTrue(first.scale_ticket_reminder_sent)
        stored_after = self.env["ir.config_parameter"].get_param(retry_key) or ""
        self.assertNotIn(str(first.id), [part.strip() for part in stored_after.split(",") if part.strip()])

    def test_more_than_300_loads_are_not_stranded(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        tx = self.env["plasticos.transaction"].create(
            {
                "name": "TX-SCALE-301",
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "sale_order_id": order.id,
            }
        )
        loads = self.env["plasticos.load"].create([{"sale_order_id": order.id} for _index in range(301)])
        tx.with_context(bypass_state_guard=True).write({"state": "delivered"})
        when = fields.Datetime.now() - timedelta(days=30)
        loads.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write(
            {"state": "delivered", "delivered_at": when, "dispatched_at": when}
        )
        model = self.env["plasticos.transaction"]
        self.env["ir.config_parameter"].set_param(
            "plasticos_documents.scale_ticket_scan_cursor", str(min(loads.ids) - 1)
        )
        first_page = model._next_scale_ticket_batch(300)
        second_page = model._next_scale_ticket_batch(300)
        self.assertEqual(len(first_page), 300)
        self.assertIn(max(loads.ids), second_page.ids)

    def test_column_rename_refuses_contradictions_and_replays(self):
        module = _align_module()
        cr = self.env.cr
        cr.execute(
            """
            CREATE TABLE plasticos_column_align_probe (
                id serial PRIMARY KEY,
                old_flag boolean,
                new_flag boolean
            )
            """
        )
        cr.execute("INSERT INTO plasticos_column_align_probe (old_flag, new_flag) VALUES (TRUE, FALSE)")
        with self.assertRaises(RuntimeError), self.env.cr.savepoint():
            module._align_columns(cr, "plasticos_column_align_probe", [("old_flag", "new_flag")])
        cr.execute("SELECT old_flag, new_flag FROM plasticos_column_align_probe")
        self.assertEqual(cr.fetchone(), (True, False))
        cr.execute("UPDATE plasticos_column_align_probe SET new_flag = NULL")
        module._align_columns(cr, "plasticos_column_align_probe", [("old_flag", "new_flag")])
        cr.execute(
            """
            SELECT column_name
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'plasticos_column_align_probe'
            """
        )
        names = {row[0] for row in cr.fetchall()}
        self.assertNotIn("old_flag", names)
        self.assertIn("new_flag", names)
        cr.execute("SELECT new_flag FROM plasticos_column_align_probe")
        self.assertTrue(cr.fetchone()[0])
        module._align_columns(cr, "plasticos_column_align_probe", [("old_flag", "new_flag")])
        cr.execute("SELECT new_flag FROM plasticos_column_align_probe")
        self.assertTrue(cr.fetchone()[0])
