import logging
from datetime import date, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PlasticosTransactionDocs(models.Model):
    _inherit = "plasticos.transaction"

    # NOTE: document_ids One2many is defined in transaction_docs_bridge.py

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

    @api.depends("load_id", "sale_order_id", "document_ids", "document_ids.tag_id", "document_ids.active")
    def _compute_missing_doc_flags(self):
        """Compute missing document flags using the existing compliance service.

        Leverages plasticos.compliance.service.get_missing_documents()
        and cross-references against the validation matrix categories.
        """
        matrix_model = self.env["plasticos.document.validation.matrix"]
        compliance = self.env["plasticos.compliance.service"]

        # Pre-fetch category → tag mappings once (avoids N+1 queries)
        supplier_tags = set(
            matrix_model.search([("doc_category", "=", "supplier"), ("active", "=", True)]).mapped("tag_id.code")
        )
        carrier_tags = set(
            matrix_model.search([("doc_category", "=", "carrier"), ("active", "=", True)]).mapped("tag_id.code")
        )
        buyer_tags = set(
            matrix_model.search([("doc_category", "=", "buyer"), ("active", "=", True)]).mapped("tag_id.code")
        )

        for tx in self:
            missing_codes = compliance.get_missing_documents(
                "plasticos.transaction",
                tx.id,
            )
            missing_set = set(missing_codes) if missing_codes else set()

            tx.missing_supplier_docs = bool(missing_set & supplier_tags)
            tx.missing_carrier_docs = bool(missing_set & carrier_tags)
            tx.missing_buyer_docs = bool(missing_set & buyer_tags)

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
            today = date.today()

            for tx in transactions:
                # Recompute missing flags
                tx._compute_missing_doc_flags()
                has_missing = tx.missing_supplier_docs or tx.missing_carrier_docs or tx.missing_buyer_docs

                if not has_missing:
                    if tx.missing_doc_status != "complete":
                        tx.missing_doc_status = "complete"
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
                    if hasattr(rule, "overdue_business_days") and rule.overdue_business_days:
                        overdue_threshold = min(overdue_threshold, rule.overdue_business_days)
                    if hasattr(rule, "escalation_business_days") and rule.escalation_business_days:
                        escalation_threshold = min(escalation_threshold, rule.escalation_business_days)

                if bd >= escalation_threshold:
                    new_status = "escalated"
                elif bd >= overdue_threshold:
                    new_status = "overdue"
                else:
                    new_status = "pending"

                if tx.missing_doc_status != new_status:
                    tx.missing_doc_status = new_status

                if new_status == "overdue":
                    if tx.last_doc_reminder_date and tx.last_doc_reminder_date >= today:
                        continue
                    tx.doc_reminder_count += 1
                    tx.last_doc_reminder_date = today
                    tx.message_post(
                        body=(
                            f"Automated reminder: transaction {tx.name} has missing documents "
                            f"(overdue by {bd} business days)."
                        ),
                        message_type="notification",
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
                        note=(
                            f"Transaction {tx.name} has missing documents for {bd} business days. "
                            "Manual intervention required."
                        ),
                    )

                _logger.info(
                    "Documents extension: TX %s status=%s (bd=%d, missing: supplier=%s, carrier=%s, buyer=%s)",
                    tx.name,
                    new_status,
                    bd,
                    tx.missing_supplier_docs,
                    tx.missing_carrier_docs,
                    tx.missing_buyer_docs,
                )
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_documents.cron_check_missing_docs"]
            )

    # ══════════════════════════════════════════════════════════════
    # Cron: Scale Ticket Request & Escalation
    # ══════════════════════════════════════════════════════════════

    # Tracking fields for scale ticket reminders (avoid duplicates)
    scale_ticket_reminder_sent = fields.Boolean(
        string="Scale Ticket Reminder Sent",
        default=False,
        help="True if 48h reminder has been sent for missing scale ticket.",
    )
    scale_ticket_escalated = fields.Boolean(
        string="Scale Ticket Escalated",
        default=False,
        help="True if 7-day escalation has been triggered for missing scale ticket.",
    )

    @api.model
    def cron_check_scale_tickets(self):
        """Check delivered/closed/invoiced transactions for missing scale tickets.

        Business rules:
        - 48 hours (2 BD) after delivery → send reminder to carrier
        - 7 days (7 BD) from pickup → escalate to logistics manager

        Uses x_overdue_business_days and x_escalation_business_days from
        the scale ticket document rule (not hardcoded).
        """
        # Advisory lock to prevent concurrent execution
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_documents.cron_check_scale_tickets"]
        )
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping scale-ticket cron: lock is already held.")
            return

        try:
            today = date.today()

            # Find transactions in relevant states with a load
            transactions = self.search(
                [
                    ("state", "in", ["delivered", "closed", "invoiced"]),
                    ("load_id", "!=", False),
                ],
                order="create_date ASC, id ASC",
                limit=300,
            )

            if not transactions:
                _logger.info("Scale ticket cron: no transactions to check.")
                return

            # Get scale ticket tag
            scale_ticket_tag = self.env["plasticos.document.tag"].search(
                [("code", "=", "SCALE")], order="id ASC", limit=1
            )
            if not scale_ticket_tag:
                _logger.warning("Scale ticket cron: SCALE tag not found. Skipping.")
                return

            # Get thresholds from document rule (not hardcoded)
            scale_rule = self.env["plasticos.document.rule"].search(
                [
                    ("tag_id", "=", scale_ticket_tag.id),
                    ("res_model", "=", "plasticos.transaction"),
                    ("active", "=", True),
                ],
                order="id ASC",
                limit=1,
            )
            overdue_bd = 2  # Default: 48h = 2 business days
            escalation_bd = 7  # Default: 7 business days
            if scale_rule:
                if scale_rule.overdue_business_days:
                    overdue_bd = scale_rule.overdue_business_days
                if scale_rule.escalation_business_days:
                    escalation_bd = scale_rule.escalation_business_days

            # Get logistics manager group for escalation
            logistics_group = self.env.ref("plasticos_logistics.group_logistics_manager", raise_if_not_found=False)

            for tx in transactions:
                load = tx.load_id
                if not load:
                    continue

                # Check if scale ticket already exists
                has_scale_ticket = self.env["plasticos.document"].search_count(
                    [
                        ("transaction_id", "=", tx.id),
                        ("tag_id", "=", scale_ticket_tag.id),
                        ("active", "=", True),
                    ]
                )
                if has_scale_ticket:
                    continue  # Scale ticket exists, skip

                # Calculate business days since delivery and pickup
                delivery_date = load.delivered_at.date() if load.delivered_at else None
                pickup_date = load.dispatched_at.date() if load.dispatched_at else None

                bd_since_delivery = self._count_business_days(delivery_date, today) if delivery_date else 0
                bd_since_pickup = self._count_business_days(pickup_date, today) if pickup_date else 0

                # Escalation: 7 BD from pickup
                if bd_since_pickup >= escalation_bd and not tx.scale_ticket_escalated:
                    # Find logistics manager to assign activity
                    manager_user = self._get_logistics_manager(logistics_group)
                    if manager_user:
                        # Create escalation activity
                        tx.activity_schedule(
                            "mail.mail_activity_data_todo",
                            user_id=manager_user.id,
                            summary=f"ESCALATION: Missing scale ticket on {tx.name}",
                            note=(
                                f"Transaction {tx.name} is missing a scale ticket.\n"
                                f"Pickup was {bd_since_pickup} business days ago.\n"
                                f"Carrier: {load.carrier_id.name if load.carrier_id else 'Unknown'}\n"
                                "Please follow up with the carrier immediately."
                            ),
                        )
                        _logger.info(
                            "Scale ticket ESCALATION: TX %s, %d BD since pickup, assigned to %s",
                            tx.name,
                            bd_since_pickup,
                            manager_user.name,
                        )
                    else:
                        # No manager found, post message instead
                        tx.message_post(
                            body=(
                                f"<b>ESCALATION:</b> Missing scale ticket for {tx.name}. "
                                f"Pickup was {bd_since_pickup} business days ago. "
                                "No logistics manager found for assignment."
                            ),
                            message_type="notification",
                            subtype_xmlid="mail.mt_note",
                        )
                        _logger.warning("Scale ticket ESCALATION: TX %s, no logistics manager found", tx.name)
                    tx.scale_ticket_escalated = True

                # Reminder: 2 BD after delivery (only if not yet escalated)
                elif bd_since_delivery >= overdue_bd and not tx.scale_ticket_reminder_sent:
                    # Send reminder message
                    carrier_name = load.carrier_id.name if load.carrier_id else "Carrier"
                    tx.message_post(
                        body=(
                            f"<b>Automated Request:</b> Scale ticket needed for {tx.name}.\n"
                            f"Delivery was {bd_since_delivery} business days ago.\n"
                            f"Please request scale ticket from {carrier_name}."
                        ),
                        message_type="notification",
                        subtype_xmlid="mail.mt_note",
                    )
                    tx.scale_ticket_reminder_sent = True
                    _logger.info("Scale ticket REMINDER: TX %s, %d BD since delivery", tx.name, bd_since_delivery)

        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_documents.cron_check_scale_tickets"]
            )

    def _get_logistics_manager(self, group):
        """Find a logistics manager user for escalation assignment.

        Returns the first active user in the logistics manager group,
        or falls back to the current user if no manager found.
        """
        if not group:
            return self.env.user

        managers = self.env["res.users"].search(
            [
                ("group_ids", "in", group.id),
                ("active", "=", True),
            ],
            limit=1,
        )
        return managers[0] if managers else self.env.user
