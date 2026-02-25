import logging
from datetime import date, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PlasticosTransactionDocs(models.Model):
    _inherit = "plasticos.transaction"

    # ── Missing Document Status Tracking ───────────────────────────
    x_missing_doc_status = fields.Selection(
        [
            ("complete", "Complete"),
            ("pending", "Pending"),
            ("overdue", "Overdue"),
            ("escalated", "Escalated"),
        ],
        string="Document Status",
        default="pending",
        help="Overall status of required documents for this transaction.",
    )
    x_missing_supplier_docs = fields.Boolean(
        string="Missing Supplier Docs",
        compute="_compute_missing_doc_flags",
        store=True,
        help="True if any required supplier documents are missing.",
    )
    x_missing_carrier_docs = fields.Boolean(
        string="Missing Carrier Docs",
        compute="_compute_missing_doc_flags",
        store=True,
        help="True if any required carrier documents are missing.",
    )
    x_missing_buyer_docs = fields.Boolean(
        string="Missing Buyer Docs",
        compute="_compute_missing_doc_flags",
        store=True,
        help="True if any required buyer documents are missing.",
    )
    x_doc_reminder_count = fields.Integer(
        string="Reminder Count",
        default=0,
        help="Number of document reminders sent for this transaction.",
    )
    x_last_doc_reminder_date = fields.Date(
        string="Last Reminder Date",
        help="Date when the last document reminder was sent.",
    )

    # ── Computed Missing Doc Flags ─────────────────────────────────

    @api.depends("load_id", "sale_order_id")
    def _compute_missing_doc_flags(self):
        """Compute missing document flags using the existing compliance service.

        Leverages plasticos.compliance.service.get_missing_documents()
        and cross-references against the validation matrix categories.
        """
        matrix_model = self.env["plasticos.document.validation.matrix"]
        compliance = self.env["plasticos.compliance.service"]

        for tx in self:
            missing_codes = compliance.get_missing_documents(
                "plasticos.transaction",
                tx.id,
            )
            missing_set = set(missing_codes) if missing_codes else set()

            # Look up which tags belong to which category
            supplier_tags = matrix_model.search(
                [
                    ("doc_category", "=", "supplier"),
                    ("active", "=", True),
                ]
            ).mapped("tag_id.code")

            carrier_tags = matrix_model.search(
                [
                    ("doc_category", "=", "carrier"),
                    ("active", "=", True),
                ]
            ).mapped("tag_id.code")

            buyer_tags = matrix_model.search(
                [
                    ("doc_category", "=", "buyer"),
                    ("active", "=", True),
                ]
            ).mapped("tag_id.code")

            tx.x_missing_supplier_docs = bool(missing_set & set(supplier_tags))
            tx.x_missing_carrier_docs = bool(missing_set & set(carrier_tags))
            tx.x_missing_buyer_docs = bool(missing_set & set(buyer_tags))

    # ── Business Day Calculation ───────────────────────────────────

    @staticmethod
    def _count_business_days(start_date, end_date):
        """Count business days between two dates (excluding weekends)."""
        if not start_date or not end_date:
            return 0
        bd = 0
        current = start_date
        while current < end_date:
            if current.weekday() < 5:
                bd += 1
            current += timedelta(days=1)
        return bd

    # ── Cron: Check Missing Documents ──────────────────────────────

    @api.model
    def cron_check_missing_docs(self):
        """Check all active transactions for missing documents."""
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_documents.cron_check_missing_docs"]
        )
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping missing-docs cron: lock is already held.")
            return

        try:
            transactions = self.search(
                [("state", "=", "active")],
                order="create_date ASC, id ASC",
                limit=300,
            )
            log_model = self.env["plasticos.automation.log"] if "plasticos.automation.log" in self.env else None
            today = date.today()

            for tx in transactions:
                # Recompute missing flags
                tx._compute_missing_doc_flags()
                has_missing = tx.x_missing_supplier_docs or tx.x_missing_carrier_docs or tx.x_missing_buyer_docs

                if not has_missing:
                    if tx.x_missing_doc_status != "complete":
                        tx.x_missing_doc_status = "complete"
                    continue

                # Determine age in business days from create_date
                start_date = tx.create_date.date() if tx.create_date else today
                bd = self._count_business_days(start_date, today)

                # Use the most aggressive thresholds from the matrix rules
                # Default: overdue after 2 BD, escalate after 5 BD
                overdue_threshold = 2
                escalation_threshold = 5

                rules = self.env["plasticos.document.rule"].search(
                    [("res_model", "=", "plasticos.transaction"), ("active", "=", True)],
                    order="id ASC",
                )
                for rule in rules:
                    if hasattr(rule, "x_overdue_business_days") and rule.x_overdue_business_days:
                        overdue_threshold = min(overdue_threshold, rule.x_overdue_business_days)
                    if hasattr(rule, "x_escalation_business_days") and rule.x_escalation_business_days:
                        escalation_threshold = min(escalation_threshold, rule.x_escalation_business_days)

                if bd >= escalation_threshold:
                    new_status = "escalated"
                elif bd >= overdue_threshold:
                    new_status = "overdue"
                else:
                    new_status = "pending"

                if tx.x_missing_doc_status != new_status:
                    tx.x_missing_doc_status = new_status

                if new_status == "overdue":
                    if tx.x_last_doc_reminder_date and tx.x_last_doc_reminder_date >= today:
                        continue
                    tx.x_doc_reminder_count += 1
                    tx.x_last_doc_reminder_date = today
                    tx.message_post(
                        body=f"Automated reminder: transaction {tx.name} has missing documents (overdue by {bd} business days).",
                        message_type="notification",
                    )
                    if log_model is not None:
                        log_model.create(
                            {
                                "name": f"Doc reminder for {tx.name}",
                                "model_name": "plasticos.transaction",
                                "res_id": tx.id,
                                "action_type": "doc_reminder",
                            }
                        )
                elif new_status == "escalated":
                    has_today_activity = self.env["mail.activity"].search_count(
                        [
                            ("res_model", "=", "plasticos.transaction"),
                            ("res_id", "=", tx.id),
                            ("summary", "=", f"ESCALATION: Missing documents on {tx.name}"),
                            ("date_deadline", "=", today),
                        ]
                    )
                    if has_today_activity:
                        continue
                    tx.activity_schedule(
                        "mail.mail_activity_data_todo",
                        user_id=self.env.user.id,
                        summary=f"ESCALATION: Missing documents on {tx.name}",
                        note=f"Transaction {tx.name} has missing documents for {bd} business days. Manual intervention required.",
                    )
                    if log_model is not None:
                        log_model.create(
                            {
                                "name": f"Doc escalation for {tx.name}",
                                "model_name": "plasticos.transaction",
                                "res_id": tx.id,
                                "action_type": "doc_escalation",
                            }
                        )

                _logger.info(
                    "Documents extension: TX %s status=%s (bd=%d, missing: supplier=%s, carrier=%s, buyer=%s)",
                    tx.name,
                    new_status,
                    bd,
                    tx.x_missing_supplier_docs,
                    tx.x_missing_carrier_docs,
                    tx.x_missing_buyer_docs,
                )
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_documents.cron_check_missing_docs"]
            )
