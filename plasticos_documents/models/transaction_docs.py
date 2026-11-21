import logging
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.addons.plasticos_base.models.res_users import EXCLUDE_CONTEXT_KEY
from odoo.tools import html2plaintext

from .exception_router import (
    EXC_MISSING_DOCUMENTS,
    EXC_MISSING_SCALE_TICKET,
    LOGISTICS,
    OPERATIONS,
    OWNER_GROUPS,
    Obligation,
    RerouteResult,
)

_logger = logging.getLogger(__name__)


class PlasticosTransactionDocs(models.Model):
    # activity_schedule is the escalation write. A list inherit needs an
    # explicit _name; leaving it unset registers plasticos.transaction.docs.
    _name = "plasticos.transaction"
    _inherit = ["plasticos.transaction", "mail.activity.mixin"]

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
        compute_sudo=True,
        help="True if any required supplier documents are missing.",
    )
    missing_carrier_docs = fields.Boolean(
        string="Missing Carrier Docs",
        compute="_compute_missing_doc_flags",
        store=True,
        compute_sudo=True,
        help="True if any required carrier documents are missing.",
    )
    missing_buyer_docs = fields.Boolean(
        string="Missing Buyer Docs",
        compute="_compute_missing_doc_flags",
        store=True,
        compute_sudo=True,
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

    @api.depends("load_ids", "sale_order_id", "document_ids", "document_ids.tag_id", "document_ids.active")
    def _compute_missing_doc_flags(self):
        """Compute missing document flags using the existing compliance service.

        Leverages plasticos.compliance.service.get_missing_documents()
        and cross-references against the validation matrix categories.
        """
        if "plasticos.compliance.service" not in self.env:
            for tx in self:
                projected = tx.sudo()  # sudo: compliance flag write; document read ACL still admits every internal user
                projected.missing_supplier_docs = False
                projected.missing_carrier_docs = False
                projected.missing_buyer_docs = False
            return

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

            projected = tx.sudo()  # sudo: compliance flag write; document read ACL still admits every internal user
            projected.missing_supplier_docs = bool(missing_set & supplier_tags)
            projected.missing_carrier_docs = bool(missing_set & carrier_tags)
            projected.missing_buyer_docs = bool(missing_set & buyer_tags)

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

    _MISSING_DOC_BATCH = 300
    _MISSING_DOC_CURSOR = "plasticos_documents.missing_doc_scan_cursor"
    _UNASSIGNED_ESCALATION_MARKER = "Missing-document escalation has no owner."

    def _cron_parameters(self):
        """Scan cursors live in ir.config_parameter, which is settings-admin only."""
        return self.env["ir.config_parameter"].sudo()  # sudo: cron-sudo-justification: scan-cursor keys only

    @api.model
    def cron_check_missing_docs(self):
        """Check one page of active transactions for missing documents.

        A wrapping keyset cursor walks every active transaction. A short page
        sets the cursor back to the start for the following run.
        """
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_documents.cron_check_missing_docs"]
        )
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping missing-docs cron: lock is already held.")
            return {"processed": 0, "failures": 0, "skipped": True}

        try:
            parameters = self._cron_parameters()
            batch_size = int(self.env.context.get("missing_doc_batch_size") or self._MISSING_DOC_BATCH)
            cursor = int(parameters.get_param(self._MISSING_DOC_CURSOR, "0") or 0)
            transactions = self.search(
                [("state", "=", "active"), ("id", ">", cursor)],
                order="id ASC",
                limit=batch_size,
            )
            next_cursor = transactions[-1].id if len(transactions) >= batch_size else 0
            parameters.set_param(self._MISSING_DOC_CURSOR, str(next_cursor))
            result = self._apply_missing_doc_page(transactions) or {"processed": 0, "failures": 0}
            if result.get("failures"):
                _logger.error("Missing-docs cron finished with %s unassigned escalations.", result["failures"])
            return {**result, "skipped": False}
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_documents.cron_check_missing_docs"]
            )

    @api.model
    def _apply_missing_doc_page(self, transactions):
        """Apply missing-document status, reminders, and escalations to one page.

        The escalation owner comes from the DEC-010 router: missing shipping paperwork only is
        Logistics work, anything financial or cross-department is the Operations Manager's.
        With no owner the escalation is logged, noted once on the transaction, and counted as a
        failure. A transaction whose documents are complete has its escalation closed.
        """
        if not transactions:
            return {"processed": 0, "failures": 0}
        router = self.env["plasticos.exception.router"]
        today = date.today()
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

        summaries = {tx.id: f"ESCALATION: Missing documents on {tx.name}" for tx in transactions}
        companies = {tx.id: tx.sale_order_id.company_id | tx.purchase_order_ids.company_id for tx in transactions}
        # One query for the page's open escalations and one for its "no owner" notes (batched page).
        open_by_tx = (
            self.env["mail.activity"]
            .search(
                [
                    ("res_model", "=", "plasticos.transaction"),
                    ("res_id", "in", transactions.ids),
                    ("summary", "in", list(summaries.values())),
                ],
                order="id ASC",
            )
            .grouped("res_id")
        )
        notes = self.env["mail.message"].search(
            [
                ("model", "=", "plasticos.transaction"),
                ("res_id", "in", transactions.ids),
                ("body", "ilike", self._UNASSIGNED_ESCALATION_MARKER),
            ]
        )
        unassigned_noted = set(notes.mapped("res_id"))
        no_activity = self.env["mail.activity"]
        owners_by_role = {}
        processed = 0
        failures = 0

        for tx in transactions:
            processed += 1
            tx._compute_missing_doc_flags()
            has_missing = tx.missing_supplier_docs or tx.missing_carrier_docs or tx.missing_buyer_docs

            if not has_missing:
                if tx.missing_doc_status != "complete":
                    tx.missing_doc_status = "complete"
                router.resolve(
                    tx,
                    summaries[tx.id],
                    "The required documents are present.",
                    open_by_tx.get(tx.id, no_activity),
                )
                continue

            start_date = tx.create_date.date() if tx.create_date else today
            bd = self._count_business_days(start_date, today)

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
                missing_codes = self.env["plasticos.compliance.service"].get_missing_documents(
                    "plasticos.transaction", tx.id
                )
                purpose = router.purpose_from_tag_codes(missing_codes)
                route = router.route(purpose, EXC_MISSING_DOCUMENTS)
                if route.role not in owners_by_role:
                    owners_by_role[route.role] = self.with_context(
                        **{EXCLUDE_CONTEXT_KEY: router._excluded_ids(route.role)}
                    )._escalation_owners(self._escalation_group_for(route.role), companies)
                manager = owners_by_role[route.role][tx.id]
                obligation = Obligation(
                    summaries[tx.id],
                    purpose,
                    EXC_MISSING_DOCUMENTS,
                    f"Transaction {tx.name} has missing documents for {bd} business days. "
                    "Manual intervention required.",
                )
                activity = router.upsert(
                    tx,
                    obligation,
                    route,
                    manager,
                    companies[tx.id],
                    self._escalation_group_for(route.role),
                    open_by_tx.get(tx.id, no_activity),
                )
                if not activity:
                    failures += 1
                    _logger.error(
                        "Missing-document ESCALATION not assigned: transaction %s has no %s owner in its company.",
                        tx.name,
                        route.role,
                    )
                    if tx.id not in unassigned_noted:
                        unassigned_noted.add(tx.id)
                        tx.message_post(
                            body=(
                                f"{self._UNASSIGNED_ESCALATION_MARKER} Transaction {tx.name} has missing "
                                f"documents for {bd} business days and no active {route.role} owner exists "
                                "in its company."
                            ),
                            message_type="notification",
                            subtype_xmlid="mail.mt_note",
                        )
                    continue

            _logger.info(
                "Documents extension: TX %s status=%s (bd=%d, missing: supplier=%s, carrier=%s, buyer=%s)",
                tx.name,
                new_status,
                bd,
                tx.missing_supplier_docs,
                tx.missing_carrier_docs,
                tx.missing_buyer_docs,
            )
        return {"processed": processed, "failures": failures}

    # ══════════════════════════════════════════════════════════════
    # Cron: Scale Ticket Request & Escalation
    # ══════════════════════════════════════════════════════════════

    # Historical evidence. Live reminder and escalation state is stored on each load.
    scale_ticket_reminder_sent = fields.Boolean(
        string="Historical Scale Ticket Reminder",
        default=False,
        readonly=True,
        help=(
            "Migration evidence from the retired transaction-level reminder. "
            "It is not the current status. Each load stores its own reminder."
        ),
    )
    scale_ticket_escalated = fields.Boolean(
        string="Historical Scale Ticket Escalation",
        default=False,
        readonly=True,
        help=(
            "Migration evidence from the retired transaction-level escalation. "
            "It is not the current status. Each load stores its own escalation."
        ),
    )

    def _load_has_current_scale_ticket(self, load, tag):
        """True only when this load has its own current scale ticket.

        A ticket on the transaction or on a sibling load does not count.
        Pending, expired, superseded, and unverified rows stay ineligible.
        """
        documents = self.env["plasticos.document"].search(
            [
                ("tag_id", "=", tag.id),
                ("active", "=", True),
                # The scale-ticket rule reads legacy rows. Operation evidence is a separate obligation.
                *self.env["plasticos.document"]._legacy_obligation_domain(),
                "|",
                ("load_id", "=", load.id),
                "&",
                ("res_model", "=", "plasticos.load"),
                ("res_id", "=", load.id),
            ]
        )
        for document in documents:
            if document._association_conflict_reason():
                document._route_association_conflict()
        return any(document._currently_eligible() for document in documents)

    @staticmethod
    def _scale_ticket_clock_dates(load):
        """Actual delivery and pickup dates from the load's attributed evidence clocks.

        Logistics owns these clocks (BRS-07-R051 as amended 2026-11-11). A state
        change, schedule or dispatch time never fills them. An empty clock is
        unknown: that reminder or escalation does not start. Documents supplies
        only the scale-ticket status and internal note/activity.
        """
        delivery_date = load.actual_delivery_at.date() if load.actual_delivery_at else None
        pickup_date = load.actual_pickup_at.date() if load.actual_pickup_at else None
        return delivery_date, pickup_date

    _SCALE_TICKET_BATCH = 300
    _SCALE_TICKET_CURSOR = "plasticos_documents.scale_ticket_scan_cursor"
    _SCALE_TICKET_RETRY = "plasticos_documents.scale_ticket_retry_ids"

    def _scale_ticket_retry_ids(self):
        raw = self._cron_parameters().get_param(self._SCALE_TICKET_RETRY, "") or ""
        ids = []
        for part in str(raw).split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        return ids

    def _set_scale_ticket_retry_ids(self, load_ids):
        unique = []
        for load_id in load_ids:
            if load_id not in unique:
                unique.append(load_id)
        capped = unique[: self._SCALE_TICKET_BATCH]
        self._cron_parameters().set_param(
            self._SCALE_TICKET_RETRY,
            ",".join(str(load_id) for load_id in capped),
        )

    def _scale_ticket_domain(self):
        return [("transaction_id.state", "in", ("delivered", "closed", "invoiced"))]

    def _next_scale_ticket_batch(self, batch_size):
        """Return the next page and advance a wrapping cursor.

        A short final page sets the cursor back to the start for the following run.
        Processed loads stay eligible to be visited again; their flags make the work idempotent.
        """
        cursor = int(self._cron_parameters().get_param(self._SCALE_TICKET_CURSOR, "0") or 0)
        loads = self.env["plasticos.load"].search(
            self._scale_ticket_domain() + [("id", ">", cursor)],
            order="id ASC",
            limit=batch_size,
        )
        if len(loads) < batch_size:
            next_cursor = 0
        else:
            next_cursor = loads.sorted("id")[-1].id
        self._cron_parameters().set_param(self._SCALE_TICKET_CURSOR, str(next_cursor))
        return loads

    def _get_logistics_manager(self, group, company=None):
        """Return the escalation owner from a manager-level group, or an empty recordset.

        Active internal users only, never the cron service user or the superuser.
        Implied membership counts. The lowest id wins, so the pick is deterministic.
        With a company, the owner must be allowed in that company (POS-INV-05).
        The rule lives in plasticos_base so every escalation site resolves the same owner.
        """
        return self.env["res.users"]._plasticos_escalation_manager_in_group(group, company)

    def _escalation_owners(self, group, companies_by_record):
        """Map each record id to its owner, resolved once per legal company.

        A record with no company takes the first eligible manager. A record whose
        companies conflict gets no owner; the caller reports it.
        """
        users = self.env["res.users"]
        distinct = self.env["res.company"].union(*companies_by_record.values())
        by_company = {company.id: self._get_logistics_manager(group, company) for company in distinct}
        unscoped = self._get_logistics_manager(group)
        owners = {}
        for record_id, companies in companies_by_record.items():
            if len(companies) > 1:
                owners[record_id] = users
            else:
                owners[record_id] = by_company[companies.id] if companies else unscoped
        return owners

    def _escalation_manager_group(self):
        """Operations Manager owns financial, cross-department and unattributed escalations (DEC-010)."""
        return self.env.ref(OWNER_GROUPS[OPERATIONS], raise_if_not_found=False)

    def _logistics_escalation_group(self):
        """Logistics Operations owns confidently attributed shipping-document escalations (DEC-010)."""
        return self.env.ref(OWNER_GROUPS[LOGISTICS], raise_if_not_found=False)

    def _scale_ticket_manager_group(self):
        """A load's own missing scale ticket is attributed shipping paperwork: Logistics."""
        return self._logistics_escalation_group()

    def _escalation_group_for(self, role):
        return self._logistics_escalation_group() if role == LOGISTICS else self._escalation_manager_group()

    def _scale_ticket_route(self):
        router = self.env["plasticos.exception.router"]
        purpose = router.purpose_from_tag_codes(["SCALE"])
        return router.route(purpose, EXC_MISSING_SCALE_TICKET), purpose

    def _record_scale_ticket_escalation(self, load, manager, bd_since_pickup, open_activities):
        router = self.env["plasticos.exception.router"]
        route, purpose = self._scale_ticket_route()
        obligation = Obligation(
            f"ESCALATION: Missing scale ticket on {load.name}",
            purpose,
            EXC_MISSING_SCALE_TICKET,
            f"Load {load.name} on transaction {load.transaction_id.name} is missing a scale ticket. "
            f"Pickup was {bd_since_pickup} business days ago. "
            f"Carrier: {load.carrier_id.name if load.carrier_id else 'Unknown'}. "
            "Please follow up with the carrier.",
        )
        router.upsert(
            load,
            obligation,
            route,
            manager,
            load.company_id,
            self._scale_ticket_manager_group(),
            open_activities,
        )
        load._write_scale_ticket_status({"scale_ticket_escalated": True})
        _logger.info(
            "Scale ticket ESCALATION: load %s transaction %s, %s BD since pickup, assigned to %s",
            load.name,
            load.transaction_id.name,
            bd_since_pickup,
            manager.name,
        )

    def _record_scale_ticket_reminder(self, load, bd_since_delivery):
        carrier_name = load.carrier_id.name if load.carrier_id else "Carrier"
        load.message_post(
            body=(
                f"<b>Automated Request:</b> Scale ticket needed for load {load.name} "
                f"on {load.transaction_id.name}.\n"
                f"Delivery was {bd_since_delivery} business days ago.\n"
                f"Please request scale ticket from {carrier_name}."
            ),
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )
        load._write_scale_ticket_status({"scale_ticket_reminder_sent": True})
        _logger.info(
            "Scale ticket REMINDER: load %s transaction %s, %s BD since delivery",
            load.name,
            load.transaction_id.name,
            bd_since_delivery,
        )

    @api.model
    def cron_check_scale_tickets(self):
        """Check each delivered load for its own missing scale ticket.

        Policy thresholds stay on the transaction document rule.
        Reminder and escalation state are recorded on the load.
        One load's failure is logged and does not stop the rest of the page.
        """
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_documents.cron_check_scale_tickets"]
        )
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping scale-ticket cron: lock is already held.")
            return {"processed": 0, "failures": 0, "skipped": True}

        processed = 0
        failures = 0
        try:
            today = date.today()
            batch_size = int(self.env.context.get("scale_ticket_batch_size") or self._SCALE_TICKET_BATCH)
            previous_retry_ids = self._scale_ticket_retry_ids()
            retry_loads = self.env["plasticos.load"].browse(previous_retry_ids).exists()
            page = self._next_scale_ticket_batch(batch_size)
            seen = set()
            loads = []
            for load in list(retry_loads) + list(page):
                if load.id in seen:
                    continue
                seen.add(load.id)
                loads.append(load)
            if not loads:
                _logger.info("Scale ticket cron: no loads to check.")
                return {"processed": 0, "failures": 0, "skipped": False}

            scale_ticket_tag = self.env["plasticos.document.tag"].search(
                [("code", "=", "SCALE")], order="id ASC", limit=1
            )
            if not scale_ticket_tag:
                _logger.error("Scale ticket cron: SCALE tag not found.")
                return {"processed": 0, "failures": 1, "skipped": False}

            scale_rule = self.env["plasticos.document.rule"].search(
                [
                    ("tag_id", "=", scale_ticket_tag.id),
                    ("res_model", "=", "plasticos.transaction"),
                    ("active", "=", True),
                ],
                order="id ASC",
                limit=1,
            )
            if scale_rule:
                overdue_bd = scale_rule.overdue_business_days or 2
                escalation_bd = scale_rule.escalation_business_days or 7
            else:
                overdue_bd = 2
                escalation_bd = 7
            route, _purpose = self._scale_ticket_route()
            router = self.env["plasticos.exception.router"]
            owners = self.with_context(**{EXCLUDE_CONTEXT_KEY: router._excluded_ids(route.role)})._escalation_owners(
                self._scale_ticket_manager_group(), {load.id: load.company_id for load in loads}
            )
            summaries = {load.id: f"ESCALATION: Missing scale ticket on {load.name}" for load in loads}
            # One query for the page's open escalations (batched page).
            open_by_load = (
                self.env["mail.activity"]
                .search(
                    [
                        ("res_model", "=", "plasticos.load"),
                        ("res_id", "in", list(summaries)),
                        ("summary", "in", list(summaries.values())),
                    ],
                    order="id ASC",
                )
                .grouped("res_id")
            )
            no_activity = self.env["mail.activity"]

            failed_ids = []
            attempted_ids = set()
            for load in loads:
                attempted_ids.add(load.id)
                try:
                    with self.env.cr.savepoint():
                        if self._load_has_current_scale_ticket(load, scale_ticket_tag):
                            router.resolve(
                                load,
                                summaries[load.id],
                                "The load's scale ticket is current.",
                                open_by_load.get(load.id, no_activity),
                            )
                            continue
                        delivery_date, pickup_date = self._scale_ticket_clock_dates(load)
                        bd_since_delivery = self._count_business_days(delivery_date, today) if delivery_date else 0
                        bd_since_pickup = self._count_business_days(pickup_date, today) if pickup_date else 0
                        due_escalation = bd_since_pickup >= escalation_bd and not load.scale_ticket_escalated
                        due_reminder = bd_since_delivery >= overdue_bd and not load.scale_ticket_reminder_sent
                        if due_escalation:
                            manager = owners[load.id]
                            if not manager:
                                failures += 1
                                _logger.error(
                                    "Scale ticket ESCALATION skipped: load %s has no Logistics owner in its company.",
                                    load.name,
                                )
                                self.env["res.users"]._plasticos_note_unrouted_escalation(
                                    load,
                                    "scale ticket escalation",
                                    f"Load {load.name} is missing a scale ticket {bd_since_pickup} business days "
                                    "after pickup and no active Logistics owner exists in its company. "
                                    "Assign it manually.",
                                )
                            else:
                                self._record_scale_ticket_escalation(
                                    load, manager, bd_since_pickup, open_by_load.get(load.id, no_activity)
                                )
                        if due_reminder:
                            self._record_scale_ticket_reminder(load, bd_since_delivery)
                        processed += 1
                except Exception:
                    failures += 1
                    failed_ids.append(load.id)
                    _logger.exception("Scale ticket cron failed for load %s", load.name)
            still_waiting = [
                load_id for load_id in previous_retry_ids if load_id not in attempted_ids and load_id in retry_loads.ids
            ]
            self._set_scale_ticket_retry_ids(still_waiting + failed_ids)
            if failures:
                _logger.error("Scale ticket cron finished with %s load failures.", failures)
            return {"processed": processed, "failures": failures, "skipped": False}
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_documents.cron_check_scale_tickets"]
            )


