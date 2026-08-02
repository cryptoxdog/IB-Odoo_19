"""Facility material rule — accept/reject/prefer/require capability (TASK-025)."""

from __future__ import annotations

import uuid

from odoo import api, fields, models
from odoo.exceptions import UserError


def _get_process_selection(self):
    from odoo.addons.plasticos_material_profile.process_codes import PROCESS_SELECTION

    return PROCESS_SELECTION


class PlasticosFacilityMaterialRule(models.Model):
    _name = "plasticos.facility.material.rule"
    _description = "Facility Material Rule"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"
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
    facility_profile_id = fields.Many2one(
        "plasticos.facility.profile",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
    )
    rule_type = fields.Selection(
        [
            ("accept", "Accept"),
            ("reject", "Reject"),
            ("prefer", "Prefer"),
            ("require", "Require"),
        ],
        required=True,
        index=True,
        tracking=True,
    )
    sequence = fields.Integer(default=10)
    polymer_id = fields.Many2one("plasticos.polymer", ondelete="restrict", index=True)
    form_id = fields.Many2one("plasticos.material.form", ondelete="restrict", index=True)
    source_type_id = fields.Many2one("plasticos.source.type", ondelete="restrict", index=True)
    filler_type_id = fields.Many2one("plasticos.filler.type", ondelete="restrict", index=True)
    equipment_type_id = fields.Many2one("plasticos.equipment.type", ondelete="restrict", index=True)
    process_type = fields.Selection(selection=_get_process_selection)
    application_class = fields.Char()
    mfi_min = fields.Float()
    mfi_max = fields.Float()
    density_min = fields.Float()
    density_max = fields.Float()
    contamination_max_pct = fields.Float()
    moisture_max_pct = fields.Float()
    filler_max_pct = fields.Float()
    food_grade_required = fields.Boolean()
    medical_grade_required = fields.Boolean()
    effective_from = fields.Date()
    effective_to = fields.Date()
    evidence_state = fields.Selection(
        [
            ("operator_confirmed", "Operator Confirmed"),
            ("documented", "Documented"),
            ("inferred", "Inferred"),
            ("unverified", "Unverified"),
            ("stale", "Stale"),
        ],
    )
    confidence = fields.Float()
    source_system = fields.Char()
    source_record_ref = fields.Char()
    migration_batch_id = fields.Char(index=True)
    contract_version = fields.Char(required=True, default="1.0")

    _canonical_uuid_uniq = models.Constraint(
        "unique(canonical_uuid)",
        "canonical_uuid must be unique and immutable.",
    )

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
