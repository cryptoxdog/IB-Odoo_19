from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

PLASTICOS_MATERIAL_ATTRIBUTE = "plasticos.material.attribute"
PLASTICOS_MATERIAL_PROFILE = "plasticos.material.profile"
PLASTICOS_INTAKE_MATCH = "plasticos.intake.match"
IR_ACT_WINDOW = "ir.actions.act_window"
RES_PARTNER = "res.partner"


class PlasticosIntake(models.Model):
    _name = "plasticos.intake"
    _description = "PlasticOS Material Intake"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    # ═════════════════════════════════════════════════════════
    # Identity
    # ═════════════════════════════════════════════════════════

    name = fields.Char(
        string="Intake Reference",
        required=True,
        copy=False,
        readonly=True,
        default="/",
        index=True,
        help="Sequential reference number (e.g., INT-26-2001).",
    )
    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
        help="Human-readable name: Company - Polymer.",
    )
    partner_id = fields.Many2one(
        RES_PARTNER,
        string="Company",
        required=False,
        tracking=True,
        index=True,
        domain="[('is_company', '=', True)]",
        help="The parent company. Optional for web lead intakes pending review.",
    )
    partner_entity_status = fields.Selection(
        related="partner_id.entity_status",
        string="Entity Status",
        readonly=True,
        help="Operational status of the company (Active/Inactive/Blocked).",
    )
    pending_company_name = fields.Char(
        string="Pending Company",
        help="Company name from web lead, before partner is created. "
        "Cleared when partner_id is set during buyer matching.",
    )
    company_display = fields.Char(
        string="Company Name",
        compute="_compute_company_display",
        help="Shows partner name or pending company name for list views.",
    )
    facility_id = fields.Many2one(
        RES_PARTNER,
        string="Facility",
        tracking=True,
        index=True,
        domain="['|', ('id', '=', partner_id), ('parent_id', '=', partner_id)]",
        help="The facility (child location) or the company itself when it is also the processing site.",
    )
    contact_id = fields.Many2one(
        RES_PARTNER,
        string="Contact Person",
        tracking=True,
        index=True,
        domain="['|', ('parent_id', '=', facility_id), ('parent_id', '=', partner_id)]",
        help="The person at the facility you are dealing with. Auto-selected from preferred contact memory.",
    )

    # ═════════════════════════════════════════════════════════
    # Lead Source Tracking
    # ═════════════════════════════════════════════════════════

    lead_source_id = fields.Many2one(
        "utm.source",
        string="Lead Source",
        tracking=True,
        index=True,
        ondelete="restrict",
        help="How this lead/intake was acquired. Auto-syncs to partner when set.",
    )

    # ── CRM Lead Link (Phase 5) ────────────────────────────────
    crm_lead_id = fields.Many2one(
        "crm.lead",
        string="CRM Lead",
        index=True,
        ondelete="set null",
        help="Link to the CRM lead that created this intake (via Convert to Intake).",
    )
    source_lead_id = fields.Integer(
        string="Source Web Lead ID",
        index=True,
        help="ID of the web lead that created this intake, if any. "
        "Stored as integer to avoid circular dependency with plasticos_web_leads.",
    )

    # ═════════════════════════════════════════════════════════
    # Assignment (for web lead routing)
    # ═════════════════════════════════════════════════════════

    assigned_user_id = fields.Many2one(
        "res.users",
        string="Assign To",
        tracking=True,
        index=True,
        domain="[('share', '=', False)]",
        help="Sales rep assigned to follow up on this intake. Dropdown shows all internal users (non-portal).",
    )

    # ═════════════════════════════════════════════════════════
    # Contact Details (auto-pulled, never manually entered)
    # ═════════════════════════════════════════════════════════

    contact_phone = fields.Char(
        related="contact_id.phone",
        string="Contact Phone",
        readonly=True,
    )
    # Note: 'mobile' field removed in Odoo 19 from res.partner base model
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
        PLASTICOS_MATERIAL_PROFILE,
        string="Material Profile",
        index=True,
        ondelete="set null",
        domain="['|', ('partner_id', '=', facility_id), ('partner_id', '=', partner_id)]",
        help="Link to the canonical material profile. When set, snapshot fields below auto-populate from the profile.",
    )

    # ═════════════════════════════════════════════════════════
    # Material Snapshot (Schema-Aligned)
    # Kept as editable Char/Selection for manual intake and
    # backward compatibility. Can be pre-filled from profile.
    # ═════════════════════════════════════════════════════════

    polymer_id = fields.Many2one(
        "plasticos.polymer",
        string="Polymer",
        required=False,
        index=True,
        ondelete="restrict",
        help="Polymer type from master registry. Optional for web lead intakes pending normalization.",
    )
    form_id = fields.Many2one(
        "plasticos.material.form",
        string="Form",
        required=False,
        index=True,
        ondelete="restrict",
        help="Material form from master registry. Optional for web lead intakes pending normalization.",
    )
    color_id = fields.Many2one(
        "plasticos.material.color",
        string="Color",
        index=True,
        ondelete="restrict",
        help="Material color from master registry.",
    )
    source_type_id = fields.Many2one(
        "plasticos.source.type",
        string="Source Type",
        index=True,
        ondelete="restrict",
        help="Canonical source type from the master registry.",
    )
    grade_hint = fields.Char()

    # ── Origin Form (what it was before processing) ──────────
    origin_form_id = fields.Many2one(
        "plasticos.material.form",
        string="Origin Form",
        help="What the material was before processing (Drums, Bottles, Film). Optional.",
    )

    # ── Packaging ────────────────────────────────────────────
    packaging_type_ids = fields.Many2many(
        "plasticos.packaging.type",
        "plasticos_intake_packaging_rel",
        "intake_id",
        "packaging_type_id",
        string="Packaging",
        help="How the material is packaged/shipped (Gaylords, Super Sacks, Bales). Multi-select.",
    )

    # ═════════════════════════════════════════════════════════
    # Material Attributes (multi-select)
    # ═════════════════════════════════════════════════════════

    material_attribute_ids = fields.Many2many(
        PLASTICOS_MATERIAL_ATTRIBUTE,
        string="Material Attributes",
        help="Condition attributes: Clean, Metalized, With Metal, Printed, etc.",
    )

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
    has_metal = fields.Boolean(
        string="Has Metal",
        help="Contains metal contamination. Synced with 'With Metal'/'No Metal' attributes.",
    )
    is_metalized = fields.Boolean(
        string="Metalized Film",
        help="Film with metallic coating (e.g., chip bags). Synced with 'Metalized' attribute.",
    )
    has_fr = fields.Boolean(string="Flame Retardant")
    # has_residue computed from contamination_pct - hidden from UI, used for buyer matching
    has_residue = fields.Boolean(
        string="Residue Present",
        compute="_compute_has_residue",
        store=True,
        help="Auto-computed: True if contamination_pct > 0.",
    )
    filler_type_id = fields.Many2one(
        "plasticos.filler.type",
        string="Filler Type",
        index=True,
        ondelete="restrict",
        help="Type of filler additive (Glass Filled, Talc Filled, etc.).",
    )
    filler_pct = fields.Float(string="Filler (%)")
    contamination_notes = fields.Text(string="Contamination")
    intake_notes = fields.Text(
        string="Intake Notes",
        help="Freeform notes about this intake. Will be normalized via LLM.",
    )

    # ═════════════════════════════════════════════════════════
    # Computed Quality Fields
    # ═════════════════════════════════════════════════════════

    @api.depends("contamination_pct")
    def _compute_has_residue(self):
        """Auto-compute has_residue from contamination percentage."""
        for rec in self:
            rec.has_residue = rec.contamination_pct > 0

    # ═════════════════════════════════════════════════════════
    # Origin Intelligence
    # ═════════════════════════════════════════════════════════

    origin_application = fields.Text(
        string="Origin Application",
        help="What the material was originally used for (freeform, will be normalized).",
    )
    origin_sector = fields.Selection(
        [
            ("automotive", "Automotive"),
            ("construction", "Construction"),
            ("consumer_goods", "Consumer Goods"),
            ("food", "Food Grade"),
            ("industrial", "Industrial"),
            ("medical", "Medical Grade"),
            ("other", "Other"),
            ("packaging", "Packaging"),
        ],
        string="Sector",
    )
    origin_process_type = fields.Selection(
        [
            ("blow_mold", "Blow Molding"),
            ("compounding", "Compounding"),
            ("extrusion", "Extrusion"),
            ("film_blown", "Film Blown"),
            ("film_cast", "Film Cast"),
            ("injection", "Injection Molding"),
            ("other", "Other"),
            ("rotomold", "Rotational Molding"),
            ("thermoform", "Thermoforming"),
        ],
        string="Process Type",
    )

    # ═════════════════════════════════════════════════════════
    # Frequency (Volume)
    # ═════════════════════════════════════════════════════════

    quantity_per_load_lbs = fields.Integer(
        string="Qty per Load (lbs)",
        required=True,
        default=40000,
    )
    loads_per_month = fields.Integer(string="Loads / Month")
    deal_type = fields.Selection(
        [
            ("spot", "Spot"),
            ("contract", "Contract"),
            ("recurring", "Recurring"),
        ],
        string="Deal Type",
        default="spot",
        help="Spot = one-time. Contract = fixed term. Recurring = ongoing.",
    )
    contract_duration_months = fields.Integer(
        string="Contract Duration (months)",
        help="For contract deals, the expected duration in months.",
    )

    # ═════════════════════════════════════════════════════════
    # Status (simplified 2-stage workflow)
    # ═════════════════════════════════════════════════════════

    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("matched", "Matched"),
            ("offer_sent", "Offer Sent"),
            ("processing", "Processing"),
            ("won", "Closed — Won"),
            ("lost", "Closed — Lost"),
            ("expired", "Expired"),
        ],
        default="draft",
        tracking=True,
        index=True,
        string="Status",
        help="Draft = editing. Matched = buyer matches found. "
        "Offer Sent = offers dispatched. Won = PO created. "
        "Lost = deal lost. Expired = no activity timeout.",
    )

    # ═════════════════════════════════════════════════════════
    # Geo (hidden from UI, used by freight automation)
    # ═════════════════════════════════════════════════════════

    lat = fields.Float(string="Latitude")
    lon = fields.Float(string="Longitude")

    # ═════════════════════════════════════════════════════════
    # Match Results (populated after matching)
    # ═════════════════════════════════════════════════════════

    match_line_ids = fields.One2many(
        PLASTICOS_INTAKE_MATCH,
        "intake_id",
        string="Buyer Matches",
        help="Potential buyers matched to this intake, sorted by match score.",
    )
    match_count = fields.Integer(
        string="Matches Found",
        compute="_compute_match_count",
        store=True,
    )
    selected_count = fields.Integer(
        string="Selected for Offer",
        compute="_compute_match_count",
        store=True,
    )
    best_match_score = fields.Float(
        string="Best Match Score",
        compute="_compute_best_match_score",
        store=True,
        help="Highest match score among all buyer matches for this intake.",
    )

    @api.depends("match_line_ids", "match_line_ids.selected")
    def _compute_match_count(self):
        for rec in self:
            rec.match_count = len(rec.match_line_ids)
            rec.selected_count = len(rec.match_line_ids.filtered("selected"))

    @api.depends("match_line_ids.match_score")
    def _compute_best_match_score(self):
        """Highest match score across all buyer match lines."""
        for rec in self:
            scores = rec.match_line_ids.mapped("match_score")
            rec.best_match_score = max(scores) if scores else 0.0

    # ═════════════════════════════════════════════════════════
    # Computed
    # ═════════════════════════════════════════════════════════

    @api.depends("name")
    def _compute_display_name(self):
        """Display name = prefix-number without year (e.g., INT-26-02001 → INT-02001)."""
        for rec in self:
            if rec.name and rec.name != "/":
                # Remove year portion: INT-26-02001 → INT-02001
                parts = rec.name.split("-")
                if len(parts) == 3:
                    rec.display_name = f"{parts[0]}-{parts[2]}"
                else:
                    rec.display_name = rec.name
            else:
                rec.display_name = f"INT-{rec.id or 'New'}"

    @api.model_create_multi
    def create(self, vals_list):
        """Create intake with auto-generated sequence number."""
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                sequence = self.env["ir.sequence"].next_by_code("plasticos.intake")
                if not sequence:
                    raise UserError(
                        "Unable to generate intake reference number. "
                        "Please ensure the sequence 'plasticos.intake' is configured."
                    )
                vals["name"] = sequence
        return super().create(vals_list)

    @api.depends("partner_id", "pending_company_name")
    def _compute_company_display(self):
        """Show partner name or pending company name for list views."""
        for rec in self:
            if rec.partner_id:
                rec.company_display = rec.partner_id.name
            elif rec.pending_company_name:
                rec.company_display = f"⏳ {rec.pending_company_name}"
            else:
                rec.company_display = "Unknown"

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
        children = self.env[RES_PARTNER].search(
            [
                ("parent_id", "=", partner.id),
                ("is_company", "=", True),
            ]
        )

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
        contacts = self.env[RES_PARTNER].search(
            [
                ("parent_id", "=", facility.id),
                ("is_company", "=", False),
                ("type", "in", ["contact", False]),
            ]
        )
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
                self.facility_id.sudo().write(
                    {
                        "x_preferred_contact_id": self.contact_id.id,
                    }
                )

    @api.onchange("lead_source_id")
    def _onchange_lead_source_id(self):
        """Auto-sync lead source to partner when set on intake.

        If partner doesn't have a lead source yet, copy from intake.
        This tracks how leads/loads came in for reporting.
        """
        if self.lead_source_id and self.partner_id:
            if not self.partner_id.lead_source_id:
                # sudo: update partner from intake (cross-model permission)
                self.partner_id.sudo().write(
                    {
                        "lead_source_id": self.lead_source_id.id,
                    }
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
        self.polymer_id = mp.polymer_id.id if mp.polymer_id else self.polymer_id
        self.form_id = mp.form_id.id if mp.form_id else self.form_id
        self.color_id = mp.color_id.id if mp.color_id else self.color_id
        self.source_type_id = mp.source_type_id.id if mp.source_type_id else self.source_type_id
        self.origin_form_id = mp.origin_form_id.id if mp.origin_form_id else self.origin_form_id
        # Copy packaging types from profile (Many2many)
        if mp.packaging_type_id:
            self.packaging_type_ids = [(4, mp.packaging_type_id.id)]
        self.mfi_value = mp.melt_flow_index or self.mfi_value
        self.density_value = mp.density or self.density_value
        self.contamination_pct = mp.contamination_percent or self.contamination_pct
        # Copy attributes from profile
        if mp.material_attribute_ids:
            self.material_attribute_ids = [(6, 0, mp.material_attribute_ids.ids)]
            self.has_metal = mp.has_metal
            self.is_metalized = mp.is_metalized

    # ═════════════════════════════════════════════════════════
    # Attribute ↔ Boolean Sync
    # ═════════════════════════════════════════════════════════

    @api.onchange("material_attribute_ids")
    def _onchange_material_attributes(self):
        """Sync boolean fields when attributes change."""
        attr_codes = set(self.material_attribute_ids.mapped("code"))
        # Metal contamination: With Metal vs No Metal
        if "with_metal" in attr_codes:
            self.has_metal = True
        elif "no_metal" in attr_codes:
            self.has_metal = False
        # Metalized film coating
        if "metalized" in attr_codes:
            self.is_metalized = True
        else:
            self.is_metalized = False
        # Flame retardant
        if "flame_retardant" in attr_codes:
            self.has_fr = True
        else:
            self.has_fr = False

    @api.onchange("has_metal")
    def _onchange_has_metal(self):
        """Sync attributes when has_metal boolean changes."""
        Attribute = self.env[PLASTICOS_MATERIAL_ATTRIBUTE]
        with_metal = Attribute.search([("code", "=", "with_metal")], limit=1)
        no_metal = Attribute.search([("code", "=", "no_metal")], limit=1)
        if self.has_metal:
            if with_metal and with_metal not in self.material_attribute_ids:
                self.material_attribute_ids = [(4, with_metal.id)]
            if no_metal and no_metal in self.material_attribute_ids:
                self.material_attribute_ids = [(3, no_metal.id)]
        else:
            if no_metal and no_metal not in self.material_attribute_ids:
                self.material_attribute_ids = [(4, no_metal.id)]
            if with_metal and with_metal in self.material_attribute_ids:
                self.material_attribute_ids = [(3, with_metal.id)]

    @api.onchange("is_metalized")
    def _onchange_is_metalized(self):
        """Sync attributes when is_metalized boolean changes."""
        Attribute = self.env[PLASTICOS_MATERIAL_ATTRIBUTE]
        metalized = Attribute.search([("code", "=", "metalized")], limit=1)
        if self.is_metalized:
            if metalized and metalized not in self.material_attribute_ids:
                self.material_attribute_ids = [(4, metalized.id)]
        else:
            if metalized and metalized in self.material_attribute_ids:
                self.material_attribute_ids = [(3, metalized.id)]

    @api.onchange("has_fr")
    def _onchange_has_fr(self):
        """Sync attributes when has_fr boolean changes."""
        Attribute = self.env[PLASTICOS_MATERIAL_ATTRIBUTE]
        flame_retardant = Attribute.search([("code", "=", "flame_retardant")], limit=1)
        if self.has_fr:
            if flame_retardant and flame_retardant not in self.material_attribute_ids:
                self.material_attribute_ids = [(4, flame_retardant.id)]
        else:
            if flame_retardant and flame_retardant in self.material_attribute_ids:
                self.material_attribute_ids = [(3, flame_retardant.id)]

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
    # Navigation Actions (Jump To)
    # ═════════════════════════════════════════════════════════

    def action_view_material_profile(self):
        """Navigate to the linked material profile."""
        self.ensure_one()
        if not self.material_profile_id:
            return
        return {
            "type": IR_ACT_WINDOW,
            "name": "Material Profile",
            "res_model": PLASTICOS_MATERIAL_PROFILE,
            "view_mode": "form",
            "res_id": self.material_profile_id.id,
        }

    def action_view_supplier(self):
        """Navigate to the supplier company."""
        self.ensure_one()
        if not self.partner_id:
            return
        return {
            "type": IR_ACT_WINDOW,
            "name": self.partner_id.name,
            "res_model": RES_PARTNER,
            "view_mode": "form",
            "res_id": self.partner_id.id,
        }

    def action_view_facility(self):
        """Navigate to the facility."""
        self.ensure_one()
        if not self.facility_id:
            return
        return {
            "type": IR_ACT_WINDOW,
            "name": self.facility_id.name,
            "res_model": RES_PARTNER,
            "view_mode": "form",
            "res_id": self.facility_id.id,
        }

    def action_view_matches(self):
        """Navigate to the buyer match lines for this intake."""
        self.ensure_one()
        return {
            "type": IR_ACT_WINDOW,
            "name": f"Matches — {self.name}",
            "res_model": PLASTICOS_INTAKE_MATCH,
            "view_mode": "list,form",
            "domain": [("intake_id", "=", self.id)],
            "context": {"default_intake_id": self.id},
        }

    def action_view_best_match(self):
        """Navigate to the best-scoring buyer match line."""
        self.ensure_one()
        best = self.match_line_ids.sorted("match_score", reverse=True)[:1]
        if best:
            return {
                "type": IR_ACT_WINDOW,
                "name": f"Best Match — {self.name}",
                "res_model": PLASTICOS_INTAKE_MATCH,
                "view_mode": "form",
                "res_id": best.id,
            }
        return self.action_view_matches()

    # ═════════════════════════════════════════════════════════
    # Status Transition Actions (Phase 4)
    # ═════════════════════════════════════════════════════════

    def _assert_status(self, *allowed):
        """Guard: raise if current status not in allowed list."""
        self.ensure_one()
        if self.status not in allowed:
            raise UserError(f"Cannot perform this action from status '{self.status}'. Allowed: {', '.join(allowed)}")

    def action_send_offer(self):
        """Transition matched intake to offer_sent status."""
        for rec in self:
            rec._assert_status("matched")
            rec.status = "offer_sent"
            rec.message_post(body="Offer sent to selected buyer(s).")

    def action_mark_processing(self):
        """Move intake to processing (PO in progress, logistics pending)."""
        for rec in self:
            rec._assert_status("offer_sent")
            rec.status = "processing"
            rec.message_post(body="Intake moved to processing.")

    def action_mark_won(self):
        """Close intake as won — PO has been created."""
        for rec in self:
            rec._assert_status("offer_sent", "processing")
            rec.status = "won"
            rec.message_post(body="Deal closed — PO created.")

    def action_mark_lost(self):
        """Close intake as lost."""
        for rec in self:
            rec.status = "lost"
            rec.message_post(body="Deal marked as lost.")

    def action_mark_expired(self):
        """Close intake as expired — no activity timeout."""
        for rec in self:
            rec.status = "expired"
            rec.message_post(body="Intake expired — no activity.")

    # ═════════════════════════════════════════════════════════
    # Actions
    # ═════════════════════════════════════════════════════════

    def action_match_to_buyers(self):
        """Run buyer matching engine on this intake.

        This base implementation is a stub. Install `plasticos_buyer_match_engine`
        for full 10-gate filtering + Neo4j graph scoring.

        For web lead intakes without a partner, creates the partner first.
        Auto-creates material profile if not set.
        """
        raise UserError(
            "Buyer matching requires the 'PlasticOS Buyer Match Engine' module.\n\n"
            "Install it from Apps → PlasticOS Buyer Match Engine to enable "
            "10-gate filtering and Neo4j graph scoring."
        )

    def _create_material_profile_from_intake(self):
        """Auto-create material profile from intake fields.

        Called by action_match_to_buyers when material_profile_id is not set.
        Creates a new profile linked to the partner/facility with intake's
        material specifications.
        """
        self.ensure_one()
        MaterialProfile = self.env[PLASTICOS_MATERIAL_PROFILE]

        # Determine the partner to link the profile to (facility or company)
        profile_partner = self.facility_id or self.partner_id
        if not profile_partner:
            return

        # Build profile name from polymer + form
        name_parts = []
        if self.polymer_id:
            name_parts.append(self.polymer_id.name)
        if self.form_id:
            name_parts.append(self.form_id.name)
        profile_name = " - ".join(name_parts) if name_parts else f"Profile from {self.name}"

        # Create the material profile
        profile_vals = {
            "name": profile_name,
            "partner_id": profile_partner.id,
            "polymer_id": self.polymer_id.id if self.polymer_id else False,
            "form_id": self.form_id.id if self.form_id else False,
            "color_id": self.color_id.id if self.color_id else False,
            "source_type_id": self.source_type_id.id if self.source_type_id else False,
            "origin_form_id": getattr(self, "origin_form_id", False) and self.origin_form_id.id,
            "melt_flow_index": self.mfi_value or 0,
            "density": self.density_value or 0,
            "contamination_percent": self.contamination_pct or 0,
            "has_metal": self.has_metal,
            "is_metalized": self.is_metalized,
        }

        # Copy material attributes
        if self.material_attribute_ids:
            profile_vals["material_attribute_ids"] = [(6, 0, self.material_attribute_ids.ids)]

        profile = MaterialProfile.create(profile_vals)
        self.write({"material_profile_id": profile.id})
        self.message_post(
            body=f"Auto-created material profile: {profile.name} (ID: {profile.id})",
            message_type="notification",
        )

    def _create_partner_from_pending(self):
        """Create partner from pending_company_name (web lead flow).

        Called when admin decides to buyer-match a web lead intake.
        Creates the partner, links it, and clears pending_company_name.
        """
        self.ensure_one()
        if not self.pending_company_name:
            return

        Partner = self.env[RES_PARTNER]
        name = self.pending_company_name

        # Check if partner already exists (may have been created elsewhere)
        existing = Partner.search([("name", "=ilike", name)], limit=1)
        if existing:
            self.write(
                {
                    "partner_id": existing.id,
                    "pending_company_name": False,
                }
            )
            self.message_post(
                body=f"Linked to existing partner: {existing.name}",
                message_type="notification",
            )
            return

        # Create new partner
        partner_vals = {
            "name": name,
            "is_company": True,
            "supplier_rank": 1,
            "comment": f"Created from web lead intake {self.name}",
        }

        # Copy lead source from intake, or default to web_lead
        if self.lead_source_id:
            partner_vals["lead_source_id"] = self.lead_source_id.id
        else:
            web_lead_source = self.env["utm.source"].search([("name", "=", "Web Lead Form")], limit=1)
            if web_lead_source:
                partner_vals["lead_source_id"] = web_lead_source.id

        # Pull contact info from intake's contact if available
        if self.contact_id:
            if self.contact_id.email:
                partner_vals["email"] = self.contact_id.email
            if self.contact_id.phone:
                partner_vals["phone"] = self.contact_id.phone

        partner = Partner.create(partner_vals)
        self.write(
            {
                "partner_id": partner.id,
                "pending_company_name": False,
            }
        )
        self.message_post(
            body=f"Created new partner: {partner.name} (ID: {partner.id})",
            message_type="notification",
        )

    def action_reset_to_draft(self):
        """Reset intake back to draft for editing."""
        for rec in self:
            if rec.status == "won":
                raise UserError("Cannot reset a Won intake. Create a new one instead.")
            rec.match_line_ids.unlink()
            rec.status = "draft"
            rec.message_post(body="Reset to draft for editing.")

    def action_send_offers(self):
        """Send offers to selected buyers.

        This base implementation is a stub. The `plasticos_offer` module
        should override this to create actual offers.
        """
        self.ensure_one()
        selected = self.match_line_ids.filtered("selected")
        if not selected:
            raise UserError("Please select at least one buyer to send offers to.")

        raise UserError(
            "Offer creation is coming soon.\n\n"
            f"Selected {len(selected)} buyer(s): {', '.join(selected.mapped('buyer_name'))}\n\n"
            "This feature will be available in a future update."
        )

    def action_make_po(self):
        """Create transaction from intake and close as Won.

        This is the one-click PO creation flow:
        1. Validates intake is in offer_sent or processing state
        2. Creates plasticos.transaction from intake data
        3. Moves intake to 'won' status
        4. Opens the new transaction form

        Requires plasticos_transaction module to be installed.
        """
        self.ensure_one()
        self._assert_status("offer_sent", "processing", "matched")

        if not self.partner_id:
            raise UserError("Cannot create PO without a supplier partner.")

        Transaction = self.env.get("plasticos.transaction")
        if Transaction is None:
            raise UserError(
                "Transaction module not installed.\n\nInstall 'PlasticOS Transactions' to enable PO creation."
            )

        # Build transaction values from intake
        tx_vals = {
            "intake_id": self.id,
            "supplier_id": self.partner_id.id,
            "quantity": self.quantity_per_load_lbs,
        }

        # Link to material profile if available
        if self.material_profile_id:
            tx_vals["supplier_profile_id"] = self.material_profile_id.id

        # Link to best buyer match if selected
        selected_match = self.match_line_ids.filtered("selected").sorted("match_score", reverse=True)[:1]
        if selected_match:
            # Try to find buyer partner
            buyer = self.env[RES_PARTNER].search([("name", "=", selected_match.buyer_name)], limit=1)
            if buyer:
                tx_vals["buyer_id"] = buyer.id

        tx = Transaction.create(tx_vals)

        # Move intake to Won
        self.status = "won"
        self.message_post(
            body=f"PO created → Transaction "
            f'<a href="#" data-oe-model="plasticos.transaction" '
            f'data-oe-id="{tx.id}">{tx.name or tx.id}</a>'
        )

        return {
            "type": IR_ACT_WINDOW,
            "name": f"Transaction — {self.name}",
            "res_model": "plasticos.transaction",
            "res_id": tx.id,
            "view_mode": "form",
            "target": "current",
        }
