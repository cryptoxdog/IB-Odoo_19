from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PlasticosFacilityProfile(models.Model):
    _name = "plasticos.facility.profile"
    _description = "Facility Capability Profile"
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

    # ── Equipment (Boolean flags) ────────────────────────────
    has_horizontal_baler = fields.Boolean(index=True)
    has_downstroke_baler = fields.Boolean()
    has_shredder = fields.Boolean()
    has_granulator = fields.Boolean()
    has_wash_line = fields.Boolean(index=True)
    has_pelletizer = fields.Boolean()
    has_extruder = fields.Boolean()
    has_compounder = fields.Boolean()
    has_sorting_line = fields.Boolean()

    # ── Throughput ───────────────────────────────────────────
    max_monthly_throughput_lbs = fields.Float(index=True)
    avg_truckload_lbs = fields.Float()

    # ── Material Handling ────────────────────────────────────
    handles_bales = fields.Boolean(index=True)
    handles_regrind = fields.Boolean()
    handles_pellet = fields.Boolean()
    handles_flake = fields.Boolean()
    handles_rollstock = fields.Boolean()

    # ── Quality Processing ───────────────────────────────────
    can_remove_metal = fields.Boolean()
    can_reduce_moisture = fields.Boolean()
    can_filter_fr = fields.Boolean()
    can_screen_fines = fields.Boolean()

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

    # ═════════════════════════════════════════════════════════
    # BCP Capability Extension (from Mack v7.0r BCP Schema)
    # ═════════════════════════════════════════════════════════

    # ── Polymer Acceptance ───────────────────────────────────
    accepted_polymer_ids = fields.Many2many(
        "plasticos.polymer",
        "facility_profile_polymer_rel",
        "profile_id",
        "polymer_id",
        string="Accepted Polymers",
        help="Polymer types this facility can process or purchase.",
    )

    # ── Form Preference ──────────────────────────────────────
    form_preference = fields.Selection(
        [
            ("flake", "Flake"),
            ("pellet", "Pellet"),
            ("regrind", "Regrind"),
            ("bale", "Bale"),
            ("film", "Film"),
            ("sheet", "Sheet"),
            ("parts", "Parts"),
            ("powder", "Powder"),
            ("any", "Any"),
        ],
        help="Primary preferred physical form for inbound material.",
    )

    # ── Process Method ───────────────────────────────────────
    process_method = fields.Selection(
        [
            ("injection", "Injection"),
            ("blow", "Blow Molding"),
            ("extrusion", "Extrusion"),
            ("film", "Film"),
            ("sheet", "Sheet"),
            ("reclaim", "Reclaim"),
            ("compounding", "Compounding"),
            ("thermoforming", "Thermoforming"),
            ("unknown", "Unknown"),
        ],
        help="Primary processing method at this facility.",
    )

    # ── Feedstock Type ───────────────────────────────────────
    feedstock_type = fields.Selection(
        [
            ("post_industrial", "Post Industrial"),
            ("post_consumer", "Post Consumer"),
            ("mixed", "Mixed"),
            ("virgin", "Virgin"),
            ("unknown", "Unknown"),
        ],
        help="Primary feedstock classification this facility purchases.",
    )

    # ── Technical Tolerances ─────────────────────────────────
    density_min = fields.Float(
        help="Minimum acceptable density (g/cm³).",
    )
    density_max = fields.Float(
        help="Maximum acceptable density (g/cm³).",
    )
    melt_index_min = fields.Float(
        help="Minimum acceptable melt flow index (g/10min).",
    )
    melt_index_max = fields.Float(
        help="Maximum acceptable melt flow index (g/10min).",
    )
    contamination_tolerance_pct = fields.Float(
        help="Maximum acceptable contamination percentage.",
    )
    moisture_tolerance_pct = fields.Float(
        help="Maximum acceptable moisture percentage.",
    )

    # ── Capacity ─────────────────────────────────────────────
    capacity_lbs_month = fields.Integer(
        string="Capacity (lbs/month)",
        help="Total purchasing or processing capacity in lbs per month.",
    )

    # ── PCR / Blend ──────────────────────────────────────────
    pcr_pct_min = fields.Float(
        help="Minimum post-consumer recycled content percentage required.",
    )
    pcr_pct_max = fields.Float(
        help="Maximum post-consumer recycled content percentage accepted.",
    )

    # ── Application Context ──────────────────────────────────
    application_class = fields.Char(
        help="End-use application class (e.g. packaging, automotive, medical).",
    )
    application_notes = fields.Text(
        help="Additional notes about the facility's end-use applications.",
    )

    # ═════════════════════════════════════════════════════════
    # Constraints
    # ═════════════════════════════════════════════════════════

    _check_unique_partner = models.Constraint(
        "unique(partner_id)",
        "Each facility may only have one capability profile.",
    )

    # ═════════════════════════════════════════════════════════
    # Validation
    # ═════════════════════════════════════════════════════════

    @api.constrains("partner_id")
    def _check_partner_is_facility(self):
        for rec in self:
            if not rec.partner_id.parent_id:
                raise ValidationError(
                    "Capability profile can only be attached to "
                    "facility-level partners."
                )

    @api.constrains("density_min", "density_max")
    def _check_density_range(self):
        for rec in self:
            if rec.density_min and rec.density_max and rec.density_min > rec.density_max:
                raise ValidationError("Density min cannot exceed density max.")

    @api.constrains("melt_index_min", "melt_index_max")
    def _check_mfi_range(self):
        for rec in self:
            if rec.melt_index_min and rec.melt_index_max and rec.melt_index_min > rec.melt_index_max:
                raise ValidationError("Melt index min cannot exceed melt index max.")

    # ═════════════════════════════════════════════════════════
    # CRUD
    # ═════════════════════════════════════════════════════════

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

    # ═════════════════════════════════════════════════════════
    # Capability Packet (stub for L9 adapter)
    # ═════════════════════════════════════════════════════════

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
                # BCP extension fields
                "accepted_polymers": list(
                    rec.accepted_polymer_ids.mapped("code")
                ),
                "form_preference": rec.form_preference,
                "process_method": rec.process_method,
                "feedstock_type": rec.feedstock_type,
                "tolerances": {
                    "density": {"min": rec.density_min, "max": rec.density_max},
                    "mfi": {"min": rec.melt_index_min, "max": rec.melt_index_max},
                    "contamination_pct": rec.contamination_tolerance_pct,
                    "moisture_pct": rec.moisture_tolerance_pct,
                },
                "capacity_lbs_month": rec.capacity_lbs_month,
                "pcr_range": {"min": rec.pcr_pct_min, "max": rec.pcr_pct_max},
                "application_class": rec.application_class,
            }
            # Stub only — L9 adapter will consume this.
            _ = packet
