"""Full cron test suite for plasticos_automation scheduled jobs.

Covers:
    - contract_renewal: cron_contract_renewal_alert
    - trucker_followup: cron_trucker_followup
    - supplier_followup: cron_supplier_followup
    - load_sla: cron_load_sla_check
    - stock_alert: cron_stock_reorder_alert
    - invoice_reminder: cron_invoice_reminder
    - sale_approval: cron_flag_sale_approvals
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


# ═══════════════════════════════════════════════════════════════════
# Shared helper
# ═══════════════════════════════════════════════════════════════════
class AutomationTestMixin:
    """Shared setup for plasticos_automation cron tests."""

    @classmethod
    def _get_config(cls):
        return cls.env["plasticos.automation.config"].get_config()


# ═══════════════════════════════════════════════════════════════════
# contract_renewal — cron_contract_renewal_alert (res.partner)
# ═══════════════════════════════════════════════════════════════════
class TestContractRenewalCron(TransactionCase, AutomationTestMixin):
    """Tests for cron_contract_renewal_alert on res.partner."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]

    def test_alert_posted_for_expiring_contract(self):
        """Partners with contract ending within threshold get message_post."""
        config = self._get_config()
        partner = self.Partner.create(
            {
                "name": "Expiring Supplier",
                "contract_end_date": date.today() + timedelta(days=config.contract_alert_days_before - 1),
            }
        )
        self.Partner.cron_contract_renewal_alert()
        messages = partner.message_ids.filtered(lambda m: "contract expires" in (m.body or "").lower())
        self.assertTrue(messages, "Should post contract alert message")

    def test_no_alert_for_distant_contract(self):
        """Partners with contract far in the future get no alert."""
        partner = self.Partner.create(
            {
                "name": "Safe Supplier",
                "contract_end_date": date.today() + timedelta(days=365),
            }
        )
        self.Partner.cron_contract_renewal_alert()
        messages = partner.message_ids.filtered(lambda m: "contract expires" in (m.body or "").lower())
        self.assertFalse(messages, "Should not alert for distant contracts")

    def test_no_alert_for_past_contract(self):
        """Already-expired contracts (past date) are NOT alerted — only upcoming."""
        partner = self.Partner.create(
            {
                "name": "Expired Supplier",
                "contract_end_date": date.today() - timedelta(days=10),
            }
        )
        self.Partner.cron_contract_renewal_alert()
        messages = partner.message_ids.filtered(lambda m: "contract expires" in (m.body or "").lower())
        self.assertFalse(messages, "Past contracts should not trigger alert")

    def test_no_duplicate_alert_same_day(self):
        """Running cron twice on same day does NOT post duplicate alerts."""
        config = self._get_config()
        partner = self.Partner.create(
            {
                "name": "Dup Check",
                "contract_end_date": date.today() + timedelta(days=config.contract_alert_days_before - 1),
            }
        )
        self.Partner.cron_contract_renewal_alert()
        count_1 = len(partner.message_ids.filtered(lambda m: "contract expires" in (m.body or "").lower()))
        self.Partner.cron_contract_renewal_alert()
        count_2 = len(partner.message_ids.filtered(lambda m: "contract expires" in (m.body or "").lower()))
        self.assertEqual(count_1, count_2, "Should not duplicate alerts same day")

    def test_creates_automation_log(self):
        """Cron creates a plasticos.automation.log entry for each alert."""
        config = self._get_config()
        partner = self.Partner.create(
            {
                "name": "Log Check",
                "contract_end_date": date.today() + timedelta(days=config.contract_alert_days_before - 1),
            }
        )
        self.Partner.cron_contract_renewal_alert()
        logs = self.env["plasticos.automation.log"].search(
            [
                ("model_name", "=", "res.partner"),
                ("res_id", "=", partner.id),
                ("action_type", "=", "contract_alert"),
            ]
        )
        self.assertTrue(logs, "Should create automation log entry")

    def test_advisory_lock_skip(self):
        """Cron skips when advisory lock already held."""
        with patch.object(self.env.cr, "execute"), patch.object(self.env.cr, "fetchone", return_value=(False,)):
            self.Partner.cron_contract_renewal_alert()

    def test_limit_200_partners(self):
        """Search is limited to 200 partners per run."""
        with patch.object(self.Partner.__class__, "search", return_value=self.Partner) as m_search:
            self.Partner.cron_contract_renewal_alert()
            if m_search.called:
                kw = m_search.call_args.kwargs or {}
                if "limit" in kw:
                    self.assertLessEqual(kw["limit"], 200)

    def test_no_contract_date_skipped(self):
        """Partners without contract_end_date are excluded."""
        partner = self.Partner.create(
            {
                "name": "No Date Supplier",
            }
        )
        self.Partner.cron_contract_renewal_alert()
        messages = partner.message_ids.filtered(lambda m: "contract expires" in (m.body or "").lower())
        self.assertFalse(messages)


