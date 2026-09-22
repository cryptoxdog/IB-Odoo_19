"""Immutable broker-approved snapshots for downstream commercial preparation."""

from __future__ import annotations

from odoo import api, fields, models
from odoo.exceptions import UserError

WEB_LEAD_MODEL = "plasticos.web.lead"
INTAKE_MODEL = "plasticos.intake"


class PlasticosWebLeadReviewSnapshot(models.Model):
    """One immutable, versioned broker decision over a specific HOT web lead."""

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("approved_by_id"):
                vals["approved_by_id"] = self.env.user.id
            if not vals.get("approved_at"):
                vals["approved_at"] = fields.Datetime.now()
        return super().create(vals_list)

    def write(self, vals):
        immutable_fields = {
            "web_lead_id",
            "intake_id",
            "revision",
            "approved_by_id",
            "approved_at",
            "snapshot_payload",
            "content_hash",
        }
        if immutable_fields.intersection(vals):
            raise UserError("Broker-approved web-lead snapshots are immutable. Create a new revision instead.")
        return super().write(vals)

    def unlink(self):
        raise UserError("Broker-approved web-lead snapshots are retained for audit and cannot be deleted.")
