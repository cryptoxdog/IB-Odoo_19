"""Odoo-native, non-executing internal review requests for Mack work.

This model is a durable attention and audit record. It creates one Odoo activity
for an explicitly configured internal reviewer and one concise chatter note on
the canonical intake. It does not grant authority, emit email, invoke Mack,
invoke Gate/CEG, mutate a CWI, run matching, or create commercial effects.
"""

from __future__ import annotations

import re

import psycopg2.errors
from markupsafe import escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ConcurrencyError, ValidationError

_ROUTE_POLICY_KEY = "mack_workbench_internal_reviewer/v1"
_DELIVERY_MODE = "in_odoo_activity_only"
_INITIAL_STATE = "requested"
# The caller's immutable request material. This is the whole replay identity:
# an existing receipt for (company, idempotency_key) is returned when, and only
# when, every one of these matches what was stored. Routing provenance
# (reviewer, policy key/revision) is resolved by the server for the first
# creation only and is never part of the comparison, so a later routing-config
# change cannot turn a byte-identical retry into a conflict (F190-01).
_CALLER_REQUEST_FIELDS = (
    "intake_id",
    "cwi_ref",
    "cwi_revision",
    "decision_snapshot_hash",
    "candidate_action",
    "reason",
    "risk_codes",
    "evidence_refs",
    "priority",
    "deadline",
    "idempotency_key",
)
# Provenance the server owns outright. A caller supplying any of these is
# denied, not silently overwritten: a request that tries to name its own
# reviewer or policy revision is a forgery attempt, not a typo.
_SERVER_OWNED_PROVENANCE_FIELDS = frozenset(
    {"reviewer_id", "requester_id", "route_policy_key", "route_policy_revision", "activity_id"}
)
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


def _validated_intake_ids(values_list: list[dict]) -> list[int]:
    """Validate create payload targets before performing one batch intake lookup."""
    intake_ids: list[int] = []
    for values in values_list:
        intake_id = values.get("intake_id")
        if not isinstance(intake_id, int) or isinstance(intake_id, bool):
            raise ValidationError(_("Review target intake is required."))
        intake_ids.append(intake_id)
    return intake_ids


