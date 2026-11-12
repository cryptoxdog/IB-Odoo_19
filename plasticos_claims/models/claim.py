import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

CLAIMS_MANAGER_GROUP_XMLID = "plasticos_claims.group_claims_manager"
SYSTEM_CRON_USER_XMLID = "plasticos_base.user_system_cron"


class PlasticosClaim(models.Model):
    _name = "plasticos.claim"
    _description = "QC Case / Claim"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _rec_name = "name"

    # ── Identity ─────────────────────────────────────────────
    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        default="New",
        copy=False,
        index=True,
    )
    transaction_id = fields.Many2one(
        "plasticos.transaction",
        string="Transaction",
        required=True,
        index=True,
        ondelete="restrict",
    )
    load_id = fields.Many2one(
        "plasticos.load",
        string="Load",
        index=True,
        ondelete="restrict",
        help="Set only when this claim is about one load. Empty claims stay transaction-level.",
    )
    source_document_id = fields.Many2one(
        "plasticos.document",
        string="Source Document",
        help="Document that triggered this claim (e.g., Claim Pics).",
        ondelete="restrict",
    )

    # ── Classification ───────────────────────────────────────
    case_type = fields.Selection(
        [
            ("buyer_claim", "Buyer Claim"),
            ("inspection", "Inspection"),
            ("freight_chargeback", "Freight Chargeback"),
            ("lightweight_penalty", "Lightweight Penalty"),
            ("other", "Other"),
        ],
        string="Case Type",
        required=True,
        default="buyer_claim",
        index=True,
        tracking=True,
    )
    severity = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
        string="Severity",
        required=True,
        default="medium",
        tracking=True,
    )

    # ── Workflow State ───────────────────────────────────────
    state = fields.Selection(
        [
            ("pending", "Pending Review"),
            ("in_progress", "In Progress"),
            ("escalated", "Escalated"),
            ("resolved", "Resolved"),
            ("archived", "Archived"),
        ],
        string="Status",
        required=True,
        default="pending",
        index=True,
        tracking=True,
    )
    assignee_id = fields.Many2one(
        "res.users",
        string="Assignee",
        index=True,
        tracking=True,
        ondelete="restrict",
    )

    # ── SLA Tracking ─────────────────────────────────────────
    opened_at = fields.Datetime(
        string="Opened At",
        default=fields.Datetime.now,
        readonly=True,
    )
    escalated_at = fields.Datetime(
        string="Escalated At",
        readonly=True,
    )
    resolved_at = fields.Datetime(
        string="Resolved At",
        readonly=True,
    )
    last_reminder_at = fields.Datetime(
        string="Last Reminder",
        readonly=True,
    )
    sla_hours = fields.Integer(
        string="SLA Hours",
        default=24,
        help="Hours before auto-escalation.",
    )

    # ── Financial ────────────────────────────────────────────
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        ondelete="restrict",
    )
    claimed_amount = fields.Float(
        string="Claimed Amount",
        help="Amount claimed by buyer or requested recovery.",
    )
    recovery_amount = fields.Float(
        string="Recovery Amount",
        help="Actual amount recovered (chargeback, penalty credit, etc.).",
    )
    recovery_rate = fields.Float(
        string="Recovery Rate (%)",
        compute="_compute_recovery_rate",
        store=True,
        help="Percentage of claimed amount recovered.",
    )

    # ── Notes ────────────────────────────────────────────────
    notes = fields.Text(
        string="Notes",
        help="Internal notes and discussion.",
    )
    description = fields.Text(
        string="Description",
        help="Detailed description of the quality issue.",
    )
    resolution_note = fields.Text(
        string="Resolution Note",
        help="Required explanation when resolving the case.",
    )

    # ── Investigation (harvested from linda_logistics_v6) ───
    investigation_notes = fields.Text(
        string="Investigation Notes",
        help="Notes from the investigation process.",
    )
    root_cause = fields.Text(
        string="Root Cause",
        help="Identified root cause of the issue.",
    )
    corrective_action = fields.Text(
        string="Corrective Action",
        help="Actions taken to prevent recurrence.",
    )
    resolution_type = fields.Selection(
        [
            ("credit", "Credit Note"),
            ("replacement", "Replacement Material"),
            ("discount", "Price Discount"),
            ("rejected", "Claim Rejected"),
            ("other", "Other Resolution"),
        ],
        string="Resolution Type",
        help="How the claim was resolved.",
    )

    # ── Escalation Tracking ────────────────────────────────
    escalation_level = fields.Integer(
        string="Escalation Level",
        default=0,
        help="Number of times this claim has been escalated.",
    )
    escalated_to_id = fields.Many2one(
        "res.users",
        string="Escalated To",
        help="User this claim was escalated to.",
        ondelete="restrict",
    )
    escalation_reason = fields.Text(
        string="Escalation Reason",
        help="Reason for escalation.",
    )

    # ── Photo Evidence ─────────────────────────────────────
    photo_ids = fields.Many2many(
        "ir.attachment",
        "plasticos_claim_photo_rel",
        "claim_id",
        "attachment_id",
        string="Photos",
        help="Photo evidence of the quality issue.",
    )

    # ── Computed ───────────────────────────────────────────
    days_open = fields.Integer(
        string="Days Open",
        compute="_compute_days_open",
    )
    is_overdue = fields.Boolean(
        string="Overdue",
        compute="_compute_is_overdue",
        store=True,
        help="True if claim is past SLA deadline. Recomputed by cron.",
    )

    # ── Constraints ──────────────────────────────────────────
    _unique_name = models.Constraint(
        "unique(name)",
        "Claim reference must be unique.",
    )

    @api.constrains("state", "resolution_note")
    def _check_resolution_note(self):
        for rec in self:
            if rec.state == "resolved" and not rec.resolution_note:
                raise ValidationError("Resolution note is required when resolving a claim.")

    # ── CRUD ─────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        names = []
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("plasticos.claim") or "New"
            name = vals.get("name")
            if name and name != "New":
                names.append(name)
        taken = set(self.search([("name", "in", names)]).mapped("name")) if names else set()
        for name in names:
            if name in taken:
                raise ValidationError(f"Claim reference '{name}' already exists.")
        return super().create(vals_list)

    def write(self, vals):
        """Guard against modifying archived claims (except state changes)."""
        name = vals.get("name")
        if name and self:
            # One reference written to several claims is always a duplicate; otherwise one
            # query asks whether a claim outside this recordset already holds it.
            if len(self) > 1 or self.search([("name", "=", name), ("id", "not in", self.ids)], limit=1):
                raise ValidationError(f"Claim reference '{name}' already exists.")
        if "state" not in vals:
            for rec in self:
                if rec.state == "archived":
                    raise ValidationError(f"Cannot modify archived claim '{rec.name}'. Reopen it first.")
        return super().write(vals)

    def unlink(self):
        """Prevent deletion of resolved/archived claims."""
        for rec in self:
            if rec.state in ("resolved", "archived"):
                raise ValidationError(
                    f"Cannot delete claim '{rec.name}' in state '{rec.state}'. "
                    "Resolved/archived claims must be preserved for audit."
                )
        return super().unlink()

    # ── Actions ──────────────────────────────────────────────
    def action_start(self):
        for rec in self:
            if rec.state == "pending":
                rec.state = "in_progress"

    def action_escalate(self, reason=None, escalate_to=None):
        self._escalate(reason=reason, escalate_to=escalate_to)

    def _escalate(self, reason=None, escalate_to=None, manager=None):
        """Escalate; ``manager`` is a reviewer the caller already resolved for the batch."""
        for rec in self:
            if rec.state in ("pending", "in_progress"):
                vals = {
                    "state": "escalated",
                    "escalated_at": fields.Datetime.now(),
                    "escalation_level": rec.escalation_level + 1,
                }
                if reason:
                    vals["escalation_reason"] = reason
                if escalate_to:
                    vals["escalated_to_id"] = escalate_to.id if hasattr(escalate_to, "id") else escalate_to
                rec.write(vals)
                rec._create_escalation_activity(manager=manager)

    def action_resolve(self):
        """Resolve the claim.

        NOTE: We do NOT manually call _update_transaction_recoveries() here.
        The transaction's _compute_chargebacks_penalties() method (in transaction_claims.py)
        has @api.depends on claim_ids.state and claim_ids.recovery_amount, so it
        auto-recomputes when we write state='resolved'. Manual update would be redundant.
        """
        for rec in self:
            if not rec.resolution_note:
                raise ValidationError("Please provide a resolution note before resolving.")
            rec.write(
                {
                    "state": "resolved",
                    "resolved_at": fields.Datetime.now(),
                }
            )

    def action_archive(self):
        for rec in self:
            if rec.state == "resolved":
                rec.state = "archived"

    def action_reopen(self):
        for rec in self:
            if rec.state in ("resolved", "archived"):
                rec.write(
                    {
                        "state": "in_progress",
                        "resolved_at": False,
                    }
                )

    # ── Computed Methods (harvested) ──────────────────────────
    @api.depends("opened_at", "state")
    def _compute_days_open(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.opened_at and rec.state not in ("resolved", "archived"):
                delta = now - rec.opened_at
                rec.days_open = delta.days
            else:
                rec.days_open = 0

    @api.depends("opened_at", "sla_hours", "state")
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.opened_at and rec.state not in ("resolved", "archived"):
                deadline = rec.opened_at + timedelta(hours=rec.sla_hours)
                rec.is_overdue = now > deadline
            else:
                rec.is_overdue = False

    @api.depends("claimed_amount", "recovery_amount")
    def _compute_recovery_rate(self):
        """Percentage of claimed amount recovered."""
        for rec in self:
            if rec.claimed_amount > 0:
                rec.recovery_rate = min((rec.recovery_amount / rec.claimed_amount) * 100, 100)
            else:
                rec.recovery_rate = 0.0

    # ── Navigation Actions (for smart buttons) ───────────────

    @api.constrains("transaction_id", "load_id")
    def _check_load_belongs_to_transaction(self):
        for rec in self:
            if rec.load_id and rec.load_id.transaction_id != rec.transaction_id:
                raise ValidationError("The selected load does not belong to this claim's transaction.")

    @api.onchange("transaction_id")
    def _onchange_transaction_clear_foreign_load(self):
        if self.load_id and self.load_id.transaction_id != self.transaction_id:
            self.load_id = False

    def action_view_transaction(self):
        """Navigate to the linked transaction."""
        self.ensure_one()
        if not self.transaction_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": f"Transaction — {self.transaction_id.name}",
            "res_model": "plasticos.transaction",
            "view_mode": "form",
            "res_id": self.transaction_id.id,
        }

    def action_view_load(self):
        """Navigate to the linked load."""
        self.ensure_one()
        if not self.load_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": f"Load — {self.load_id.name}",
            "res_model": "plasticos.load",
            "view_mode": "form",
            "res_id": self.load_id.id,
        }

    # ── SLA Cron ─────────────────────────────────────────────
    @api.model
    def _cron_check_sla(self):
        """Auto-escalate claims past SLA and create daily reminders."""
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_claims.cron_claim_sla_check"])
        locked = self.env.cr.fetchone()[0]
        if not locked:
            return

        try:
            now = fields.Datetime.now()
            # One reviewer lookup for the whole run; an empty result is kept as the answer.
            manager = self._claims_manager_reviewer()

            # Recompute is_overdue for all open claims (stored computed field)
            open_for_recompute = self.search(
                [("state", "not in", ("resolved", "archived"))],
                order="opened_at ASC, id ASC",
                limit=500,
            )
            open_for_recompute._compute_is_overdue()

            # Auto-escalate pending claims past SLA
            pending = self.search([("state", "=", "pending")], order="opened_at ASC, id ASC", limit=300)
            for claim in pending:
                deadline = claim.opened_at + timedelta(hours=claim.sla_hours)
                if now > deadline:
                    claim._escalate(manager=manager)

            # Daily reminders for open claims
            open_claims = self.search(
                [("state", "in", ("pending", "in_progress", "escalated"))],
                order="last_reminder_at ASC, opened_at ASC, id ASC",
                limit=300,
            )
            # One query for today's reminder activities on every open claim in this run.
            reminded_today = {
                (row["res_id"], row["summary"])
                for row in self.env["mail.activity"].search_read(
                    [
                        ("res_model", "=", "plasticos.claim"),
                        ("res_id", "in", open_claims.ids),
                        ("date_deadline", "=", fields.Date.today()),
                    ],
                    ["res_id", "summary"],
                    order="id ASC",
                )
            }
            for claim in open_claims:
                if claim.last_reminder_at:
                    last = claim.last_reminder_at
                    if (now - last).days < 1:
                        continue
                if (claim.id, f"Open Claim Reminder: {claim.name}") in reminded_today:
                    continue
                claim._create_reminder_activity(manager=manager)
                claim.last_reminder_at = now
        finally:
            self.env.cr.execute("SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_claims.cron_claim_sla_check"])

    # ── Manager routing ──────────────────────────────────────
    @api.model
    def _claims_manager_reviewer(self):
        """Return the one claims manager unresolved claim work is routed to, or nobody.

        The lowest-id active internal user holding the Claims Manager group.
        The system cron user holds that group for ACL reasons only (see
        ``hooks.post_init_hook``) and is never eligible.
        """
        users = self.env["res.users"]
        cron_user = self.env.ref(SYSTEM_CRON_USER_XMLID, raise_if_not_found=False)
        # Membership must resolve the same way under the cron user and under a
        # claims user who cannot read other users' access rights.
        elevated = users.sudo()  # sudo: read-only group membership lookup, returns one user id
        internal_users = elevated.search([("share", "=", False), ("active", "=", True)], order="id ASC")
        for user in internal_users:
            if cron_user and user == cron_user:
                continue
            if user.has_group(CLAIMS_MANAGER_GROUP_XMLID):
                return users.browse(user.id)
        return users.browse()

    def _route_to_claims_manager(self, summary, note, assign=False, manager=None):
        """Schedule manager work on this claim, or record visibly that nobody can take it.

        Returns the manager, or an empty recordset when the Claims Manager group
        has no eligible member. That case is logged as an error and written to
        the claim's chatter; the current user is never substituted. ``manager``
        is a reviewer already resolved by the caller (an empty recordset means
        nobody is eligible); ``None`` resolves it here.
        """
        self.ensure_one()
        if manager is None:
            manager = self._claims_manager_reviewer()
        if not manager:
            _logger.error(
                "Claim %s (id=%s): '%s' could not be routed, the Claims Manager group has no eligible member.",
                self.name,
                self.id,
                summary,
            )
            self.message_post(
                body=(
                    f"Not routed: {summary}. No active internal user holds the Claims Manager role, "
                    "so nobody was assigned. Add a Claims Manager, then assign this claim."
                ),
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
            return manager
        if assign and not self.assignee_id:
            self.assignee_id = manager
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=manager.id,
            summary=summary,
            note=note,
        )
        return manager

    def _send_claim_notification(self):
        """Route an auto-created claim to a claims manager and notify by email.

        The claim is assigned to the claims manager and the manager gets the
        activity. The email template is information only; it creates no work
        for its recipient.
        """
        self.ensure_one()
        self._route_to_claims_manager(
            summary=f"New Claim Created: {self.name}",
            note=f"Claim {self.name} auto-created from document upload.",
            assign=True,
        )
        template = self.env.ref(
            "plasticos_claims.email_template_claim_created",
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=False)

    def _create_escalation_activity(self, manager=None):
        """Create activity for the claims manager on escalation."""
        self.ensure_one()
        self._route_to_claims_manager(
            summary=f"Escalated Claim: {self.name}",
            note=f"Claim {self.name} has been escalated due to SLA breach.",
            manager=manager,
        )

    def _create_reminder_activity(self, manager=None):
        """Create daily reminder activity for the assignee, else the claims manager."""
        self.ensure_one()
        summary = f"Open Claim Reminder: {self.name}"
        note = f"Claim {self.name} is still open and requires attention."
        if not self.assignee_id:
            self._route_to_claims_manager(summary=summary, note=note, manager=manager)
            return
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=self.assignee_id.id,
            summary=summary,
            note=note,
        )
