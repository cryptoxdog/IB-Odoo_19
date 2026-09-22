"""Odoo-native, non-executing internal review requests for Mack work.

This model is a durable attention and audit record. It creates one Odoo activity
for an explicitly configured internal reviewer and one concise chatter note on
the canonical intake. It does not grant authority, emit email, invoke Mack,
invoke Gate/CEG, mutate a CWI, run matching, or create commercial effects.
"""

from __future__ import annotations

import re

from markupsafe import escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_ROUTE_POLICY_KEY = "hot_web_lead_reviewer/v1"
_DELIVERY_MODE = "in_odoo_activity_only"
_ALLOWED_CANDIDATE_ACTIONS = frozenset(
    {
        "human_owned_consult",
        "request_match_intake",
        "request_internal_review",
        "prepare_non_authoritative_terms",
    }
)
_ALLOWED_PRIORITIES = frozenset({"0", "1", "2", "3"})
_MAX_EVIDENCE_REFS = 32
_MAX_RISK_CODES = 16
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def _validated_string_list(value: object, *, field_name: str, maximum: int) -> list[str]:
    """Return bounded, duplicate-free strings from a JSON list boundary."""
    if not isinstance(value, list):
        raise ValidationError(_("%s must be a JSON list.") % field_name)
    if len(value) > maximum:
        raise ValidationError(_("%s exceeds the maximum number of values.") % field_name)
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValidationError(_("%s values must be non-empty text.") % field_name)
        candidate = item.strip()
        if len(candidate) > 512:
            raise ValidationError(_("%s values are too long.") % field_name)
        if candidate in normalized:
            raise ValidationError(_("%s must not contain duplicate values.") % field_name)
        normalized.append(candidate)
    return normalized


def _safe_note_text(value: object) -> str:
    """Escape a value before placing it in Odoo's HTML chatter/activity body."""
    return str(escape(str(value)))