class PlasticosMackInternalReview(models.Model):
    """One idempotent request for an internal Odoo review of a canonical intake."""

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
    # No ``check_company=True``: ``plasticos.intake`` carries no company field, and
    # Odoo's ``_check_company`` raises ``ValueError: Invalid field
    # plasticos.intake.company_id`` on every create when the target lacks one
    # (observed at runtime on 8bcc22c). Company scope is the receipt's own
    # ``company_id``, bound server-side to the active company in ``create``.
    intake_id = fields.Many2one(
        "plasticos.intake",
        string="Intake",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
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

    _unique_name = models.Constraint("unique(name)", "Review request reference must be unique.")
    _unique_company_idempotency_key = models.Constraint(
        "unique(company_id, idempotency_key)",
        "An internal review request already exists for this company and idempotency key.",
    )

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
        """Return the receipt for each request: the stored one on replay, else a new one.

        Order matters. The caller's immutable material is extracted and the
        existing receipt looked up *before* any routing policy is consulted, so a
        replay is judged only against what the caller sent the first time.
        Routing (reviewer, policy revision) is resolved once, for a first
        creation, in :meth:`_create_first_receipt`.
        """
        normalized_vals_list = [dict(values) for values in vals_list]
        intake_ids = _validated_intake_ids(normalized_vals_list)
        intakes_by_id = {intake.id: intake for intake in self.env["plasticos.intake"].browse(intake_ids).exists()}
        company = self.env.company
        result = self.browse([])
        for values in normalized_vals_list:
            self._reject_server_owned_provenance(values)
            if values.get("intake_id") not in intakes_by_id:
                raise ValidationError(_("Review target intake does not exist."))
            material = self._caller_request_material(values)
            existing = self._find_receipt(company, material["idempotency_key"])
            if existing:
                existing._assert_idempotent_replay(material)
                result |= existing
                continue
            result |= self._create_first_receipt(company, material)
        return result

    @api.model
    def _reject_server_owned_provenance(self, values):
        """Deny caller-supplied reviewer/policy provenance and cross-company binding."""
        forged = sorted(_SERVER_OWNED_PROVENANCE_FIELDS.intersection(values))
        if forged:
            raise AccessError(
                _("Reviewer and routing provenance are resolved by Odoo routing policy, not the caller (%s).")
                % ", ".join(forged)
            )
        company_id = values.get("company_id")
        if company_id and company_id != self.env.company.id:
            raise AccessError(_("Review requests are bound to the active Odoo company, not a caller-supplied one."))
        for field_name, server_value in (
            ("delivery_mode", _DELIVERY_MODE),
            ("state", _INITIAL_STATE),
            ("name", "New"),
        ):
            if values.get(field_name, server_value) != server_value:
                raise AccessError(_("%s is assigned by Odoo, not the caller.") % field_name)

    @api.model
    def _caller_request_material(self, values):
        """The immutable caller material that identifies one request for replay."""
        material = {field_name: values.get(field_name) for field_name in _CALLER_REQUEST_FIELDS}
        material["deadline"] = fields.Date.to_date(material["deadline"])
        return material

    @api.model
    def _find_receipt(self, company, idempotency_key):
        return self.search(
            [("company_id", "=", company.id), ("idempotency_key", "=", idempotency_key)],
            limit=1,
        )

    @api.model
    def _create_first_receipt(self, company, material):
        """Resolve routing once and insert the receipt, converging on a concurrent winner.

        The insert runs inside a savepoint. When a concurrent request for the same
        (company, idempotency_key) committed first, PostgreSQL raises the unique
        violation here; the savepoint is rolled back and the stored winner is
        re-queried and compared exactly like a sequential replay. Odoo cursors
        are REPEATABLE READ, so a winner that committed *after* this
        transaction's snapshot began is not visible to the re-query; that case
        raises :class:`~odoo.exceptions.ConcurrencyError`, which the RPC layer
        (``odoo.service.model.retrying``) answers by re-running the request on a
        fresh snapshot, where the ordinary replay path returns the winner.
        """
        config = self.env["plasticos.mack.workbench.config"].get_active_config(company=company)
        values = dict(
            material,
            name=self.env["ir.sequence"].next_by_code("plasticos.mack.internal.review") or "New",
            company_id=company.id,
            requester_id=self.env.user.id,
            reviewer_id=config.internal_reviewer_id.id,
            route_policy_key=_ROUTE_POLICY_KEY,
            route_policy_revision=str(config.write_date or config.create_date or config.id),
            delivery_mode=_DELIVERY_MODE,
            state=_INITIAL_STATE,
        )
        intake = self.env["plasticos.intake"].browse(material["intake_id"])
        try:
            with self.env.cr.savepoint():
                # The activity is scheduled first so its id travels in the INSERT:
                # the receipt is never written after creation (immutable from its
                # first byte) and a create-only operator never needs a write ACL for
                # the server's own link. A collision below rolls the activity back
                # with the savepoint.
                values["activity_id"] = self._schedule_in_odoo_activity(intake, values).id
                request = super().create([values])
                request._post_intake_audit_note()
                return request
        except psycopg2.errors.UniqueViolation as exc:
            winner = self._find_receipt(company, material["idempotency_key"])
            if not winner:
                raise ConcurrencyError(
                    "concurrent internal review request for the same idempotency key committed first; "
                    "retry on a fresh snapshot"
                ) from exc
            winner._assert_idempotent_replay(material)
            return winner

    def write(self, values):
        # No exception, no context flag: the activity link is part of the INSERT,
        # and activity completion/deletion reach this row only through the FK's
        # ON DELETE SET NULL inside PostgreSQL, never through the ORM (U190-01).
        raise AccessError(_("Internal review requests are immutable after creation."))

    def unlink(self):
        raise AccessError(_("Internal review requests are retained for audit and cannot be deleted."))

    @api.model
    def _schedule_in_odoo_activity(self, intake, values):
        """Schedule the reviewer's activity on the intake from the receipt's values."""
        return intake.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=values["reviewer_id"],
            summary=_("Mack internal review: %s") % values["name"],
            note=self._activity_note(values),
            date_deadline=values["deadline"],
        )

    def _post_intake_audit_note(self):
        self.ensure_one()
        self.intake_id.message_post(
            body=self._audit_note(),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

    @api.model
    def _activity_note(self, values):
        evidence_refs = _validated_string_list(
            values.get("evidence_refs"),
            field_name="Evidence references",
            maximum=_MAX_EVIDENCE_REFS,
        )
        risk_codes = _validated_string_list(values.get("risk_codes"), field_name="Risk codes", maximum=_MAX_RISK_CODES)
        return "<br/>".join(
            [
                _("Review request: %s") % _safe_note_text(values["name"]),
                _("Candidate action: %s") % _safe_note_text(values.get("candidate_action")),
                _("Reason: %s") % _safe_note_text(values.get("reason")),
                _("Risk codes: %s") % _safe_note_text(", ".join(risk_codes) or _("None")),
                _("Evidence: %s") % _safe_note_text(", ".join(evidence_refs)),
                _("Decision snapshot: %s") % _safe_note_text(values.get("decision_snapshot_hash")),
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

    def _stored_request_material(self):
        """The caller material this receipt was created from, shaped like a request."""
        self.ensure_one()
        stored = {field_name: self[field_name] for field_name in _CALLER_REQUEST_FIELDS}
        stored["intake_id"] = self.intake_id.id
        return stored

    def _assert_idempotent_replay(self, material):
        """Accept only a materially identical retry of one prior review request.

        Only the caller's immutable material is compared. The stored receipt owns
        replay truth: its reviewer and route-policy revision were resolved once
        at first creation and are deliberately not re-derived or re-compared, so
        a routing-config change after the fact leaves an identical retry
        idempotent.
        """
        self.ensure_one()
        stored = self._stored_request_material()
        for field_name in _CALLER_REQUEST_FIELDS:
            if material.get(field_name) != stored[field_name]:
                raise ValidationError(
                    _("Idempotency key is already bound to different review request material (%s).") % field_name
                )
