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
        string="Company",
        required=True,
        tracking=True,
        index=True,
        domain="[('is_company', '=', True)]",
        help="The parent company or standalone company.",
    )
    facility_id = fields.Many2one(
        "res.partner",
        string="Facility",
        tracking=True,
        index=True,
        domain="['|',"
               " ('id', '=', partner_id),"
               " ('parent_id', '=', partner_id)]",
        help="The facility (child location) or the company itself "
             "when it is also the processing site.",
    )
    contact_id = fields.Many2one(
        "res.partner",
        string="Contact Person",
        tracking=True,
        index=True,
        domain="['|',"
               " ('parent_id', '=', facility_id),"
               " ('parent_id', '=', partner_id)]",
        help="The person at the facility you are dealing with. "
             "Auto-selected from preferred contact memory.",
    )

    # ═════════════════════════════════════════════════════════
    # Contact Details (auto-pulled, never manually entered)
    # ═════════════════════════════════════════════════════════

    contact_phone = fields.Char(
        related="contact_id.phone",
        string="Contact Phone",
        readonly=True,
    )
    contact_mobile = fields.Char(
        related="contact_id.mobile",
        string="Contact Mobile",
        readonly=True,
    )
    contact_email = fields.Char(
        related="contact_id.email",
        string="Contact Email",
        readonly=True,
    )
    facility_phone = fields.Char(
        related="facility_id.phone",
        string="Facility Phone",
        readonly=True,
    )
    facility_street = fields.Char(
        related="facility_id.street",
        string="Facility Street",
        readonly=True,
    )
    facility_city = fields.Char(
        related="facility_id.city",
        string="Facility City",
        readonly=True,
    )
    facility_state = fields.Char(
        related="facility_id.state_id.name",
        string="Facility State",
        readonly=True,
    )

    # ═════════════════════════════════════════════════════════
    # Material Profile Reference (Unified Schema)
    # ═════════════════════════════════════════════════════════

    material_profile_id = fields.Many2one(
        "plasticos.material.profile",
        string="Material Profile",
        index=True,
        ondelete="set null",
        domain="['|',"
               " ('partner_id', '=', facility_id),"
               " ('partner_id', '=', partner_id)]",
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

    mfi_value = fields.Float(string="MFI")
    density_value = fields.Float(string="Density (g/cm³)")
    moisture_pct = fields.Float(
        string="Moisture (%)",
        help="Moisture content as a percentage (e.g. 0.5 = 0.5%).",
    )
    contamination_pct = fields.Float(
        string="Contamination (%)",
        help="Total contamination as a percentage.",
    )
    has_metal = fields.Boolean(string="Metal Present")
    has_fr = fields.Boolean(string="Flame Retardant")
    has_residue = fields.Boolean(string="Residue Present")
    filler_type = fields.Char()
    filler_pct = fields.Float(string="Filler (%)")
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
    # Frequency (Volume + Deal Terms)
    # ═════════════════════════════════════════════════════════

    quantity_per_load_lbs = fields.Integer(
        string="Qty per Load (lbs)",
        required=True,
    )
    loads_per_month = fields.Integer(string="Loads / Month")
    deal_type = fields.Selection(
        [
            ("spot", "Spot"),
            ("recurring", "Recurring"),
            ("contract", "Contract"),
            ("trial", "Trial"),
        ],
        default="spot",
    )
    contract_duration_months = fields.Integer(string="Contract Duration (mo)")

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
    # Geo (hidden from UI, used by freight automation)
    # ═════════════════════════════════════════════════════════

    lat = fields.Float(string="Latitude")
    lon = fields.Float(string="Longitude")

    # ═════════════════════════════════════════════════════════
    # Matching / Debug (admin-only in UI)
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
    match_response = fields.Json(string="Match Response (JSON)")
    normalized = fields.Boolean(
        default=False,
        help="Must be True before adapter emits packet.",
    )
    last_packet_id = fields.Char(string="Packet ID", index=True)
    last_packet_version = fields.Char(string="Packet Version")
    last_packet_payload = fields.Json(string="Packet Payload (JSON)")
    last_packet_ts = fields.Datetime(string="Packet Timestamp")

    # ═════════════════════════════════════════════════════════
    # Constraints
    # ═════════════════════════════════════════════════════════

    _check_unique_packet = models.Constraint(
        "unique(last_packet_id, last_packet_version)",
        "Duplicate packet emission detected.",
    )

    # ═════════════════════════════════════════════════════════
    # Onchange — Smart Cascade
    # partner_id → facility_id → contact_id → details
    # ═════════════════════════════════════════════════════════

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        """Auto-select facility when company has exactly one.

        Also handles the flagship case: if the company itself is a
        processing facility (has facility_profile_ids), default to it.
        Clears downstream fields when company changes.
        """
        self.facility_id = False
        self.contact_id = False
        self.material_profile_id = False
        if not self.partner_id:
            return

        partner = self.partner_id
        children = self.env["res.partner"].search([
            ("parent_id", "=", partner.id),
            ("is_company", "=", True),
        ])

        if not children:
            # Company IS the facility (standalone or flagship)
            self.facility_id = partner.id
        elif len(children) == 1:
            # Single facility — auto-select
            self.facility_id = children[0].id
        # else: multiple facilities — user must pick

    @api.onchange("facility_id")
    def _onchange_facility_id(self):
        """Auto-select contact from preferred memory or single contact.

        Checks x_preferred_contact_id on the facility first. If not set,
        auto-selects when there is exactly one contact. Clears contact
        when facility changes.
        """
        self.contact_id = False
        if not self.facility_id:
            return

        facility = self.facility_id

        # Check preferred contact memory
        preferred = facility.x_preferred_contact_id
        if preferred and preferred.parent_id.id == facility.id:
            self.contact_id = preferred.id
            return

        # Also check parent-level preferred if facility == partner
        if facility.id == self.partner_id.id:
            preferred = facility.x_preferred_contact_id
            if preferred:
                self.contact_id = preferred.id
                return

        # Auto-select if single contact
        contacts = self.env["res.partner"].search([
            ("parent_id", "=", facility.id),
            ("is_company", "=", False),
            ("type", "in", ["contact", False]),
        ])
        if len(contacts) == 1:
            self.contact_id = contacts[0].id

    @api.onchange("contact_id")
    def _onchange_contact_id(self):
        """Save contact selection to preferred memory on the facility.

        Next time this facility is selected on any intake, the system
        will auto-select this contact. No double-entry ever.
        """
        if self.contact_id and self.facility_id:
            # Write preferred contact memory (sudo to bypass ACL)
            if self.facility_id.x_preferred_contact_id != self.contact_id:
                self.facility_id.sudo().write({
                    "x_preferred_contact_id": self.contact_id.id,
                })

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
        self.form = mp.form_id.code if mp.form_id else self.form
        self.color = mp.color_id.code if mp.color_id else self.color
        self.source_type = mp.source_type_id.code if mp.source_type_id else self.source_type
        self.mfi_value = mp.melt_flow_index or self.mfi_value
        self.density_value = mp.density or self.density_value
        self.contamination_pct = (
            mp.contamination_percent or self.contamination_pct
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
