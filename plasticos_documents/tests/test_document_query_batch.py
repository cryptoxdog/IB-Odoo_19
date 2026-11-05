"""Batched document reads keep the same transaction, reminder, and escalation results."""

import base64
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_logistics.models.load import (
    _FREIGHT_INTERNAL_WRITE,
    _FREIGHT_INTERNAL_WRITE_TOKEN,
)
from odoo.tests import TransactionCase, tagged

CONFLICT_MARKER = "Conflicting association withheld from evidence."


def _fixed_business_days(_start_date, _end_date):
    return 2


@tagged("post_install", "-at_install")
class TestDocumentQueryBatch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.buyer = cls.env["res.partner"].create({"name": "Query Batch Buyer", "customer_rank": 1})
        cls.supplier = cls.env["res.partner"].create(
            {"name": "Query Batch Supplier", "is_company": True, "supplier_rank": 1}
        )
        cls.tag = cls.env["plasticos.document.tag"].create({"name": "Query Batch Doc", "code": "QBATCHDOC"})

    def _attachment(self):
        return self.env["ir.attachment"].create(
            {
                "name": "query-batch.txt",
                "datas": base64.b64encode(b"query-batch"),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )

    def _document(self, **vals):
        values = {
            "name": "Query batch document",
            "tag_id": self.tag.id,
            "attachment_id": self._attachment().id,
        }
        values.update(vals)
        return self.env["plasticos.document"].create(values)

    def _transaction(self, name, order):
        return self.env["plasticos.transaction"].create(
            {
                "name": name,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "sale_order_id": order.id,
            }
        )

    def _escalation_count(self, transaction):
        summary = f"ESCALATION: Missing documents on {transaction.name}"
        return self.env["mail.activity"].search_count(
            [
                ("res_model", "=", "plasticos.transaction"),
                ("res_id", "=", transaction.id),
                ("summary", "=", summary),
                ("date_deadline", "=", date.today()),
            ]
        )

    def test_sale_order_batch_keeps_unique_match_and_conflict(self):
        order_one = self.env["sale.order"].create({"partner_id": self.buyer.id})
        order_two = self.env["sale.order"].create({"partner_id": self.buyer.id})
        tx_one = self._transaction("TX-QBATCH-ONE", order_one)
        tx_two_a = self._transaction("TX-QBATCH-TWO-A", order_two)
        tx_two_b = self._transaction("TX-QBATCH-TWO-B", order_two)
        load = self.env["plasticos.load"].create({"sale_order_id": order_one.id})
        self.assertEqual(load.transaction_id, tx_one)

        unique_doc = self._document(res_model="sale.order", res_id=order_one.id)
        duplicate_doc = self._document(res_model="sale.order", res_id=order_two.id)
        self.assertFalse(unique_doc.transaction_id)
        self.assertFalse(unique_doc.load_id)
        self.assertFalse(duplicate_doc.transaction_id)
        self.assertFalse(duplicate_doc.load_id)
        conflict = self._document(
            res_model="plasticos.load",
            res_id=load.id,
            load_id=load.id,
            transaction_id=tx_two_a.id,
        )
        self.assertTrue(conflict._association_conflict_reason())

        found = conflict._get_related_transactions(unique_doc | duplicate_doc | conflict)
        self.assertEqual(found, tx_one)
        self.assertNotIn(tx_two_a, found)
        self.assertNotIn(tx_two_b, found)
        self.assertFalse(conflict._get_related_transactions(conflict))
        self.assertIn(CONFLICT_MARKER, " ".join(conflict.message_ids.mapped("body")))

    def test_missing_doc_page_schedules_one_escalation_each(self):
        tag = self.env["plasticos.document.tag"].create({"name": "Query Batch Missing", "code": "QBATCHMISS"})
        self.env["plasticos.document.validation.matrix"].create(
            {"name": "Query Batch Supplier", "doc_category": "supplier", "tag_id": tag.id}
        )
        self.env["plasticos.document.rule"].create(
            {
                "name": "Query Batch Rule",
                "tag_id": tag.id,
                "res_model": "plasticos.transaction",
                "overdue_business_days": 1,
                "escalation_business_days": 1,
            }
        )
        already = self._transaction("TX-QBATCH-ALREADY", self.env["sale.order"].create({"partner_id": self.buyer.id}))
        sibling = self._transaction("TX-QBATCH-SIBLING", self.env["sale.order"].create({"partner_id": self.buyer.id}))
        self.assertEqual(
            date.today(),
            fields.Date.context_today(already),
            "date.today() differs from fields.Date.context_today; the deadline filter stays",
        )
        already.activity_schedule(
            "mail.mail_activity_data_todo",
            date_deadline=date.today(),
            summary=f"ESCALATION: Missing documents on {already.name}",
            user_id=self.env.user.id,
        )

        def _missing(self, res_model, res_id, purpose=None):
            return [tag.code]

        model = type(self.env["plasticos.transaction"])
        service = type(self.env["plasticos.compliance.service"])
        with (
            patch.object(service, "get_missing_documents", _missing),
            patch.object(model, "_count_business_days", staticmethod(_fixed_business_days)),
        ):
            page = already | sibling
            page._apply_missing_doc_page(page)
            self.assertEqual(self._escalation_count(already), 1)
            self.assertEqual(self._escalation_count(sibling), 1)
            page._apply_missing_doc_page(page)
            self.assertEqual(self._escalation_count(already), 1)
            self.assertEqual(self._escalation_count(sibling), 1)

    def test_missing_doc_cron_calls_the_page_once(self):
        calls = []

        def recorder(self, transactions):
            calls.append(transactions)

        with patch.object(type(self.env["plasticos.transaction"]), "_apply_missing_doc_page", recorder):
            self.env["plasticos.transaction"].cron_check_missing_docs()
        self.assertEqual(len(calls), 1)

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
        return load

    def _scale_escalation_count(self, load):
        summary = f"ESCALATION: Missing scale ticket on {load.name}"
        return self.env["mail.activity"].search_count(
            [("res_model", "=", "plasticos.load"), ("res_id", "=", load.id), ("summary", "=", summary)]
        )

    def _aim_scale_page(self, first_load):
        parameter = self.env["ir.config_parameter"]
        parameter.set_param("plasticos_documents.scale_ticket_retry_ids", "")
        parameter.set_param("plasticos_documents.scale_ticket_scan_cursor", str(first_load.id - 1))

    def test_scale_ticket_page_keeps_one_escalation_each(self):
        group = self.env.ref("plasticos_security_base.group_logistics", raise_if_not_found=False)
        self.assertTrue(group)
        if not self.env["res.users"].search([("group_ids", "in", group.id), ("active", "=", True)], limit=1):
            self.env.user.write({"group_ids": [fields.Command.link(group.id)]})
        if not self.env["res.users"].search([("group_ids", "in", group.id), ("active", "=", True)], limit=1):
            # The test user's own group write is not visible to this search.
            self.env["res.users"].create(
                {
                    "name": "Query Batch Logistics",
                    "login": "query.batch.logistics",
                    "group_ids": [fields.Command.link(group.id)],
                }
            )
        if not self.env["plasticos.document.tag"].search([("code", "=", "SCALE")], limit=1):
            self.env["plasticos.document.tag"].create({"name": "Scale Ticket", "code": "SCALE"})
        held = self._delivered_load("TX-QBATCH-SCALE-HELD")
        fresh = self._delivered_load("TX-QBATCH-SCALE-FRESH")
        self.assertFalse(held.scale_ticket_escalated)
        self.assertFalse(fresh.scale_ticket_escalated)
        held.activity_schedule(
            "mail.mail_activity_data_todo",
            summary=f"ESCALATION: Missing scale ticket on {held.name}",
            user_id=self.env.user.id,
        )
        cron = self.env["plasticos.transaction"].with_context(scale_ticket_batch_size=2)
        first = held if held.id <= fresh.id else fresh
        self._aim_scale_page(first)
        cron.cron_check_scale_tickets()
        self.assertEqual(self._scale_escalation_count(held), 1)
        self.assertTrue(held.scale_ticket_escalated)
        self.assertEqual(self._scale_escalation_count(fresh), 1)
        self.assertTrue(fresh.scale_ticket_escalated)
        self._aim_scale_page(first)
        cron.cron_check_scale_tickets()
        self.assertEqual(self._scale_escalation_count(held), 1)
        self.assertEqual(self._scale_escalation_count(fresh), 1)
