from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


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
        related="transaction_id.load_id",
        store=True,
        index=True,
    )
    source_document_id = fields.Many2one(
        "plasticos.document",
        string="Source Document",
        help="Document that triggered this claim (e.g., Claim Pics).",
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
    claimed_amount = fields.Float(
        string="Claimed Amount",
        help="Amount claimed by buyer or requested recovery.",
    )
    recovery_amount = fields.Float(
        string="Recovery Amount",
        help="Actual amount recovered (chargeback, penalty credit, etc.).",
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
    )

    # ── Constraints ──────────────────────────────────────────
    _sql_constraints = [
        ("unique_name", "unique(name)", "Claim reference must be unique."),
    ]

    @api.constrains("state", "resolution_note")
    def _check_resolution_note(self):
        for rec in self:
            if rec.state == "resolved" and not rec.resolution_note:
                raise ValidationError("Resolution note is required when resolving a claim.")

    # ── CRUD ─────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("plasticos.claim") or "New"
        return super().create(vals_list)

    # ── Actions ──────────────────────────────────────────────
    def action_start(self):
        for rec in self:
            if rec.state == "pending":
                rec.state = "in_progress"

    def action_escalate(self, reason=None, escalate_to=None):
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
                rec._create_escalation_activity()

    def action_resolve(self):
        for rec in self:
            if not rec.resolution_note:
                raise ValidationError("Please provide a resolution note before resolving.")
            rec.write(
                {
                    "state": "resolved",
                    "resolved_at": fields.Datetime.now(),
                }
            )
            rec._update_transaction_recoveries()

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

    # ── SLA Cron ─────────────────────────────────────────────
    @api.model
    def _cron_check_sla(self):
        """Auto-escalate claims past SLA and create daily reminders."""
        now = fields.Datetime.now()

        # Auto-escalate pending claims past SLA
        pending = self.search([("state", "=", "pending")])
        for claim in pending:
            deadline = claim.opened_at + timedelta(hours=claim.sla_hours)
            if now > deadline:
                claim.action_escalate()

        # Daily reminders for open claims
        open_claims = self.search([("state", "in", ("pending", "in_progress", "escalated"))])
        for claim in open_claims:
            if claim.last_reminder_at:
                last = claim.last_reminder_at
                if (now - last).days < 1:
                    continue
            claim._create_reminder_activity()
            claim.last_reminder_at = now

    def _create_escalation_activity(self):
        """Create activity for quality manager on escalation."""
        self.ensure_one()
        quality_manager_group = self.env.ref("plasticos_claims.group_claims_manager", raise_if_not_found=False)
        if quality_manager_group and quality_manager_group.users:
            manager = quality_manager_group.users[0]
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=manager.id,
                summary=f"Escalated Claim: {self.name}",
                note=f"Claim {self.name} has been escalated due to SLA breach.",
            )

    def _create_reminder_activity(self):
        """Create daily reminder activity for assignee."""
        self.ensure_one()
        user = self.assignee_id or self.env.user
        self.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=user.id,
            summary=f"Open Claim Reminder: {self.name}",
            note=f"Claim {self.name} is still open and requires attention.",
        )

    def _update_transaction_recoveries(self):
        """Update transaction chargeback/penalty fields when claim resolved."""
        self.ensure_one()
        if not self.transaction_id:
            return

        tx = self.transaction_id
        resolved_claims = self.search(
            [
                ("transaction_id", "=", tx.id),
                ("state", "=", "resolved"),
            ]
        )

        chargebacks = sum(c.recovery_amount for c in resolved_claims if c.case_type == "freight_chargeback")
        penalties = sum(c.recovery_amount for c in resolved_claims if c.case_type == "lightweight_penalty")

        tx.write(
            {
                "freight_chargebacks": chargebacks,
                "lightweight_penalties": penalties,
            }
        )