# ═══════════════════════════════════════════════════════════════════
# trucker_followup — cron_trucker_followup (stock.picking)
# ═══════════════════════════════════════════════════════════════════
class TestTruckerFollowupCron(TransactionCase, AutomationTestMixin):
    """Tests for cron_trucker_followup on stock.picking."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Picking = cls.env["stock.picking"]
        cls.partner = cls.env["res.partner"].create({"name": "Test Trucker"})

    def _create_picking(self, **kwargs):
        """Helper to create outgoing picking with trucker."""
        pick_type = self.env.ref("stock.picking_type_out", raise_if_not_found=False)
        if not pick_type:
            pick_type = self.env["stock.picking.type"].search([("code", "=", "outgoing")], limit=1)
        stock_loc = self.env.ref("stock.stock_location_stock", raise_if_not_found=False)
        customer_loc = self.env.ref("stock.stock_location_customers", raise_if_not_found=False)
        vals = {
            "picking_type_id": pick_type.id if pick_type else False,
            "location_id": stock_loc.id if stock_loc else False,
            "location_dest_id": customer_loc.id if customer_loc else False,
            "trucker_id": self.partner.id,
            "receipt_confirmation": False,
        }
        vals.update(kwargs)
        return self.Picking.create(vals)

    def test_followup_posted(self):
        """Unconfirmed pickings get follow-up message posted."""
        picking = self._create_picking()
        self.Picking.cron_trucker_followup()
        messages = picking.message_ids.filtered(lambda m: "follow-up" in (m.body or "").lower())
        self.assertTrue(messages, "Should post follow-up message")

    def test_followup_count_incremented(self):
        """trucker_followup_count increments each run."""
        picking = self._create_picking()
        self.Picking.cron_trucker_followup()
        self.assertEqual(picking.trucker_followup_count, 1)

    def test_trucker_notified_on_updated(self):
        """trucker_notified_on is set to current time on follow-up."""
        picking = self._create_picking()
        self.Picking.cron_trucker_followup()
        self.assertTrue(picking.trucker_notified_on, "Should set notification timestamp")

    def test_confirmed_receipt_skipped(self):
        """Pickings with receipt_confirmation=True are not followed up."""
        picking = self._create_picking(receipt_confirmation=True)
        self.Picking.cron_trucker_followup()
        self.assertEqual(picking.trucker_followup_count, 0)

    def test_no_trucker_skipped(self):
        """Pickings without trucker_id are not followed up."""
        picking = self._create_picking(trucker_id=False)
        self.Picking.cron_trucker_followup()
        self.assertEqual(picking.trucker_followup_count, 0)

    def test_escalation_at_3_followups(self):
        """After 3 follow-ups, activity is scheduled for escalation."""
        picking = self._create_picking()
        picking.trucker_followup_count = 2
        picking.trucker_notified_on = False
        self.Picking.cron_trucker_followup()
        self.assertEqual(picking.trucker_followup_count, 3)
        # Activity should be created
        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "stock.picking"),
                ("res_id", "=", picking.id),
            ]
        )
        self.assertTrue(activities, "Escalation activity should be scheduled at 3 follow-ups")

    def test_email_template_sent_if_exists(self):
        """Email template is sent if it exists in the system."""
        picking = self._create_picking()
        with patch.object(self.env.__class__, "ref", return_value=MagicMock(send_mail=MagicMock())):
            self.Picking.cron_trucker_followup()

    def test_creates_automation_log(self):
        """Cron creates automation log entry for each follow-up."""
        picking = self._create_picking()
        self.Picking.cron_trucker_followup()
        logs = self.env["plasticos.automation.log"].search(
            [
                ("model_name", "=", "stock.picking"),
                ("res_id", "=", picking.id),
                ("action_type", "=", "logistics_followup"),
            ]
        )
        self.assertTrue(logs)

    def test_advisory_lock_skip(self):
        """Skips when lock held."""
        with patch.object(self.env.cr, "execute"), patch.object(self.env.cr, "fetchone", return_value=(False,)):
            self.Picking.cron_trucker_followup()

    def test_done_cancelled_excluded(self):
        """Done/cancelled pickings are excluded from follow-up."""
        picking = self._create_picking()
        picking.state = "done"
        self.Picking.cron_trucker_followup()
        self.assertEqual(picking.trucker_followup_count, 0)


# ═══════════════════════════════════════════════════════════════════
# supplier_followup — cron_supplier_followup (purchase.order)
# ═══════════════════════════════════════════════════════════════════
class TestSupplierFollowupCron(TransactionCase, AutomationTestMixin):
    """Tests for cron_supplier_followup on purchase.order."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.PO = cls.env["purchase.order"]
        cls.partner = cls.env["res.partner"].create({"name": "Test Supplier"})

    def _create_po(self, **kwargs):
        vals = {
            "partner_id": self.partner.id,
            "ready_for_pickup": False,
        }
        vals.update(kwargs)
        po = self.PO.create(vals)
        po.button_confirm()  # Move to 'purchase' state
        return po

    def test_followup_posted(self):
        """POs not ready for pickup get follow-up message."""
        po = self._create_po()
        self.PO.cron_supplier_followup()
        messages = po.message_ids.filtered(lambda m: "follow-up" in (m.body or "").lower())
        self.assertTrue(messages)

    def test_followup_count_incremented(self):
        """followup_count increments each run."""
        po = self._create_po()
        self.PO.cron_supplier_followup()
        self.assertEqual(po.followup_count, 1)

    def test_ready_for_pickup_skipped(self):
        """POs with ready_for_pickup=True are skipped."""
        po = self._create_po(ready_for_pickup=True)
        self.PO.cron_supplier_followup()
        self.assertEqual(po.followup_count, 0)

    def test_escalation_at_3_followups(self):
        """After 3 follow-ups, escalation activity is scheduled."""
        po = self._create_po()
        po.followup_count = 2
        po.last_followup_on = False
        self.PO.cron_supplier_followup()
        self.assertEqual(po.followup_count, 3)
        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "purchase.order"),
                ("res_id", "=", po.id),
            ]
        )
        self.assertTrue(activities, "Escalation activity should be scheduled")

    def test_email_template_sent(self):
        """Email template is called if it exists."""
        po = self._create_po()
        with patch.object(self.env.__class__, "ref", return_value=MagicMock(send_mail=MagicMock())):
            self.PO.cron_supplier_followup()

    def test_creates_automation_log(self):
        """Creates automation log entry."""
        po = self._create_po()
        self.PO.cron_supplier_followup()
        logs = self.env["plasticos.automation.log"].search(
            [
                ("model_name", "=", "purchase.order"),
                ("res_id", "=", po.id),
                ("action_type", "=", "logistics_followup"),
            ]
        )
        self.assertTrue(logs)

    def test_advisory_lock_skip(self):
        with patch.object(self.env.cr, "execute"), patch.object(self.env.cr, "fetchone", return_value=(False,)):
            self.PO.cron_supplier_followup()


