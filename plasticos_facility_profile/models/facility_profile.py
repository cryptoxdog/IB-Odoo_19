from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PlastosFacilityProfile(models.Model):
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
        tracking=True
    )

    active = fields.Boolean(default=True)

    # Equipment
    has_horizontal_baler = fields.Boolean(index=True)
    has_downstroke_baler = fields.Boolean()
    has_shredder = fields.Boolean()
    has_granulator = fields.Boolean()
    has_wash_line = fields.Boolean(index=True)
    has_pelletizer = fields.Boolean()
    has_extruder = fields.Boolean()
    has_compounder = fields.Boolean()
    has_sorting_line = fields.Boolean()

    # Throughput
    max_monthly_throughput_lbs = fields.Float(index=True)
    avg_truckload_lbs = fields.Float()

    # Material Handling
    handles_bales = fields.Boolean(index=True)
    handles_regrind = fields.Boolean()
    handles_pellet = fields.Boolean()
    handles_flake = fields.Boolean()
    handles_rollstock = fields.Boolean()

    # Quality Processing
    can_remove_metal = fields.Boolean()
    can_reduce_moisture = fields.Boolean()
    can_filter_fr = fields.Boolean()
    can_screen_fines = fields.Boolean()

    # Certification
    iso_certified = fields.Boolean()
    food_grade_certified = fields.Boolean()
    medical_grade_capable = fields.Boolean()

    # Operational Constraints
    min_lot_size_lbs = fields.Float()
    max_lot_size_lbs = fields.Float()
    accepts_spot = fields.Boolean(default=True)
    prefers_contract = fields.Boolean()

    # AI Enrichment
    freeform_notes = fields.Text()

    _check_unique_partner = models.Constraint(
        "unique(partner_id)",
        "Each facility may only have one capability profile.",
    )

    @api.constrains("partner_id")
    def _check_partner_is_facility(self):
        for rec in self:
            if not rec.partner_id.parent_id:
                raise ValidationError("Capability profile can only be attached to facility-level partners.")

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
                ("state", "!=", "cancel")
            ]) > 0:
                raise ValidationError("Cannot delete capability profile linked to active transaction.")
        return super().unlink()

    def _emit_capability_packet(self):
        for rec in self:
            packet = {
                "partner_id": rec.partner_id.id,
                "facility_role": rec.partner_id.x_facility_role,
                "equipment": {
                    "horizontal_baler": rec.has_horizontal_baler,
                    "wash_line": rec.has_wash_line,
                    "shredder": rec.has_shredder,
                    "granulator": rec.has_granulator,
                    "pelletizer": rec.has_pelletizer,
                    "extruder": rec.has_extruder,
                    "compounder": rec.has_compounder,
                    "sorting_line": rec.has_sorting_line,
                },
                "throughput": rec.max_monthly_throughput_lbs,
                "handling": {
                    "bales": rec.handles_bales,
                    "regrind": rec.handles_regrind,
                    "pellet": rec.handles_pellet,
                    "flake": rec.handles_flake,
                },
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
