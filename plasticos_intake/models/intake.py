from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class PlasticosIntake(models.Model):
    _name = "plasticos.intake"
    _description = "PlasticOS Material Intake"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    # ═════════════════════════════════════════════════════════
    # Identity
    # ═════════════════════════════════════════════════════════

    name = fields.Char(
        compute="_compute_name",
        store=True,
        index=True,
    )
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
        domain="['|'," " ('id', '=', partner_id)," " ('parent_id', '=', partner_id)]",
        help="The facility (child location) or the company itself " "when it is also the processing site.",
    )
    contact_id = fields.Many2one(
        "res.partner",
        string="Contact Person",
        tracking=True,
        index=True,
        domain="['|'," " ('parent_id', '=', facility_id)," " ('parent_id', '=', partner_id)]",
        help="The person at the facility you are dealing with. " "Auto-selected from preferred contact memory.",
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
        help="Sales rep assigned to follow up on this intake. " "Dropdown shows all internal users (non-portal).",
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
        "plasticos.material.profile",
        string="Material Profile",
        index=True,
        ondelete="set null",
        domain="['|'," " ('partner_id', '=', facility_id)," " ('partner_id', '=', partner_id)]",
        help="Link to the canonical material profile. When set, snapshot "
        "fields below auto-populate from the profile.",
    )

    # ═════════════════════════════════════════════════════════
    # Material Snapshot (Schema-Aligned)
    # Kept as editable Char/Selection for manual intake and
    # backward compatibility. Can be pre-filled from profile.
    # ═════════════════════════════════════════════════════════

    polymer_id = fields.Many2one(
        "plasticos.polymer",
        string="Polymer",
        required=True,
        index=True,
        ondelete="restrict",
        help="Polymer type from master registry.",
    )
    form_id = fields.Many2one(
        "plasticos.material.form",
        string="Form",
        required=True,
        index=True,
        ondelete="restrict",
        help="Material form from master registry.",
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
    packaging_type_id = fields.Many2one(
        "plasticos.packaging.type",
        string="Packaging",
        help="How the material is packaged/shipped (Gaylords, Super Sacks, Bales). Optional.",
    )

    # ═════════════════════════════════════════════════════════
    # Material Attributes (multi-select)
    # ═════════════════════════════════════════════════════════

    material_attribute_ids = fields.Many2many(
        "plasticos.material.attribute",
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
    has_residue = fields.Boolean(string="Residue Present")
    filler_type = fields.Char()
    filler_pct = fields.Float(string="Filler (%)")
    contamination_notes = fields.Text()

    # ═════════════════════════════════════════════════════════
    # Origin Intelligence
    # ═════════════════════════════════════════════════════════

    origin_application = fields.Char(
        string="Intended Use",
        help="What the material was originally used for or intended application.",
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
    )
    loads_per_month = fields.Integer(string="Loads / Month")

    # ═════════════════════════════════════════════════════════
    # Status (simplified 2-stage workflow)
    # ═════════════════════════════════════════════════════════

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("matched", "Matched"),
        ],
        default="draft",
        tracking=True,
        index=True,
        string="Status",
        help="Draft = user editing. Matched = submitted and buyer matches found.",
    )

    # ═════════════════════════════════════════════════════════
    # Geo (hidden from UI, used by freight automation)
    # ═════════════════════════════════════════════════════════

    lat = fields.Float(string="Latitude")
    lon = fields.Float(string="Longitude")

    # ═════════════════════════════════════════════════════════
    # Match Results (populated after submission)
    # ═════════════════════════════════════════════════════════

    match_count = fields.Integer(
        string="Matches Found",
        readonly=True,
        help="Number of buyer matches found.",
    )
    match_response = fields.Json(
        string="Match Results",
        readonly=True,
        help="JSON response from matching engine.",
    )

    # ═════════════════════════════════════════════════════════
    # Computed
    # ═════════════════════════════════════════════════════════

    @api.depends("partner_id", "facility_id", "polymer_id")
    def _compute_name(self):
        """Auto-generate display name from company/facility + polymer."""
        for rec in self:
            parts = []
            if rec.facility_id and rec.facility_id != rec.partner_id:
                parts.append(rec.facility_id.name or "")
            elif rec.partner_id:
                parts.append(rec.partner_id.name or "")
            if rec.polymer_id:
                parts.append(rec.polymer_id.name.upper())
            if parts:
                rec.name = " - ".join(filter(None, parts))
            else:
                rec.name = f"Intake #{rec.id or 'New'}"

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
        children = self.env["res.partner"].search(
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
        contacts = self.env["res.partner"].search(
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
        self.packaging_type_id = mp.packaging_type_id.id if mp.packaging_type_id else self.packaging_type_id
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

    @api.onchange("has_metal")
    def _onchange_has_metal(self):
        """Sync attributes when has_metal boolean changes."""
        Attribute = self.env["plasticos.material.attribute"]
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
        Attribute = self.env["plasticos.material.attribute"]
        metalized = Attribute.search([("code", "=", "metalized")], limit=1)
        if self.is_metalized:
            if metalized and metalized not in self.material_attribute_ids:
                self.material_attribute_ids = [(4, metalized.id)]
        else:
            if metalized and metalized in self.material_attribute_ids:
                self.material_attribute_ids = [(3, metalized.id)]

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

    def action_submit(self):
        """Submit intake for buyer matching.

        Single-click action: validates, runs matching engine, updates state.
        """
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft intakes can be submitted.")

            # TODO: Call buyer matching engine here
            # For now, mark as matched with placeholder
            rec.write(
                {
                    "state": "matched",
                    "match_count": 0,
                    "match_response": {"status": "pending_integration"},
                }
            )

    def action_reset_to_draft(self):
        """Reset matched intake back to draft for editing."""
        for rec in self:
            rec.write(
                {
                    "state": "draft",
                    "match_count": 0,
                    "match_response": False,
                }
            )
