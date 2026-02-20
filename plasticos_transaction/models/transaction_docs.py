from odoo import models, fields, api

from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class PlasticosTransactionDocs(models.Model):
    _inherit = "plasticos.transaction"

    # ── Missing Document Status Tracking ───────────────────────────
    missing_doc_status = fields.Selection(
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
    missing_supplier_docs = fields.Boolean(
        string="Missing Supplier Docs",
        compute="_compute_missing_doc_flags",
        store=True,
        help="True if any required supplier documents are missing.",
    )
    missing_carrier_docs = fields.Boolean(
        string="Missing Carrier Docs",
        compute="_compute_missing_doc_flags",
        store=True,
        help="True if any required carrier documents are missing.",
    )
    missing_buyer_docs = fields.Boolean(
        string="Missing Buyer Docs",
        compute="_compute_missing_doc_flags",
        store=True,
        help="True if any required buyer documents are missing.",
    )
    doc_reminder_count = fields.Integer(
        string="Reminder Count",
        default=0,
        help="Number of document reminders sent for this transaction.",
    )
    last_doc_reminder_date = fields.Date(
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
                "plasticos.transaction", tx.id,
            )
            missing_set = set(missing_codes) if missing_codes else set()

            # Look up which tags belong to which category
            supplier_tags = matrix_model.search([
                ("doc_category", "=", "supplier"),
                ("active", "=", True),
            ]).mapped("tag_id.code")

            carrier_tags = matrix_model.search([
                ("doc_category", "=", "carrier"),
                ("active", "=", True),
            ]).mapped("tag_id.code")

            buyer_tags = matrix_model.search([
                ("doc_category", "=", "buyer"),
                ("active", "=", True),
            ]).mapped("tag_id.code")

            tx.missing_supplier_docs = bool(missing_set & set(supplier_tags))
            tx.missing_carrier_docs = bool(missing_set & set(carrier_tags))
            tx.missing_buyer_docs = bool(missing_set & set(buyer_tags))

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
        """Check all active transactions for missing documents.

        Determines overdue/escalated status based on business days
        since transaction creation. Posts reminders and escalation
        activities as needed. Logs all actions to plasticos.automation.log.
        """
        transactions = self.search([
            ("state", "=", "active"),
        ])

        log_model = self.env.get("plasticos.automation.log")
        today = date.today()

        for tx in transactions:
            # Recompute missing flags
            tx._compute_missing_doc_flags()

            has_missing = (
                tx.missing_supplier_docs
                or tx.missing_carrier_docs
                or tx.missing_buyer_docs
            )

            if not has_missing:
                if tx.missing_doc_status != "complete":
                    tx.missing_doc_status = "complete"
                continue

            # Determine age in business days from create_date
            start = tx.create_date.date() if tx.create_date else today
            bd = self._count_business_days(start, today)

            # Use the most aggressive thresholds from the matrix rules
            # Default: overdue after 2 BD, escalate after 5 BD
            overdue_threshold = 2
            escalation_threshold = 5

            rules = self.env["plasticos.document.rule"].search([
                ("res_model", "=", "plasticos.transaction"),
                ("active", "=", True),
            ])
            for rule in rules:
                if rule.overdue_business_days:
                    overdue_threshold = min(overdue_threshold, rule.overdue_business_days)
                if rule.escalation_business_days:
                    escalation_threshold = min(escalation_threshold, rule.escalation_business_days)

            # Determine status
            if bd >= escalation_threshold:
                new_status = "escalated"
            elif bd >= overdue_threshold:
                new_status = "overdue"
            else:
                new_status = "pending"

            if tx.missing_doc_status != new_status:
                tx.missing_doc_status = new_status

            # Send reminder for overdue transactions
            if new_status == "overdue":
                tx.doc_reminder_count += 1
                tx.last_doc_reminder_date = today
                tx.message_post(
                    body="Automated reminder: transaction %s has missing "
                         "documents (overdue by %d business days)."
                         % (tx.name, bd),
                    message_type="notification",
                )

                if log_model is not None:
                    log_model.create({
                        "name": "Doc reminder for %s" % tx.name,
                        "model_name": "plasticos.transaction",
                        "res_id": tx.id,
                        "action_type": "doc_reminder",
                    })

            # Escalate
            elif new_status == "escalated":
                tx.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=self.env.user.id,
                    summary="ESCALATION: Missing documents on %s" % tx.name,
                    note="Transaction %s has missing documents for %d "
                         "business days. Manual intervention required."
                         % (tx.name, bd),
                )

                if log_model is not None:
                    log_model.create({
                        "name": "Doc escalation for %s" % tx.name,
                        "model_name": "plasticos.transaction",
                        "res_id": tx.id,
                        "action_type": "doc_escalation",
                    })

            _logger.info(
                "Documents: TX %s status=%s (bd=%d, missing: "
                "supplier=%s, carrier=%s, buyer=%s)",
                tx.name,
                new_status,
                bd,
                tx.missing_supplier_docs,
                tx.missing_carrier_docs,
                tx.missing_buyer_docs,
            )
