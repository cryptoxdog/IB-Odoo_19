"""Cron effects for the methods ir.cron actually calls.

Each test asserts a field on a record it created. A second call must not
repeat that effect. Helpers that swallow exceptions are not used.
"""

from datetime import timedelta

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

_OFFER_STATES = ("draft", "sent", "responded")
_SLA_STATES = ("awaiting_ready", "ready_confirmed", "rate_confirmed", "scheduled", "dispatched")
_SCALE_STATES = ("delivered", "closed", "invoiced")


def _log_count(env, model_name, res_id, action_type):
    return env["plasticos.automation.log"].search_count(
        [
            ("model_name", "=", model_name),
            ("res_id", "=", res_id),
            ("action_type", "=", action_type),
        ]
    )


@tagged("post_install", "-at_install", "cron", "idempotency")
class TestCronInDomain(PlasticosTestCase):
    """One in-domain record per live cron, then the cron's own second-call guard."""

    def test_offer_expire_in_domain(self):
        offer_model = self.env["plasticos.offer"]
        past = fields.Date.today() - timedelta(days=1)
        supplier = self.env["res.partner"].create({"name": "Cron Supplier", "is_company": True})
        buyer = self.env["res.partner"].create({"name": "Cron Buyer", "is_company": True})
        intake = self._create_intake(partner=supplier)
        self.assertTrue(intake)
        past_offer = offer_model.create(
            {
                "intake_id": intake.id,
                "supplier_id": supplier.id,
                "buyer_id": buyer.id,
                "valid_until": past,
                "state": "sent",
            }
        )
        future_offer = offer_model.create(
            {
                "intake_id": intake.id,
                "supplier_id": supplier.id,
                "buyer_id": buyer.id,
                "valid_until": fields.Date.today() + timedelta(days=1),
                "state": "draft",
            }
        )
        ahead = offer_model.search_count(
            [
                ("state", "in", _OFFER_STATES),
                ("id", "!=", past_offer.id),
                "|",
                ("valid_until", "<", past),
                "&",
                ("valid_until", "=", past),
                ("id", "<", past_offer.id),
            ]
        )
        self.assertLess(ahead, 500, f"plasticos.offer sort prefix already has {ahead} rows; limit is 500")
        offer_model.cron_expire_offers()
        past_offer.invalidate_recordset()
        future_offer.invalidate_recordset()
        self.assertEqual(past_offer.state, "expired")
        self.assertEqual(future_offer.state, "draft")
        offer_model.cron_expire_offers()
        past_offer.invalidate_recordset()
        future_offer.invalidate_recordset()
        self.assertEqual(past_offer.state, "expired")
        self.assertEqual(future_offer.state, "draft")

    def test_sale_approval_in_domain(self):
        order_model = self.env["sale.order"]
        config = self.env["plasticos.automation.config"].get_config()
        domain = [
            ("amount_total", ">", config.sale_approval_threshold),
            ("state", "=", "draft"),
            ("requires_approval", "=", False),
        ]
        waiting = order_model.search_count(domain)
        self.assertLess(waiting, 500, f"sale.order domain already has {waiting} rows; limit is 500")
        buyer = self.env["res.partner"].create({"name": "Approval Buyer", "is_company": True})
        product = self.env["product.product"].create({"name": "Approval Product", "type": "consu"})
        order = order_model.create(
            {
                "partner_id": buyer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": config.sale_approval_threshold + 5000,
                        },
                    )
                ],
            }
        )
        self.assertFalse(order.requires_approval)
        order_model.cron_flag_sale_approvals()
        order.invalidate_recordset()
        self.assertTrue(order.requires_approval)
        self.assertEqual(_log_count(self.env, "sale.order", order.id, "approval_flag"), 1)
        order_model.cron_flag_sale_approvals()
        self.assertEqual(_log_count(self.env, "sale.order", order.id, "approval_flag"), 1)

    def test_invoice_reminder_in_domain(self):
        move_model = self.env["account.move"]
        config = self.env["plasticos.automation.config"].get_config()
        due = fields.Date.to_date("1900-01-01")
        cutoff = fields.Date.today() - timedelta(days=config.invoice_overdue_days)
        older = move_model.search_count(
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "!=", "paid"),
                ("invoice_date_due", "<", due),
                ("invoice_date_due", "<=", cutoff),
            ]
        )
        self.assertLess(older, 200, f"account.move domain already has {older} rows; limit is 200")
        partner = self.env["res.partner"].create({"name": "Overdue Buyer", "is_company": True})
        journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )
        if not journal:
            journal = self.env["account.journal"].create({"name": "Cron Sale Journal", "type": "sale", "code": "CSJRN"})
        product = self.env["product.product"].create({"name": "Reminder Product", "type": "consu"})
        invoice = move_model.create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": journal.id,
                "invoice_date": due,
                "invoice_date_due": due,
                "invoice_line_ids": [
                    (0, 0, {"product_id": product.id, "quantity": 1, "price_unit": 25}),
                ],
            }
        )
        invoice.action_post()
        move_model.cron_invoice_reminder()
        invoice.invalidate_recordset()
        self.assertEqual(invoice.last_reminder_date, fields.Date.today())
        self.assertEqual(_log_count(self.env, "account.move", invoice.id, "invoice_reminder"), 1)
        move_model.cron_invoice_reminder()
        self.assertEqual(_log_count(self.env, "account.move", invoice.id, "invoice_reminder"), 1)

    def test_contract_renewal_in_domain(self):
        partner_model = self.env["res.partner"]
        today = fields.Date.today()
        same_day = partner_model.search_count(
            [
                ("contract_end_date", "=", today),
                ("contract_end_date", "!=", False),
            ]
        )
        self.assertLess(same_day, 200, f"res.partner domain already has {same_day} rows; limit is 200")
        partner = partner_model.create(
            {"name": "Renewal Co", "is_company": True, "contract_end_date": today},
        )
        partner_model.cron_contract_renewal_alert()
        self.assertEqual(_log_count(self.env, "res.partner", partner.id, "contract_alert"), 1)
        partner_model.cron_contract_renewal_alert()
        self.assertEqual(_log_count(self.env, "res.partner", partner.id, "contract_alert"), 1)

    def test_stock_reorder_in_domain(self):
        product_model = self.env["product.product"]
        waiting = product_model.search_count([("type", "in", ("product", "consu"))])
        self.assertLess(waiting, 500, f"product.product domain already has {waiting} rows; limit is 500")
        product = product_model.create(
            {"name": "Low Stock", "type": "consu", "min_stock_threshold": 10},
        )
        product_model.cron_stock_reorder_alert()
        self.assertEqual(_log_count(self.env, "product.product", product.id, "stock_alert"), 1)
        product_model.cron_stock_reorder_alert()
        self.assertEqual(_log_count(self.env, "product.product", product.id, "stock_alert"), 1)

    def test_claim_sla_in_domain(self):
        claim_model = self.env["plasticos.claim"]
        opened = fields.Datetime.to_datetime("2000-01-01 00:00:00")
        claim = self._create_claim(opened_at=opened, sla_hours=1, state="pending")
        self.assertTrue(claim)
        pending_ahead = claim_model.search_count(
            [
                ("state", "=", "pending"),
                ("id", "!=", claim.id),
                "|",
                ("opened_at", "<", opened),
                "&",
                ("opened_at", "=", opened),
                ("id", "<", claim.id),
            ]
        )
        self.assertLess(
            pending_ahead, 300, f"plasticos.claim sort prefix already has {pending_ahead} rows; limit is 300"
        )
        resolved = self._create_claim(state="resolved", resolution_note="Cron test resolution")
        self.assertTrue(resolved)
        claim_model._cron_check_sla()
        claim.invalidate_recordset()
        self.assertEqual(claim.state, "escalated")
        reminder_ahead = claim_model.search_count(
            [
                ("state", "in", ("pending", "in_progress", "escalated")),
                ("id", "!=", claim.id),
                ("last_reminder_at", "=", False),
                "|",
                ("opened_at", "<", claim.opened_at),
                "&",
                ("opened_at", "=", claim.opened_at),
                ("id", "<", claim.id),
            ]
        )
        self.assertLess(
            reminder_ahead,
            300,
            f"plasticos.claim reminder prefix already has {reminder_ahead} rows; limit is 300",
        )
        summary = f"Open Claim Reminder: {claim.name}"
        activity_domain = [
            ("res_model", "=", "plasticos.claim"),
            ("res_id", "=", claim.id),
            ("summary", "=", summary),
            ("date_deadline", "=", fields.Date.today()),
        ]
        self.assertEqual(self.env["mail.activity"].search_count(activity_domain), 1)
        claim_model._cron_check_sla()
        self.assertEqual(self.env["mail.activity"].search_count(activity_domain), 1)
        resolved.invalidate_recordset()
        self.assertEqual(resolved.state, "resolved")

    def test_batch_normalize_in_domain(self):
        intake_model = self.env["plasticos.intake"]
        config = self.env["plasticos.normalizer.config"].get_config()
        limit = config.batch_limit or 200
        pending = intake_model.search_count([("normalized", "=", False), ("match_status", "=", "pending")])
        self.assertLess(pending, limit, f"plasticos.intake domain already has {pending} rows; limit is {limit}")
        intake = self._create_intake(density_value=-1.0)
        self.assertTrue(intake)
        self.assertEqual(intake.match_status, "pending")
        intake_model.cron_batch_normalize()
        intake.invalidate_recordset()
        self.assertEqual(intake.match_status, "error")
        self.assertFalse(intake.normalized)
        errors = intake.normalization_errors
        self.assertTrue(errors)
        intake_model.cron_batch_normalize()
        intake.invalidate_recordset()
        self.assertEqual(intake.normalization_errors, errors)
        self.assertEqual(intake.match_status, "error")

    def test_load_sla_in_domain(self):
        from odoo.addons.plasticos_logistics.models.load import (
            _FREIGHT_INTERNAL_WRITE,
            _FREIGHT_INTERNAL_WRITE_TOKEN,
        )

        load_model = self.env["plasticos.load"]
        entered = fields.Datetime.now() - timedelta(hours=100)
        load = load_model.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).create(
            {"state": "awaiting_ready", "entered_state_at": entered},
        )
        ahead = load_model.search_count(
            [
                ("state", "in", list(_SLA_STATES)),
                ("id", "!=", load.id),
                "|",
                ("entered_state_at", "=", False),
                "|",
                ("entered_state_at", "<", entered),
                "&",
                ("entered_state_at", "=", entered),
                ("id", "<", load.id),
            ]
        )
        self.assertLess(ahead, 500, f"plasticos.load sort prefix already has {ahead} rows; limit is 500")
        load_model.cron_load_sla_check()
        load.invalidate_recordset()
        self.assertTrue(load.sla_breached)
        logs = _log_count(self.env, "plasticos.load", load.id, "logistics_escalation")
        self.assertEqual(logs, 1)
        load_model.cron_load_sla_check()
        self.assertEqual(_log_count(self.env, "plasticos.load", load.id, "logistics_escalation"), logs)

    def test_missing_docs_leaves_inactive_transaction(self):
        """Negative only. create_date cannot be aimed, and the status rule needs age."""
        transaction = self._create_transaction(name="TX-CRON-DRAFT", state="draft")
        self.assertTrue(transaction)
        status = transaction.missing_doc_status
        self.env["plasticos.transaction"].cron_check_missing_docs()
        self.env["plasticos.transaction"].cron_check_missing_docs()
        transaction.invalidate_recordset()
        self.assertEqual(transaction.missing_doc_status, status)
        self.assertNotEqual(transaction.state, "active")

    def test_scale_tickets_leave_unloaded_transaction(self):
        """Negative only. create_date cannot be aimed, and a new row is not old enough."""
        transaction = self._create_transaction(name="TX-CRON-SCALE", state="draft")
        self.assertTrue(transaction)
        self.assertFalse(transaction.load_id)
        self.env["plasticos.transaction"].cron_check_scale_tickets()
        self.env["plasticos.transaction"].cron_check_scale_tickets()
        transaction.invalidate_recordset()
        self.assertFalse(transaction.scale_ticket_escalated)

    def test_geo_backfill_skips_partner_without_address(self):
        """Negative only. An addressed partner calls Nominatim."""
        partner = self.env["res.partner"].create({"name": "No Address Co", "is_company": True})
        self.assertFalse(partner.street)
        self.assertFalse(partner.city)
        latitude = partner.partner_latitude
        self.env["res.partner"].cron_geo_backfill()
        self.env["res.partner"].cron_geo_backfill()
        partner.invalidate_recordset()
        self.assertAlmostEqual(partner.partner_latitude, latitude, places=5)

    def test_midnight_recompute_refreshes_stale_stored_flags(self):
        claim_model = self.env["plasticos.claim"]
        open_claims = claim_model.search_count([("state", "not in", ("resolved", "archived"))])
        self.assertLess(open_claims, 1000, f"plasticos.claim open set already has {open_claims} rows; limit is 1000")
        claim = self._create_claim(opened_at=fields.Datetime.to_datetime("2000-01-01 00:00:00"), sla_hours=1)
        self.assertTrue(claim)
        if claim._table != "plasticos_claim":
            self.fail(f"plasticos.claim table is {claim._table}")
        self.env.cr.execute(
            'UPDATE "plasticos_claim" SET is_overdue = FALSE WHERE id = %s',
            [claim.id],
        )
        attachment = self.env["ir.attachment"].create(
            {
                "name": "midnight.txt",
                "datas": "bWlkbmlnaHQ=",
                "res_model": "plasticos.claim",
                "res_id": claim.id,
            }
        )
        tag = self.env["plasticos.document.tag"].create({"name": "Midnight Tag", "code": f"MID-{claim.id}"})
        document = self.env["plasticos.document"].create(
            {
                "name": "Midnight Doc",
                "res_model": "plasticos.claim",
                "res_id": claim.id,
                "attachment_id": attachment.id,
                "tag_id": tag.id,
            }
        )
        today = fields.Date.today()
        stale_documents = self.env["plasticos.document"].search_count(
            [
                ("expiry_date", "<=", today),
                ("is_expired", "=", False),
                ("active", "=", True),
            ]
        )
        self.assertLess(
            stale_documents,
            1000,
            f"plasticos.document expiry search already has {stale_documents} rows; limit is 1000",
        )
        if document._table != "plasticos_document":
            self.fail(f"plasticos.document table is {document._table}")
        self.env.cr.execute(
            'UPDATE "plasticos_document" SET expiry_date = %s, is_expired = FALSE WHERE id = %s',
            [today - timedelta(days=1), document.id],
        )
        claim.invalidate_recordset()
        document.invalidate_recordset()
        if claim.is_overdue:
            self.fail("is_overdue recomputed true before the cron; the stale row was not preserved")
        if document.is_expired:
            self.fail("is_expired recomputed true before the cron; the stale row was not preserved")
        service = self.env["plasticos.midnight.recompute"]
        service._cron_midnight_recompute()
        claim.invalidate_recordset()
        document.invalidate_recordset()
        self.assertTrue(claim.is_overdue)
        self.assertTrue(document.is_expired)
        service._cron_midnight_recompute()
        claim.invalidate_recordset()
        document.invalidate_recordset()
        self.assertTrue(claim.is_overdue)
        self.assertTrue(document.is_expired)

    def test_logistics_escalation_marks_sla_load(self):
        from odoo.addons.plasticos_logistics.models.load import (
            _FREIGHT_INTERNAL_WRITE,
            _FREIGHT_INTERNAL_WRITE_TOKEN,
        )

        load_model = self.env["plasticos.load"]
        waiting = load_model.search_count([("state", "in", list(_SLA_STATES))])
        self.assertLess(waiting, 500, f"plasticos.load SLA states already have {waiting} rows; limit is 500")
        entered = fields.Datetime.now() - timedelta(hours=100)
        load = load_model.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).create(
            {"state": "awaiting_ready", "entered_state_at": entered},
        )
        self.assertFalse(load.sla_breached)
        load_model._cron_escalation_check()
        load.invalidate_recordset()
        self.assertTrue(load.sla_breached)
        self.assertEqual(load.state, "awaiting_ready")
        load_model._cron_escalation_check()
        load.invalidate_recordset()
        self.assertTrue(load.sla_breached)
        self.assertEqual(load.state, "awaiting_ready")

    def test_monthly_audit_logs_closed_transaction(self):
        transaction_model = self.env["plasticos.transaction"]
        if "commission_locked" not in transaction_model._fields:
            self.fail(
                "commission_locked is absent; the warning domain is gross_margin < 0 "
                "and this computed margin is not negative"
            )
        waiting = transaction_model.search_count(
            [
                ("state", "=", "closed"),
                "|",
                ("gross_margin", "<", 0),
                ("commission_locked", "=", False),
            ]
        )
        self.assertLess(waiting, 500, f"plasticos.transaction audit domain already has {waiting} rows; limit is 500")
        transaction = self._create_transaction(name="TX-CRON-AUDIT", state="closed")
        self.assertTrue(transaction)
        state = transaction.state
        margin = transaction.gross_margin
        with self.assertLogs("odoo.addons.plasticos_transaction.models.audit_cron", level="WARNING") as caught:
            self.env["plasticos.audit.cron"].run_monthly_audit()
        self.assertTrue(any("Monthly audit:" in message for message in caught.output))
        transaction.invalidate_recordset()
        self.assertEqual(transaction.state, state)
        self.assertAlmostEqual(transaction.gross_margin, margin, places=5)