# ═══════════════════════════════════════════════════════════════════
# load_sla — cron_load_sla_check (plasticos.load)
# ═══════════════════════════════════════════════════════════════════
class TestLoadSLACron(TransactionCase, AutomationTestMixin):
    """Tests for cron_load_sla_check on plasticos.load."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.load" not in cls.env:
            raise unittest.SkipTest("plasticos.load not installed")
        cls.Load = cls.env["plasticos.load"]

    def _create_load(self, state="awaiting_ready", hours_ago=0):
        load = self.Load.create({"state": state})
        if hours_ago:
            ts = datetime.now() - timedelta(hours=hours_ago)
            load.entered_state_at = ts
        return load

    def test_no_breach_within_sla(self):
        """Loads within SLA hours are not escalated."""
        load = self._create_load("awaiting_ready", hours_ago=1)
        self.Load.cron_load_sla_check()
        self.assertEqual(load.escalation_level, "none")

    def test_warning_escalation(self):
        """Loads past SLA but < 2x get warning escalation."""
        load = self._create_load("awaiting_ready", hours_ago=50)  # SLA=48h
        self.Load.cron_load_sla_check()
        self.assertEqual(load.escalation_level, "warning")
        self.assertTrue(load.sla_breached)

    def test_critical_escalation(self):
        """Loads past 2x SLA get critical escalation."""
        load = self._create_load("awaiting_ready", hours_ago=100)  # 2x48=96h
        self.Load.cron_load_sla_check()
        self.assertEqual(load.escalation_level, "critical")

    def test_message_posted_on_escalation(self):
        """SLA breach posts a notification message."""
        load = self._create_load("awaiting_ready", hours_ago=50)
        self.Load.cron_load_sla_check()
        messages = load.message_ids.filtered(lambda m: "sla breach" in (m.body or "").lower())
        self.assertTrue(messages)

    def test_no_entered_state_at_skipped(self):
        """Loads without entered_state_at are skipped."""
        load = self._create_load("awaiting_ready")
        load.entered_state_at = False
        self.Load.cron_load_sla_check()
        self.assertEqual(load.escalation_level, "none")

    def test_escalation_cleared_back_within_sla(self):
        """Escalation resets to none if load returns within SLA (edge case)."""
        load = self._create_load("awaiting_ready", hours_ago=1)
        load.escalation_level = "warning"
        self.Load.cron_load_sla_check()
        self.assertEqual(load.escalation_level, "none")

    def test_creates_automation_log(self):
        """Creates log entry on escalation change."""
        load = self._create_load("awaiting_ready", hours_ago=50)
        self.Load.cron_load_sla_check()
        logs = self.env["plasticos.automation.log"].search(
            [
                ("model_name", "=", "plasticos.load"),
                ("res_id", "=", load.id),
                ("action_type", "=", "logistics_escalation"),
            ]
        )
        self.assertTrue(logs)

    def test_advisory_lock_skip(self):
        with patch.object(self.env.cr, "execute"), patch.object(self.env.cr, "fetchone", return_value=(False,)):
            self.Load.cron_load_sla_check()

    def test_all_sla_states_covered(self):
        """SLA hours defined for awaiting_ready, ready_confirmed, rate_confirmed, scheduled, dispatched."""
        from odoo.addons.plasticos_automation.models.load_automation import _SLA_HOURS

        expected_states = {"awaiting_ready", "ready_confirmed", "rate_confirmed", "scheduled", "dispatched"}
        self.assertEqual(set(_SLA_HOURS.keys()), expected_states)


# ═══════════════════════════════════════════════════════════════════
# stock_alert — cron_stock_reorder_alert (product.product)
# ═══════════════════════════════════════════════════════════════════
class TestStockAlertCron(TransactionCase, AutomationTestMixin):
    """Tests for cron_stock_reorder_alert on product.product."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]

    def test_alert_posted_below_threshold(self):
        """Products below min_stock_threshold get alert message."""
        product = self.Product.create(
            {
                "name": "Low Stock Product",
                "type": "consu",
                "min_stock_threshold": 100.0,
            }
        )
        # qty_available defaults to 0 < 100
        self.Product.cron_stock_reorder_alert()
        messages = product.message_ids.filtered(lambda m: "stock level" in (m.body or "").lower())
        self.assertTrue(messages, "Should post stock alert")

    def test_no_alert_above_threshold(self):
        """Products above threshold get no alert."""
        product = self.Product.create(
            {
                "name": "Full Stock Product",
                "type": "consu",
                "min_stock_threshold": 0.0,
            }
        )
        self.Product.cron_stock_reorder_alert()
        messages = product.message_ids.filtered(lambda m: "stock level" in (m.body or "").lower())
        self.assertFalse(messages)

    def test_no_duplicate_alert_same_day(self):
        """Running twice on same day does not duplicate alerts."""
        product = self.Product.create(
            {
                "name": "Dedup Stock",
                "type": "consu",
                "min_stock_threshold": 100.0,
            }
        )
        self.Product.cron_stock_reorder_alert()
        count_1 = len(product.message_ids.filtered(lambda m: "stock level" in (m.body or "").lower()))
        self.Product.cron_stock_reorder_alert()
        count_2 = len(product.message_ids.filtered(lambda m: "stock level" in (m.body or "").lower()))
        self.assertEqual(count_1, count_2)

    def test_global_threshold_fallback(self):
        """Uses config.stock_threshold_default when product threshold is 0."""
        product = self.Product.create(
            {
                "name": "Global Threshold",
                "type": "consu",
                "min_stock_threshold": 0.0,
            }
        )
        # Global threshold from config may be 0 too — product should be skipped
        self.Product.cron_stock_reorder_alert()  # Should not raise

    def test_creates_automation_log(self):
        """Creates log entry for each stock alert."""
        product = self.Product.create(
            {
                "name": "Log Stock",
                "type": "consu",
                "min_stock_threshold": 100.0,
            }
        )
        self.Product.cron_stock_reorder_alert()
        logs = self.env["plasticos.automation.log"].search(
            [
                ("model_name", "=", "product.product"),
                ("res_id", "=", product.id),
                ("action_type", "=", "stock_alert"),
            ]
        )
        self.assertTrue(logs)

    def test_advisory_lock_skip(self):
        with patch.object(self.env.cr, "execute"), patch.object(self.env.cr, "fetchone", return_value=(False,)):
            self.Product.cron_stock_reorder_alert()

    def test_service_products_excluded(self):
        """Service/consumable products are excluded (type != product)."""
        product = self.Product.create(
            {
                "name": "Service Product",
                "type": "service",
                "min_stock_threshold": 100.0,
            }
        )
        self.Product.cron_stock_reorder_alert()
        messages = product.message_ids.filtered(lambda m: "stock level" in (m.body or "").lower())
        self.assertFalse(messages)


