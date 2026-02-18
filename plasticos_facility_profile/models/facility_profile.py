from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PlasticosFacilityProfile(models.Model):
    _name = "plasticos.facility.profile"
    _description = "Facility Mechanical Capability Profile"
    _inherit = ["mail.thread"]
    _order = "partner_id"

    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
        ondelete="cascade",
        domain="[('parent_id','!=',False)]",
        tracking=True,
    )

    active = fields.Boolean(default=True)

    # ── Relational Equipment (replaces boolean farm) ─────────
    equipment_ids = fields.Many2many(
        "plasticos.equipment.type",
        relation="plasticos_facility_equipment_rel",
        column1="profile_id",
        column2="equipment_type_id",
        string="Equipment & Capabilities",
        domain="[('category', '=', 'equipment')]",
    )
    handling_ids = fields.Many2many(
        "plasticos.equipment.type",
        relation="plasticos_facility_handling_rel",
        column1="profile_id",
        column2="equipment_type_id",
        string="Material Handling",
        domain="[('category', '=', 'handling')]",
    )
    quality_ids = fields.Many2many(
        "plasticos.equipment.type",
        relation="plasticos_facility_quality_rel",
        column1="profile_id",
        column2="equipment_type_id",
        string="Quality Processing",
        domain="[('category', '=', 'quality')]",
    )

    # ── Legacy Boolean Compat (computed from relational) ─────
    # These remain for backward-compatible reads (search, reports,
    # partner-import, _emit_capability_packet). They are stored
    # so existing domain filters continue to work.
    has_horizontal_baler = fields.Boolean(
        compute="_compute_equipment_flags", store=True, index=True,
    )
    has_downstroke_baler = fields.Boolean(
        compute="_compute_equipment_flags", store=True,
    )
    has_shredder = fields.Boolean(
        compute="_compute_equipment_flags", store=True,
    )
    has_granulator = fields.Boolean(
        compute="_compute_equipment_flags", store=True,
    )
    has_wash_line = fields.Boolean(
        compute="_compute_equipment_flags", store=True, index=True,
    )
    has_pelletizer = fields.Boolean(
        compute="_compute_equipment_flags", store=True,
    )
    has_extruder = fields.Boolean(
        compute="_compute_equipment_flags", store=True,
    )
    has_compounder = fields.Boolean(
        compute="_compute_equipment_flags", store=True,
    )
    has_sorting_line = fields.Boolean(
        compute="_compute_equipment_flags", store=True,
    )
    handles_bales = fields.Boolean(
        compute="_compute_handling_flags", store=True, index=True,
    )
    handles_regrind = fields.Boolean(
        compute="_compute_handling_flags", store=True,
    )
    handles_pellet = fields.Boolean(
        compute="_compute_handling_flags", store=True,
    )
    handles_flake = fields.Boolean(
        compute="_compute_handling_flags", store=True,
    )
    handles_rollstock = fields.Boolean(
        compute="_compute_handling_flags", store=True,
    )
    can_remove_metal = fields.Boolean(
        compute="_compute_quality_flags", store=True,
    )
    can_reduce_moisture = fields.Boolean(
        compute="_compute_quality_flags", store=True,
    )
    can_filter_fr = fields.Boolean(
        compute="_compute_quality_flags", store=True,
    )
    can_screen_fines = fields.Boolean(
        compute="_compute_quality_flags", store=True,
    )

    # ── Throughput ───────────────────────────────────────────
    max_monthly_throughput_lbs = fields.Float(index=True)
    avg_truckload_lbs = fields.Float()

    # ── Certification ────────────────────────────────────────
    iso_certified = fields.Boolean()
    food_grade_certified = fields.Boolean()
    medical_grade_capable = fields.Boolean()

    # ── Operational Constraints ──────────────────────────────
    min_lot_size_lbs = fields.Float()
    max_lot_size_lbs = fields.Float()
    accepts_spot = fields.Boolean(default=True)
    prefers_contract = fields.Boolean()

    # ── AI Enrichment ────────────────────────────────────────
    freeform_notes = fields.Text()

    # ── Constraints (Odoo 19 models.Constraint) ──────────────
    _check_unique_partner = models.Constraint(
        "unique(partner_id)",
        "Each facility may only have one capability profile.",
    )

    # ── Computed Flag Methods ────────────────────────────────
    @api.depends("equipment_ids", "equipment_ids.code")
    def _compute_equipment_flags(self):
        _MAP = {
            "horizontal_baler": "has_horizontal_baler",
            "downstroke_baler": "has_downstroke_baler",
            "shredder": "has_shredder",
            "granulator": "has_granulator",
            "wash_line": "has_wash_line",
            "pelletizer": "has_pelletizer",
            "extruder": "has_extruder",
            "compounder": "has_compounder",
            "sorting_line": "has_sorting_line",
        }
        for rec in self:
            codes = set(rec.equipment_ids.mapped("code"))
            for code, field_name in _MAP.items():
                setattr(rec, field_name, code in codes)

    @api.depends("handling_ids", "handling_ids.code")
    def _compute_handling_flags(self):
        _MAP = {
            "bales": "handles_bales",
            "regrind": "handles_regrind",
            "pellet": "handles_pellet",
            "flake": "handles_flake",
            "rollstock": "handles_rollstock",
        }
        for rec in self:
            codes = set(rec.handling_ids.mapped("code"))
            for code, field_name in _MAP.items():
                setattr(rec, field_name, code in codes)

    @api.depends("quality_ids", "quality_ids.code")
    def _compute_quality_flags(self):
        _MAP = {
            "metal_removal": "can_remove_metal",
            "moisture_reduction": "can_reduce_moisture",
            "fr_filtration": "can_filter_fr",
            "fines_screening": "can_screen_fines",
        }
        for rec in self:
            codes = set(rec.quality_ids.mapped("code"))
            for code, field_name in _MAP.items():
                setattr(rec, field_name, code in codes)

    # ── Validation ───────────────────────────────────────────
    @api.constrains("partner_id")
    def _check_partner_is_facility(self):
        for rec in self:
            if not rec.partner_id.parent_id:
                raise ValidationError(
                    "Capability profile can only be attached to facility-level partners."
                )

    # ── CRUD ─────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._emit_capability_packet()
        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._emit_capability_packet()
        return res

    def unlink(self):
        for rec in self:
            if rec.env["sale.order"].search_count([
                ("partner_id", "=", rec.partner_id.id),
                ("state", "!=", "cancel"),
            ]) > 0:
                raise ValidationError(
                    "Cannot delete capability profile linked to active transaction."
                )
        return super().unlink()

    # ── Capability Packet (stub for AI enrichment) ───────────
    def _emit_capability_packet(self):
        for rec in self:
            packet = {
                "partner_id": rec.partner_id.id,
                "facility_role": rec.partner_id.x_facility_role,
                "equipment": list(rec.equipment_ids.mapped("code")),
                "handling": list(rec.handling_ids.mapped("code")),
                "quality": list(rec.quality_ids.mapped("code")),
                "throughput": rec.max_monthly_throughput_lbs,
                "certifications": {
                    "iso": rec.iso_certified,
                    "food": rec.food_grade_certified,
                    "medical": rec.medical_grade_capable,
                },
                "lot_size_range": {
                    "min": rec.min_lot_size_lbs,
                    "max": rec.max_lot_size_lbs,
                },
                "spot": rec.accepts_spot,
                "contract": rec.prefers_contract,
            }
            # Stub only. No external call.
            _ = packet
