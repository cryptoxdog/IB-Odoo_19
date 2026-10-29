"""Out-of-domain cron proofs for the methods ir.cron actually calls.

A record outside the cron search domain keeps its fields across two calls.
These tests do not rewrite seed rows to fake an empty table.
"""

import logging
from datetime import timedelta

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

_AUDIT_LOGGER = "odoo.addons.plasticos_transaction.models.audit_cron"


class _WarningCapture(logging.Handler):
    """Collect warning text from the monthly-audit logger."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def _log_count(env, model_name, res_id, action_type):
    return env["plasticos.automation.log"].search_count(
        [
            ("model_name", "=", model_name),
            ("res_id", "=", res_id),
            ("action_type", "=", action_type),
        ]
    )


@tagged("post_install", "-at_install", "cron")
class TestCronOutOfDomain(PlasticosTestCase):
    """Records the live cron must not select."""

    def test_offer_expire_leaves_future_offer(self):
        supplier = self.env["res.partner"].create({"name": "Future Supplier", "is_company": True})
        buyer = self.env["res.partner"].create({"name": "Future Buyer", "is_company": True})
        intake = self._create_intake(partner=supplier)
        self.assertTrue(intake)
        offer = self.env["plasticos.offer"].create(
            {
                "intake_id": intake.id,
                "supplier_id": supplier.id,
                "buyer_id": buyer.id,
                "valid_until": fields.Date.today() + timedelta(days=1),
                "state": "draft",
            }
        )
        self.env["plasticos.offer"].cron_expire_offers()
        self.env["plasticos.offer"].cron_expire_offers()
        offer.invalidate_recordset()
        self.assertEqual(offer.state, "draft")

    def test_sale_approval_leaves_small_order(self):
        config = self.env["plasticos.automation.config"].get_config()
        buyer = self.env["res.partner"].create({"name": "Small Buyer", "is_company": True})
        product = self.env["product.product"].create({"name": "Small Product", "type": "consu"})
        order = self.env["sale.order"].create(
            {
                "partner_id": buyer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {"product_id": product.id, "product_uom_qty": 1, "price_unit": 0},
                    )
                ],
            }
        )
        self.assertLessEqual(order.amount_total, config.sale_approval_threshold)
        self.env["sale.order"].cron_flag_sale_approvals()
        self.env["sale.order"].cron_flag_sale_approvals()
        order.invalidate_recordset()
        self.assertFalse(order.requires_approval)
        self.assertEqual(_log_count(self.env, "sale.order", order.id, "approval_flag"), 0)

    def test_invoice_reminder_leaves_future_invoice(self):
        partner = self.env["res.partner"].create({"name": "Future Payer", "is_company": True})
        journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )
        if not journal:
            journal = self.env["account.journal"].create(
                {"name": "Cron Future Journal", "type": "sale", "code": "CFJRN"}
            )
        product = self.env["product.product"].create({"name": "Future Product", "type": "consu"})
        due = fields.Date.today() + timedelta(days=10)
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": journal.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_due": due,
                "invoice_line_ids": [
                    (0, 0, {"product_id": product.id, "quantity": 1, "price_unit": 25}),
                ],
            }
        )
        invoice.action_post()
        self.env["account.move"].cron_invoice_reminder()
        self.env["account.move"].cron_invoice_reminder()
        invoice.invalidate_recordset()
        self.assertFalse(invoice.last_reminder_date)
        self.assertEqual(_log_count(self.env, "account.move", invoice.id, "invoice_reminder"), 0)

    def test_contract_renewal_leaves_partner_without_end_date(self):
        partner = self.env["res.partner"].create({"name": "Open Contract Co", "is_company": True})
        self.assertFalse(partner.contract_end_date)
        self.env["res.partner"].cron_contract_renewal_alert()
        self.env["res.partner"].cron_contract_renewal_alert()
        self.assertEqual(_log_count(self.env, "res.partner", partner.id, "contract_alert"), 0)

    def test_stock_reorder_leaves_non_positive_threshold(self):
        product = self.env["product.product"].create(
            {"name": "Untracked Stock", "type": "consu", "min_stock_threshold": -1},
        )
        self.env["product.product"].cron_stock_reorder_alert()
        self.env["product.product"].cron_stock_reorder_alert()
        self.assertEqual(_log_count(self.env, "product.product", product.id, "stock_alert"), 0)

    def test_claim_sla_leaves_resolved_claim(self):
        claim = self._create_claim(state="resolved", resolution_note="Cron test resolution")
        self.assertTrue(claim)
        self.env["plasticos.claim"]._cron_check_sla()
        self.env["plasticos.claim"]._cron_check_sla()
        claim.invalidate_recordset()
        self.assertEqual(claim.state, "resolved")

    def test_batch_normalize_leaves_normalized_intake(self):
        intake = self._create_intake()
        self.assertTrue(intake)
        intake.write({"normalized": True, "match_status": "normalized"})
        self.env["plasticos.intake"].cron_batch_normalize()
        self.env["plasticos.intake"].cron_batch_normalize()
        intake.invalidate_recordset()
        self.assertTrue(intake.normalized)
        self.assertEqual(intake.match_status, "normalized")

    def test_load_sla_leaves_draft_load(self):
        load = self.env["plasticos.load"].create({})
        self.assertEqual(load.state, "draft")
        self.assertFalse(load.sla_breached)
        self.env["plasticos.load"].cron_load_sla_check()
        self.env["plasticos.load"].cron_load_sla_check()
        load.invalidate_recordset()
        self.assertFalse(load.sla_breached)
        self.assertEqual(_log_count(self.env, "plasticos.load", load.id, "logistics_escalation"), 0)

    def test_missing_docs_leaves_draft_transaction(self):
        """Negative only. create_date cannot be aimed, and the status rule needs age."""
        transaction = self._create_transaction(name="TX-CRON-MISS-OUT", state="draft")
        self.assertTrue(transaction)
        status = transaction.missing_doc_status
        self.env["plasticos.transaction"].cron_check_missing_docs()
        self.env["plasticos.transaction"].cron_check_missing_docs()
        transaction.invalidate_recordset()
        self.assertEqual(transaction.state, "draft")
        self.assertEqual(transaction.missing_doc_status, status)

    def test_scale_tickets_leave_draft_transaction(self):
        """Negative only. create_date cannot be aimed, and a new row is not old enough."""
        transaction = self._create_transaction(name="TX-CRON-SCALE-OUT", state="draft")
        self.assertTrue(transaction)
        self.env["plasticos.transaction"].cron_check_scale_tickets()
        self.env["plasticos.transaction"].cron_check_scale_tickets()
        transaction.invalidate_recordset()
        self.assertFalse(transaction.scale_ticket_escalated)

    def test_geo_backfill_leaves_blank_partner(self):
        """Negative only. An addressed partner calls Nominatim."""
        partner = self.env["res.partner"].create({"name": "Blank Geo Co", "is_company": True})
        latitude = partner.partner_latitude
        self.env["res.partner"].cron_geo_backfill()
        self.env["res.partner"].cron_geo_backfill()
        partner.invalidate_recordset()
        self.assertAlmostEqual(partner.partner_latitude, latitude, places=5)
        self.assertFalse(partner.street)
        self.assertFalse(partner.city)

    def test_midnight_recompute_leaves_new_claim(self):
        claim = self._create_claim()
        self.assertTrue(claim)
        state = claim.state
        self.assertIsNone(self.env["plasticos.midnight.recompute"]._cron_midnight_recompute())
        self.assertIsNone(self.env["plasticos.midnight.recompute"]._cron_midnight_recompute())
        claim.invalidate_recordset()
        self.assertEqual(claim.state, state)

    def test_logistics_escalation_leaves_draft_load(self):
        load = self.env["plasticos.load"].create({})
        self.env["plasticos.load"]._cron_escalation_check()
        self.env["plasticos.load"]._cron_escalation_check()
        load.invalidate_recordset()
        self.assertEqual(load.state, "draft")

    def test_monthly_audit_leaves_draft_transaction(self):
        """A draft transaction is outside the closed-transaction audit search."""
        transaction = self._create_transaction(name="TX-CRON-AUDIT-OUT", state="draft")
        self.assertTrue(transaction)
        logger = logging.getLogger(_AUDIT_LOGGER)
        capture = _WarningCapture()
        previous = logger.level
        logger.setLevel(logging.WARNING)
        logger.addHandler(capture)
        try:
            self.env["plasticos.audit.cron"].run_monthly_audit()
            self.env["plasticos.audit.cron"].run_monthly_audit()
        finally:
            logger.removeHandler(capture)
            logger.setLevel(previous)
        transaction.invalidate_recordset()
        self.assertEqual(transaction.state, "draft")
        self.assertNotIn(transaction.name, "\n".join(capture.messages))