class PlasticosLoadScaleTicket(models.Model):
    """Per-load scale-ticket reminder state. A sibling load does not share it."""

    _inherit = "plasticos.load"

    scale_ticket_reminder_sent = fields.Boolean(
        string="Scale Ticket Reminder Sent",
        default=False,
        help="True after the reminder for this load's own missing scale ticket.",
    )
    scale_ticket_escalated = fields.Boolean(
        string="Scale Ticket Escalated",
        default=False,
        help="True after the escalation for this load's own missing scale ticket.",
    )


class PlasticosEscalationReroute(models.AbstractModel):
    """Move open document escalations to their DEC-010 owner. Repeatable: a second run changes nothing."""

    _name = "plasticos.escalation.reroute"
    _description = "Reroute open document escalations (DEC-010)"

    @api.model
    def _owner_roles(self, activities):
        operations = self.env.ref(OWNER_GROUPS[OPERATIONS], raise_if_not_found=False)
        counts = {LOGISTICS: 0, OPERATIONS: 0, "other": 0}
        for activity in activities.exists():
            user = activity.user_id
            if operations and user and operations in user.all_group_ids:
                counts[OPERATIONS] += 1
            elif user and user.has_group(OWNER_GROUPS[LOGISTICS]):
                counts[LOGISTICS] += 1
            else:
                counts["other"] += 1
        return counts

    @api.model
    def _base_note(self, activity):
        text = html2plaintext(activity.note or "").strip()
        return text.split(" Routed to ")[0]

    @api.model
    def reroute_open_escalations(self):
        """Return a ``RerouteResult``: owner counts by role before and after, and the changed count."""
        Activity = self.env["mail.activity"]
        router = self.env["plasticos.exception.router"]
        transactions = self.env["plasticos.transaction"]
        activities = Activity.search(
            [
                "|",
                "&",
                ("res_model", "=", "plasticos.transaction"),
                ("summary", "=like", "ESCALATION: Missing documents on %"),
                "&",
                ("res_model", "=", "plasticos.load"),
                ("summary", "=like", "ESCALATION: Missing scale ticket on %"),
            ],
            order="id ASC",
        )
        before = self._owner_roles(activities)
        rerouted = 0
        for activity in activities:
            if not activity.exists():
                continue  # closed as a duplicate of an earlier one in this run
            snapshot = (activity.user_id.id, activity.activity_type_id.id)
            record = self.env[activity.res_model].browse(activity.res_id).exists()
            if not record:
                continue
            if record._name == "plasticos.transaction":
                purpose = router.purpose_from_tag_codes(
                    self.env["plasticos.compliance.service"].get_missing_documents("plasticos.transaction", record.id)
                )
                exception_class = EXC_MISSING_DOCUMENTS
                company = record.sale_order_id.company_id | record.purchase_order_ids.company_id
                group = transactions._escalation_group_for(router.route(purpose, exception_class).role)
            else:
                purpose = router.purpose_from_tag_codes(["SCALE"])
                exception_class = EXC_MISSING_SCALE_TICKET
                company = record.company_id
                group = transactions._scale_ticket_manager_group()
            route = router.route(purpose, exception_class)
            owner = router.owner(route, company or None, group)
            obligation = Obligation(activity.summary, purpose, exception_class, self._base_note(activity))
            kept = router.upsert(record, obligation, route, owner, company or None, group)
            if not owner and not router.owner_is_valid(kept.user_id, route, company or None, group):
                _logger.error(
                    "Escalation activity %s has no eligible %s owner; it stays assigned.", activity.id, route.role
                )
            if (kept.user_id.id, kept.activity_type_id.id) != snapshot:
                rerouted += 1
        after = self._owner_roles(activities)
        _logger.info("Rerouted %d escalation activities: before %s, after %s", rerouted, before, after)
        return RerouteResult(before, after, rerouted)