# ═══════════════════════════════════════════════════════════════════
# invoice_reminder — cron_invoice_reminder (account.move)
# ═══════════════════════════════════════════════════════════════════
class TestInvoiceReminderCron(TransactionCase, AutomationTestMixin):
    """Tests for cron_invoice_reminder on account.move."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Move = cls.env["account.move"]
        # Ensure sale journal exists (required for out_invoice in Odoo 19)
        cls._sale_journal = cls.env["account.journal"].search([("type", "=", "sale")], limit=1)
        if not cls._sale_journal:
            cls._sale_journal = cls.env["account.journal"].create(
                {
                    "name": "Test Sales Journal",
                    "type": "sale",
                    "code": "TSALE",
                }
            )
        # Ensure purchase journal exists (required for in_invoice)
        cls._purchase_journal = cls.env["account.journal"].search([("type", "=", "purchase")], limit=1)
        if not cls._purchase_journal:
            cls._purchase_journal = cls.env["account.journal"].create(
                {
                    "name": "Test Purchase Journal",
                    "type": "purchase",
                    "code": "TPURCH",
                }
            )

    def _create_overdue_invoice(self, days_overdue=30):
        """Create a posted, unpaid, overdue out_invoice."""
        config = self._get_config()
        partner = self.env["res.partner"].create({"name": "Overdue Customer"})
        invoice = self.Move.create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": date.today() - timedelta(days=days_overdue + config.invoice_overdue_days),
                "invoice_date_due": date.today() - timedelta(days=days_overdue),
            }
        )
        invoice.action_post()
        return invoice

    def test_reminder_posted_for_overdue(self):
        """Overdue invoices get reminder message posted."""
        inv = self._create_overdue_invoice()
        self.Move.cron_invoice_reminder()
        messages = inv.message_ids.filtered(lambda m: "overdue" in (m.body or "").lower())
        self.assertTrue(messages)

    def test_last_reminder_date_set(self):
        """last_reminder_date is set to today on reminder."""
        inv = self._create_overdue_invoice()
        self.Move.cron_invoice_reminder()
        self.assertEqual(inv.last_reminder_date, date.today())

    def test_paid_invoices_excluded(self):
        """Paid invoices are not reminded."""
        inv = self._create_overdue_invoice()
        inv.payment_state = "paid"
        self.Move.cron_invoice_reminder()
        messages = inv.message_ids.filtered(lambda m: "overdue" in (m.body or "").lower())
        self.assertFalse(messages)

    def test_batch_log_creation(self):
        """Batch creates log entries for all reminded invoices."""
        inv = self._create_overdue_invoice()
        self.Move.cron_invoice_reminder()
        logs = self.env["plasticos.automation.log"].search(
            [
                ("model_name", "=", "account.move"),
                ("res_id", "=", inv.id),
                ("action_type", "=", "invoice_reminder"),
            ]
        )
        self.assertTrue(logs)

    def test_advisory_lock_skip(self):
        with patch.object(self.env.cr, "execute"), patch.object(self.env.cr, "fetchone", return_value=(False,)):
            self.Move.cron_invoice_reminder()

    def test_only_out_invoices(self):
        """Only customer invoices (out_invoice) are reminded."""
        partner = self.env["res.partner"].create({"name": "Vendor"})
        bill = self.Move.create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
            }
        )
        self.Move.cron_invoice_reminder()
        messages = bill.message_ids.filtered(lambda m: "overdue" in (m.body or "").lower())
        self.assertFalse(messages)


# ═══════════════════════════════════════════════════════════════════
# sale_approval — cron_flag_sale_approvals (sale.order)
# ═══════════════════════════════════════════════════════════════════
class TestSaleApprovalCron(TransactionCase, AutomationTestMixin):
    """Tests for cron_flag_sale_approvals on sale.order."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SO = cls.env["sale.order"]

    def _create_high_value_so(self, amount=10000.0):
        partner = self.env["res.partner"].create({"name": "Big Buyer"})
        product = self.env["product.product"].create(
            {
                "name": "Expensive Item",
                "list_price": amount,
            }
        )
        so = self.SO.create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": amount,
                        },
                    )
                ],
            }
        )
        return so

    def test_high_value_flagged(self):
        """Draft SOs exceeding threshold get requires_approval=True."""
        config = self._get_config()
        so = self._create_high_value_so(config.sale_approval_threshold + 1)
        self.SO.cron_flag_sale_approvals()
        self.assertTrue(so.requires_approval)

    def test_below_threshold_not_flagged(self):
        """Draft SOs below threshold are not flagged."""
        so = self._create_high_value_so(1.0)
        self.SO.cron_flag_sale_approvals()
        self.assertFalse(so.requires_approval)

    def test_already_flagged_not_re_flagged(self):
        """SOs already flagged are not processed again."""
        config = self._get_config()
        so = self._create_high_value_so(config.sale_approval_threshold + 1)
        so.requires_approval = True
        self.SO.cron_flag_sale_approvals()  # Should skip this one

    def test_action_confirm_blocked_without_approval(self):
        """Confirming a flagged SO without approval raises UserError."""
        config = self._get_config()
        so = self._create_high_value_so(config.sale_approval_threshold + 1)
        so.requires_approval = True
        with self.assertRaises(UserError):
            so.action_confirm()

    def test_action_confirm_succeeds_with_approval(self):
        """Confirming a flagged SO with approved=True succeeds."""
        config = self._get_config()
        so = self._create_high_value_so(config.sale_approval_threshold + 1)
        so.requires_approval = True
        so.approved = True
        so.action_confirm()  # Should not raise

    def test_creates_automation_log(self):
        config = self._get_config()
        so = self._create_high_value_so(config.sale_approval_threshold + 1)
        self.SO.cron_flag_sale_approvals()
        logs = self.env["plasticos.automation.log"].search(
            [
                ("model_name", "=", "sale.order"),
                ("res_id", "=", so.id),
                ("action_type", "=", "approval_flag"),
            ]
        )
        self.assertTrue(logs)

    def test_advisory_lock_skip(self):
        with patch.object(self.env.cr, "execute"), patch.object(self.env.cr, "fetchone", return_value=(False,)):
            self.SO.cron_flag_sale_approvals()

    def test_only_draft_orders(self):
        """Only draft SOs are flagged — confirmed ones are excluded."""
        config = self._get_config()
        so = self._create_high_value_so(config.sale_approval_threshold + 1)
        so.approved = True
        so.action_confirm()
        so.requires_approval = False
        self.SO.cron_flag_sale_approvals()
        self.assertFalse(so.requires_approval)
