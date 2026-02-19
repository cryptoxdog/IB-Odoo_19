from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class PlasticosIntake(models.Model):
    _name = "plasticos.intake"
    _description = "PlasticOS Material Intake"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    # ═════════════════════════════════════════════════════════
    # Identity
    # ═════════════════════════════════════════════════════════

    name = fields.Char(required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        tracking=True,
        index=True,
    )
    facility_id = fields.Many2one(
        "res.partner",
        domain="[('parent_id', '=', partner_id)]",
    )

    # ═════════════════════════════════════════════════════════
    # Material Profile Reference (Unified Schema)
    # ═════════════════════════════════════════════════════════

    material_profile_id = fields.Many2one(
        "plasticos.material.profile",
        string="Material Profile",
        index=True,
        ondelete="set null",
        domain="[('partner_id', '=', facility_id)]",
        help="Link to the canonical material profile. When set, snapshot "
             "fields below auto-populate from the profile.",
    )

    # ═════════════════════════════════════════════════════════
    # Raw Broker Layer
    # ═════════════════════════════════════════════════════════

    material_hint_text = fields.Text(
        help="Raw broker description. Parsed later by L9.",
    )

    # ═════════════════════════════════════════════════════════
    # Material Snapshot (Schema-Aligned)
    # Kept as editable Char/Selection for manual intake and
    # backward compatibility. Can be pre-filled from profile.
    # ═════════════════════════════════════════════════════════

    polymer = fields.Char(required=True, index=True)
    form = fields.Char(required=True, index=True)
    color = fields.Char()
    source_type = fields.Char()
    grade_hint = fields.Char()

    # ═════════════════════════════════════════════════════════
    # Observed Quality (Instance-Level)
    # ═════════════════════════════════════════════════════════

    mfi_value = fields.Float()
    density_value = fields.Float()
    moisture_ppm = fields.Integer()
    contamination_total_pct = fields.Float()
    has_metal = fields.Boolean()
    has_fr = fields.Boolean()
    has_residue = fields.Boolean()
    filler_type = fields.Char()
    filler_pct = fields.Float()
    contamination_notes = fields.Text()

    # ═════════════════════════════════════════════════════════
    # Origin Intelligence
    # ═════════════════════════════════════════════════════════

    origin_application = fields.Char()
    origin_sector = fields.Selection(
        [
            ("medical", "Medical"),
            ("automotive", "Automotive"),
            ("packaging", "Packaging"),
            ("construction", "Construction"),
            ("consumer_goods", "Consumer Goods"),
            ("industrial", "Industrial"),
            ("other", "Other"),
        ],
    )
    origin_process_type = fields.Selection(
        [
            ("injection", "Injection Molding"),
            ("extrusion", "Extrusion"),
            ("blow_mold", "Blow Molding"),
            ("thermoform", "Thermoforming"),
            ("rotomold", "Rotational Molding"),
            ("film_blown", "Film Blown"),
            ("film_cast", "Film Cast"),
            ("compounding", "Compounding"),
            ("other", "Other"),
        ],
    )

    # ═════════════════════════════════════════════════════════
    # Commercial Layer
    # ═════════════════════════════════════════════════════════

    quantity_per_load_lbs = fields.Integer(required=True)
    loads_per_month = fields.Integer()
    deal_type = fields.Selection(
        [
            ("spot", "Spot"),
            ("recurring", "Recurring"),
            ("contract", "Contract"),
            ("trial", "Trial"),
        ],
        default="spot",
    )
    contract_duration_months = fields.Integer()

    # ═════════════════════════════════════════════════════════
    # Onboarding Status
    # ═════════════════════════════════════════════════════════

    onboarding_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("profiled", "Profiled"),
            ("normalized", "Normalized"),
            ("ready", "Ready for Matching"),
        ],
        default="draft",
        tracking=True,
        index=True,
        help="Tracks the intake's progression through the onboarding pipeline.",
    )

    # ═════════════════════════════════════════════════════════
    # Geo
    # ═════════════════════════════════════════════════════════

    lat = fields.Float()
    lon = fields.Float()

    # ═════════════════════════════════════════════════════════
    # Matching
    # ═════════════════════════════════════════════════════════

    match_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("normalized", "Normalized"),
            ("matched", "Matched"),
            ("rejected", "Rejected"),
            ("error", "Error"),
        ],
        default="pending",
        tracking=True,
    )
    match_response = fields.Json()
    normalized = fields.Boolean(
        default=False,
        help="Must be True before adapter emits packet.",
    )
    last_packet_id = fields.Char(index=True)
    last_packet_version = fields.Char()
    last_packet_payload = fields.Json()
    last_packet_ts = fields.Datetime()

    # ═════════════════════════════════════════════════════════
    # Constraints
    # ═════════════════════════════════════════════════════════

    _check_unique_packet = models.Constraint(
        "unique(last_packet_id, last_packet_version)",
        "Duplicate packet emission detected.",
    )

    # ═════════════════════════════════════════════════════════
    # Onchange — pre-fill from material profile
    # ═════════════════════════════════════════════════════════

    @api.onchange("material_profile_id")
    def _onchange_material_profile(self):
        """Pre-fill snapshot fields from the selected material profile."""
        mp = self.material_profile_id
        if not mp:
            return
        self.polymer = mp.polymer_id.code if mp.polymer_id else self.polymer
        self.form = mp.form or self.form
        self.color = mp.color or self.color
        self.source_type = mp.source_type or self.source_type
        self.mfi_value = mp.melt_flow_index or self.mfi_value
        self.density_value = mp.density or self.density_value
        self.contamination_total_pct = (
            mp.contamination_percent or self.contamination_total_pct
        )
        if not self.onboarding_status or self.onboarding_status == "draft":
            self.onboarding_status = "profiled"

    # ═════════════════════════════════════════════════════════
    # Validation
    # ═════════════════════════════════════════════════════════

    @api.constrains("quantity_per_load_lbs")
    def _check_quantity(self):
        for rec in self:
            if rec.quantity_per_load_lbs <= 0:
                raise ValidationError("Quantity per load must be positive.")

    @api.constrains("loads_per_month")
    def _check_loads(self):
        for rec in self:
            if rec.loads_per_month and rec.loads_per_month < 0:
                raise ValidationError("Loads per month cannot be negative.")

    # ═════════════════════════════════════════════════════════
    # Actions
    # ═════════════════════════════════════════════════════════

    def action_mark_normalized(self):
        for rec in self:
            rec.write({
                "normalized": True,
                "match_status": "normalized",
                "onboarding_status": "normalized",
            })

    def action_mark_ready(self):
        """Mark intake as ready for matching after normalization."""
        for rec in self:
            if not rec.normalized:
                raise UserError("Intake must be normalized before marking ready.")
            rec.write({"onboarding_status": "ready"})

    def action_run_buyer_match(self):
        for rec in self:
            if not rec.normalized:
                raise UserError("Intake must be normalized before match.")
            # L9 adapter stub — will be consumed by SDK adapter
            raise UserError(
                "L9 adapter not yet configured. Enable l9_trace module."
            )

    def action_replay_last_packet(self):
        for rec in self:
            if not rec.last_packet_payload:
                raise UserError("No stored packet to replay.")
            # L9 adapter stub
            raise UserError(
                "L9 adapter not yet configured. Enable l9_trace module."
            )
