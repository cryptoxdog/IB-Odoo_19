"""Material specification — versioned normative requirements (TASK-023)."""

from __future__ import annotations

import uuid

from odoo import api, fields, models
from odoo.exceptions import UserError


class PlasticosMaterialSpecification(models.Model):
    _name = "plasticos.material.specification"
    _description = "Material Specification"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name, version desc, id desc"
    _rec_name = "name"

    name = fields.Char(required=True, index=True, tracking=True)
    canonical_uuid = fields.Char(
        required=True,
        index=True,
        copy=False,
        default=lambda self: str(uuid.uuid4()),
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        ondelete="restrict",
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("superseded", "Superseded"),
            ("archived", "Archived"),
        ],
        required=True,
        default="draft",
        index=True,
        tracking=True,
    )
    version = fields.Integer(required=True, default=1)
    supersedes_id = fields.Many2one(
        "plasticos.material.specification",
        ondelete="restrict",
        index=True,
    )
    legacy_material_profile_id = fields.Many2one(
        "plasticos.material.profile",
        ondelete="set null",
        index=True,
    )
    polymer_id = fields.Many2one(
        "plasticos.polymer",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    form_id = fields.Many2one(
        "plasticos.material.form",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    color_id = fields.Many2one(
        "plasticos.material.color",
        ondelete="restrict",
        index=True,
    )
    source_type_id = fields.Many2one(
        "plasticos.source.type",
        ondelete="restrict",
        index=True,
    )
    filler_type_id = fields.Many2one(
        "plasticos.filler.type",
        ondelete="restrict",
        index=True,
    )
    attribute_ids = fields.Many2many(
        "plasticos.material.attribute",
        "plasticos_material_spec_attribute_rel",
        "specification_id",
        "attribute_id",
        string="Attributes",
    )
    mfi_min = fields.Float()
    mfi_max = fields.Float()
    density_min = fields.Float()
    density_max = fields.Float()
    contamination_max_pct = fields.Float()
    moisture_max_pct = fields.Float()
    filler_min_pct = fields.Float()
    filler_max_pct = fields.Float()
    food_grade_required = fields.Boolean()
    medical_grade_required = fields.Boolean()
    effective_from = fields.Date()
    effective_to = fields.Date()
    notes = fields.Text()
    source_system = fields.Char()
    source_record_ref = fields.Char()
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