class PlasticosMackInternalReview(models.Model):
    """One idempotent request for an internal Odoo review of a HOT intake."""

    _name = "plasticos.mack.internal.review"
    _description = "Mack Internal Review Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Review Request",
        required=True,
        readonly=True,
        copy=False,
        default="New",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete="restrict",
    )
    intake_id = fields.Many2one(
        "plasticos.intake",
        string="Intake",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
        check_company=True,
    )
    requester_id = fields.Many2one(
        "res.users",
        string="Requested By",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
        index=True,
        ondelete="restrict",
    )
    reviewer_id = fields.Many2one(
        "res.users",
        string="Internal Reviewer",
        required=True,
        readonly=True,
        index=True,
        domain="[('share', '=', False), ('active', '=', True)]",
        ondelete="restrict",
    )
    activity_id = fields.Many2one(
        "mail.activity",
        string="Odoo Activity",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    cwi_ref = fields.Char(string="CWI Reference", required=True, readonly=True, index=True)
    cwi_revision = fields.Integer(string="CWI Revision", required=True, readonly=True)
    decision_snapshot_hash = fields.Char(string="Decision Snapshot Hash", required=True, readonly=True, index=True)
    candidate_action = fields.Selection(
        selection=[(action, action.replace("_", " ").title()) for action in sorted(_ALLOWED_CANDIDATE_ACTIONS)],
        required=True,
        readonly=True,
    )
    reason = fields.Text(string="Review Reason", required=True, readonly=True)
    risk_codes = fields.Json(string="Risk Codes", required=True, readonly=True)
    evidence_refs = fields.Json(string="Evidence References", required=True, readonly=True)
    priority = fields.Selection(
        [
            ("0", "Low"),
            ("1", "Normal"),
            ("2", "High"),
            ("3", "Urgent"),
        ],
        required=True,
        readonly=True,
        default="1",
    )
    deadline = fields.Date(required=True, readonly=True)
    idempotency_key = fields.Char(required=True, readonly=True, index=True)
    route_policy_key = fields.Char(required=True, readonly=True, default=_ROUTE_POLICY_KEY)
    route_policy_revision = fields.Char(required=True, readonly=True)
    delivery_mode = fields.Selection(
        [("in_odoo_activity_only", "Odoo Activity Only")],
        required=True,
        readonly=True,
        default=_DELIVERY_MODE,
    )
    state = fields.Selection(
        [("requested", "Requested"), ("cancelled", "Cancelled")],
        required=True,
        readonly=True,
        default="requested",
        tracking=True,
    )

    _sql_constraints = [
        ("mack_internal_review_name_unique", "unique(name)", "Review request reference must be unique."),
        (
            "mack_internal_review_idempotency_unique",
            "unique(company_id, idempotency_key)",
            "An internal review request already exists for this company and idempotency key.",
        ),
    ]

    @api.constrains(
        "cwi_ref",
        "cwi_revision",
        "decision_snapshot_hash",
        "reason",
        "risk_codes",
        "evidence_refs",
        "priority",
        "idempotency_key",
        "route_policy_key",
        "route_policy_revision",
        "delivery_mode",
        "deadline",
    )
    def _check_request_shape(self):
        for record in self:
            if not (record.cwi_ref or "").strip():
                raise ValidationError(_("CWI reference is required."))
            if len(record.cwi_ref) > 256:
                raise ValidationError(_("CWI reference must be at most 256 characters."))
            if record.cwi_revision < 0:
                raise ValidationError(_("CWI revision must be non-negative."))
            if not _SHA256_RE.fullmatch((record.decision_snapshot_hash or "").strip()):
                raise ValidationError(_("Decision snapshot hash must be a SHA-256 digest."))
            if not (record.reason or "").strip() or len(record.reason) > 4_096:
                raise ValidationError(_("Review reason is required and must be at most 4096 characters."))
            _validated_string_list(record.risk_codes, field_name="Risk codes", maximum=_MAX_RISK_CODES)
            evidence_refs = _validated_string_list(
                record.evidence_refs,
                field_name="Evidence references",
                maximum=_MAX_EVIDENCE_REFS,
            )
            if not evidence_refs:
                raise ValidationError(_("At least one evidence reference is required."))
            if record.priority not in _ALLOWED_PRIORITIES:
                raise ValidationError(_("Priority is invalid."))
            if record.candidate_action not in _ALLOWED_CANDIDATE_ACTIONS:
                raise ValidationError(_("Candidate action is invalid."))
            if not record.deadline or record.deadline < fields.Date.today():
                raise ValidationError(_("Review deadline must be today or later."))
            if not (record.idempotency_key or "").strip() or len(record.idempotency_key) > 256:
                raise ValidationError(_("Idempotency key is required and must be at most 256 characters."))
            if record.route_policy_key != _ROUTE_POLICY_KEY:
                raise ValidationError(_("Review routing policy key is invalid."))
            if not (record.route_policy_revision or "").strip():
                raise ValidationError(_("Review routing policy revision is required."))
            if record.delivery_mode != _DELIVERY_MODE:
                raise ValidationError(_("Only Odoo-native activity delivery is allowed."))

    @api.model_create_multi
    def create(self, vals_list):
        """Resolve one configured reviewer and create one activity per request."""
        result = self.browse([])
        for values in vals_list:
            values = dict(values)
            if values.get("name", "New") == "New":
                values["name"] = self.env["ir.sequence"].next_by_code("plasticos.mack.internal.review") or "New"
            if values.get("reviewer_id"):
                raise AccessError(_("Reviewer identity is resolved by Odoo routing policy, not the caller."))
            intake_id = values.get("intake_id")
            if not isinstance(intake_id, int) or isinstance(intake_id, bool):
                raise ValidationError(_("Review target intake is required."))
            intake = self.env["plasticos.intake"].browse(intake_id).exists()
            if not intake:
                raise ValidationError(_("Review target intake does not exist."))
            if not intake.source_lead_id:
                raise ValidationError(_("Only an intake created from a HOT web lead is eligible for Mack review."))
            web_lead = self.env["plasticos.web.lead"].browse(intake.source_lead_id).exists()
            if not web_lead or web_lead.decision != "hot" or web_lead.intake_id != intake:
                raise ValidationError(_("Review target must be the canonical intake of a HOT web lead."))
            config = self.env["plasticos.web.lead.config"].get_config()
            reviewer = config.hot_intake_reviewer_id
            if not reviewer or reviewer.share or not reviewer.active:
                raise ValidationError(_("HOT reviewer routing is not configured to an active internal user."))
            values["reviewer_id"] = reviewer.id
            values["company_id"] = self.env.company.id
            values["requester_id"] = self.env.user.id
            values["route_policy_key"] = _ROUTE_POLICY_KEY
            values["route_policy_revision"] = str(config.write_date or config.create_date or config.id)
            values["delivery_mode"] = _DELIVERY_MODE
            values["state"] = "requested"
            values["deadline"] = fields.Date.to_date(values.get("deadline"))
            existing = self.search(
                [
                    ("company_id", "=", values["company_id"]),
                    ("idempotency_key", "=", values.get("idempotency_key")),
                ],
                limit=1,
            )
            if existing:
                existing._assert_idempotent_replay(values)
                result |= existing
                continue
            request = super().create([values])
            request._schedule_in_odoo_activity()
            request._post_intake_audit_note()
            result |= request
        return result

    def write(self, values):
        if set(values) != {"activity_id"} or not self.env.context.get("mack_internal_review_system_write"):
            raise AccessError(_("Internal review requests are immutable after creation."))
        return super().write(values)

    def unlink(self):
        raise AccessError(_("Internal review requests are retained for audit and cannot be deleted."))

    def _schedule_in_odoo_activity(self):
        self.ensure_one()
        if self.activity_id:
            return
        activity = self.intake_id.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=self.reviewer_id.id,
            summary=_("Mack internal review: %s") % self.name,
            note=self._activity_note(),
            date_deadline=self.deadline,
        )
        self.with_context(mack_internal_review_system_write=True).write({"activity_id": activity.id})

    def _post_intake_audit_note(self):
        self.ensure_one()
        self.intake_id.message_post(
            body=self._audit_note(),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

    def _activity_note(self):
        self.ensure_one()
        evidence_refs = _validated_string_list(
            self.evidence_refs,
            field_name="Evidence references",
            maximum=_MAX_EVIDENCE_REFS,
        )
        risk_codes = _validated_string_list(self.risk_codes, field_name="Risk codes", maximum=_MAX_RISK_CODES)
        return "<br/>".join(
            [
                _("Review request: %s") % _safe_note_text(self.name),
                _("Candidate action: %s") % _safe_note_text(self.candidate_action),
                _("Reason: %s") % _safe_note_text(self.reason),
                _("Risk codes: %s") % _safe_note_text(", ".join(risk_codes) or _("None")),
                _("Evidence: %s") % _safe_note_text(", ".join(evidence_refs)),
                _("Decision snapshot: %s") % _safe_note_text(self.decision_snapshot_hash),
                _("Delivery: Odoo activity only; not a commercial approval."),
            ]
        )

    def _audit_note(self):
        self.ensure_one()
        return _(
            "Mack internal review request %s was routed to %s through policy %s (revision %s). "
            "This is an internal Odoo activity only, not a mandate, approval, or authority grant."
        ) % (
            _safe_note_text(self.name),
            _safe_note_text(self.reviewer_id.display_name),
            _safe_note_text(self.route_policy_key),
            _safe_note_text(self.route_policy_revision),
        )

    def _assert_idempotent_replay(self, values):
        """Accept only a materially identical retry of one prior review request."""
        self.ensure_one()
        comparable = {
            "intake_id": self.intake_id.id,
            "cwi_ref": self.cwi_ref,
            "cwi_revision": self.cwi_revision,
            "decision_snapshot_hash": self.decision_snapshot_hash,
            "candidate_action": self.candidate_action,
            "reason": self.reason,
            "risk_codes": self.risk_codes,
            "evidence_refs": self.evidence_refs,
            "priority": self.priority,
            "deadline": self.deadline,
            "route_policy_key": self.route_policy_key,
            "route_policy_revision": self.route_policy_revision,
            "delivery_mode": self.delivery_mode,
        }
        for field_name, existing_value in comparable.items():
            if values.get(field_name) != existing_value:
                raise ValidationError(
                    _("Idempotency key is already bound to different review request material (%s).") % field_name
                )


class PlasticosIntake(models.Model):
    """Expose immutable Mack review records on their canonical intake."""

    _inherit = "plasticos.intake"

    mack_review_request_ids = fields.One2many(
        "plasticos.mack.internal.review",
        "intake_id",
        string="Mack Internal Review Requests",
        readonly=True,
    )
    mack_review_request_count = fields.Integer(compute="_compute_mack_review_request_count")

    @api.depends("mack_review_request_ids")
    def _compute_mack_review_request_count(self):
        for intake in self:
            intake.mack_review_request_count = len(intake.mack_review_request_ids)

    def action_view_mack_review_requests(self):
        self.ensure_one()
        action = self.env.ref("plasticos_mack_workbench.action_mack_internal_review").read()[0]
        action["domain"] = [("intake_id", "=", self.id)]
        action["context"] = {"default_intake_id": self.id}
        return action
