"""Immutable broker-approved snapshots for downstream commercial preparation."""

from __future__ import annotations

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .evidence_keys import ASSESSMENT_STATUS_ASSESSED, KEY_ECONOMIC_ASSESSMENT, KEY_STATUS
from .review_snapshot import build_snapshot_payload, snapshot_content_hash

WEB_LEAD_MODEL = "plasticos.web.lead"
INTAKE_MODEL = "plasticos.intake"

# The approval action is the only writer of this evidence model. It marks its
# create() call with a module-private object token; JSON-RPC / XML-RPC clients
# can only send strings, numbers, booleans and null in a context, so no remote
# caller can reproduce this token (same mechanism as plasticos_logistics
# freight provenance writes).
_APPROVAL_CONTEXT_KEY = "plasticos_web_leads_broker_approval"
_APPROVAL_TOKEN = object()

_IMMUTABLE_FIELDS = frozenset(
    {
        "web_lead_id",
        "intake_id",
        "revision",
        "approved_by_id",
        "approved_at",
        "snapshot_payload",
        "content_hash",
    }
)


class PlasticosWebLeadReviewSnapshot(models.Model):
    """One immutable, versioned broker decision over a specific HOT web lead.

    Rows are minted only by :meth:`_record_broker_approval`, which derives the
    approver, time, revision, lead/intake binding, payload and content hash on
    the server. Generic ORM/RPC creation is refused for every user, including
    administrators, so a row that looks broker-approved always is.
    """

    _name = "plasticos.web.lead.review.snapshot"
    _description = "Broker-Approved Web Lead Snapshot"
    _inherit = ["mail.thread"]
    _order = "web_lead_id, revision desc"
    _rec_name = "name"

    name = fields.Char(required=True, readonly=True, index=True)
    web_lead_id = fields.Many2one(
        WEB_LEAD_MODEL,
        string="Web Lead",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    intake_id = fields.Many2one(
        INTAKE_MODEL,
        string="Intake",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    revision = fields.Integer(required=True, readonly=True, index=True)
    approved_by_id = fields.Many2one(
        "res.users",
        string="Approved By",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
    )
    approved_at = fields.Datetime(required=True, readonly=True)
    snapshot_payload = fields.Json(required=True, readonly=True)
    content_hash = fields.Char(required=True, readonly=True, index=True)

    _unique_lead_revision = models.Constraint(
        "unique(web_lead_id, revision)",
        "A web lead snapshot revision can only be created once.",
    )

    # ═══════════════════════════════════════════════════════════
    # Server-owned approval path
    # ═══════════════════════════════════════════════════════════

    @api.model
    def _record_broker_approval(self, lead):
        """Mint the next approved snapshot revision for ``lead`` from server-derived facts.

        Every provenance value is computed here from the acting user, the clock,
        and the lead's own records. Caller-supplied approver, time, revision,
        payload, or hash values are impossible by construction.
        """
        lead.ensure_one()
        user = self.env.user
        if user.share or user._is_public():
            raise AccessError("Only internal Odoo users may record a broker approval.")
        # The approver must be allowed to change the lead they are approving.
        lead.check_access("write")
        if lead.decision != "hot" or not lead.intake_id:
            raise UserError("Only a HOT lead with an intake can be approved for commercial preparation.")
        intake = lead.intake_id
        # plasticos.intake.source_lead_id is an integer back-reference to the
        # originating web lead; a mismatch means the intake is not this lead's.
        bound_lead_id = int(getattr(intake, "source_lead_id", 0) or 0)
        if bound_lead_id and bound_lead_id != lead.id:
            raise ValidationError("The intake linked to this lead was created from a different web lead.")
        assessment = (lead.evidence_bundle or {}).get(KEY_ECONOMIC_ASSESSMENT) or {}
        if assessment.get(KEY_STATUS) != ASSESSMENT_STATUS_ASSESSED:
            raise UserError(
                "A completed economic-opportunity assessment is required before broker approval. "
                "Configure the selected economic evaluation provider and re-run triage."
            )

        revision = max(lead.review_snapshot_ids.mapped("revision"), default=0) + 1
        payload = build_snapshot_payload(lead=lead, intake=intake, review_notes=lead.review_notes)
        vals = {
            "name": f"{lead.lead_id} / Broker Snapshot v{revision}",
            "web_lead_id": lead.id,
            "intake_id": intake.id,
            "revision": revision,
            "approved_by_id": user.id,
            "approved_at": fields.Datetime.now(),
            "snapshot_payload": payload,
            "content_hash": snapshot_content_hash(payload),
        }
        # sudo() is justified: the ACL grants no group create on this evidence
        # model, so the checked approval path above is its sole writer
        # (plasticos_logistics freight-evidence pattern). The approver identity
        # was captured from the real user before elevation.
        return self.sudo().with_context(**{_APPROVAL_CONTEXT_KEY: _APPROVAL_TOKEN}).create(vals)

    # ═══════════════════════════════════════════════════════════
    # CRUD guards
    # ═══════════════════════════════════════════════════════════

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get(_APPROVAL_CONTEXT_KEY) is not _APPROVAL_TOKEN:
            raise AccessError(
                "Broker-approved web-lead snapshots are minted only by the lead's broker approval action; "
                "direct creation is not permitted."
            )
        for vals in vals_list:
            payload = vals.get("snapshot_payload")
            if not isinstance(payload, dict) or vals.get("content_hash") != snapshot_content_hash(payload):
                raise ValidationError("Snapshot content hash does not match its payload.")
        return super().create(vals_list)

    def write(self, vals):
        if _IMMUTABLE_FIELDS.intersection(vals):
            raise UserError("Broker-approved web-lead snapshots are immutable. Create a new revision instead.")
        return super().write(vals)

    def unlink(self):
        raise UserError("Broker-approved web-lead snapshots are retained for audit and cannot be deleted.")
