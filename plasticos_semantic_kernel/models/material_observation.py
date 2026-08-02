"""Material observation — attributed measured/reported/inferred values (TASK-023)."""

from __future__ import annotations

import uuid

from odoo import api, fields, models
from odoo.exceptions import UserError


class PlasticosMaterialObservation(models.Model):
    _name = "plasticos.material.observation"
    _description = "Material Observation"
    _order = "observed_at desc, id desc"
    _rec_name = "feature_id"

    canonical_uuid = fields.Char(
        required=True,
        index=True,
        copy=False,
        default=lambda self: str(uuid.uuid4()),
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        ondelete="restrict",
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)
    material_profile_id = fields.Many2one(
        "plasticos.material.profile",
        required=True,
        index=True,
        ondelete="cascade",
    )
    specification_id = fields.Many2one(
        "plasticos.material.specification",
        ondelete="set null",
        index=True,
    )
    feature_id = fields.Char(required=True, index=True)
    value_state = fields.Selection(
        [
            ("observed", "Observed"),
            ("reported", "Reported"),
            ("inferred", "Inferred"),
            ("unknown", "Unknown"),
            ("not_applicable", "Not Applicable"),
            ("stale", "Stale"),
            ("conflicting", "Conflicting"),
            ("superseded", "Superseded"),
        ],
        required=True,
        index=True,
    )
    value_numeric = fields.Float()
    value_text = fields.Text()
    value_boolean = fields.Boolean()
    value_json = fields.Json()
    unit_code = fields.Char()
    method = fields.Char(required=True)
    confidence = fields.Float()
    observed_at = fields.Datetime(required=True, index=True)
    valid_until = fields.Datetime(index=True)
    source_system = fields.Char(required=True)
    source_record_ref = fields.Char()
    inference_rule_version = fields.Char()
    model_version = fields.Char()
    supersedes_id = fields.Many2one(
        "plasticos.material.observation",
        ondelete="restrict",
        index=True,
    )
    conflict_group = fields.Char(index=True)
    evidence_attachment_ids = fields.Many2many(
        "ir.attachment",
        "plasticos_material_obs_attachment_rel",
        "observation_id",
        "attachment_id",
        string="Evidence Attachments",
    )
    migration_batch_id = fields.Char(index=True)
    contract_version = fields.Char(required=True, default="1.0")

    _sql_constraints = [
        (
            "canonical_uuid_uniq",
            "unique(canonical_uuid)",
            "canonical_uuid must be unique and immutable.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("canonical_uuid"):
                vals["canonical_uuid"] = str(uuid.uuid4())
        return super().create(vals_list)

    def write(self, vals):
        if "canonical_uuid" in vals:
            raise UserError("canonical_uuid is immutable once issued.")
        return super().write(vals)
