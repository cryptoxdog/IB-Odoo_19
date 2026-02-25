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
        required=False,
        tracking=True,
        index=True,
        domain="[('is_company', '=', True)]",
        help="The parent company. Optional for web lead intakes pending review.",
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
        "res.partner",
        string="Facility",
        tracking=True,
        index=True,
        domain="['|', ('id', '=', partner_id), ('parent_id', '=', partner_id)]",
        help="The facility (child location) or the company itself when it is also the processing site.",
    )
    contact_id = fields.Many2one(
        "res.partner",
        string="Contact Person",
        tracking=True,
        index=True,
        domain="['|', ('parent_id', '=', facility_id), ('parent_id', '=', partner_id)]",
        help="The person at the facility you are dealing with. Auto-selected from preferred contact memory.",
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
        "plasticos.material.profile",
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
        ],
        default="draft",
        tracking=True,
        index=True,
        string="Status",
        help="Draft = editing. Matched = buyer matches found.",
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
        "plasticos.intake.match",
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

    @api.depends("match_line_ids", "match_line_ids.selected")
    def _compute_match_count(self):
        for rec in self:
            rec.match_count = len(rec.match_line_ids)
            rec.selected_count = len(rec.match_line_ids.filtered("selected"))

    # ═════════════════════════════════════════════════════════
    # Computed
    # ═════════════════════════════════════════════════════════

    @api.depends("partner_id", "facility_id", "polymer_id", "pending_company_name")
    def _compute_name(self):
        """Auto-generate display name from company/facility + polymer."""
        for rec in self:
            parts = []
            if rec.facility_id and rec.facility_id != rec.partner_id:
                parts.append(rec.facility_id.name or "")
            elif rec.partner_id:
                parts.append(rec.partner_id.name or "")
            elif rec.pending_company_name:
                parts.append(f"[PENDING] {rec.pending_company_name}")
            if rec.polymer_id:
                parts.append(rec.polymer_id.name.upper())
            if parts:
                rec.name = " - ".join(filter(None, parts))
            else:
                rec.name = f"Intake #{rec.id or 'New'}"

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
    # Navigation Actions (Jump To)
    # ═════════════════════════════════════════════════════════

    def action_view_material_profile(self):
        """Navigate to the linked material profile."""
        self.ensure_one()
        if not self.material_profile_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": "Material Profile",
            "res_model": "plasticos.material.profile",
            "view_mode": "form",
            "res_id": self.material_profile_id.id,
        }

    def action_view_supplier(self):
        """Navigate to the supplier company."""
        self.ensure_one()
        if not self.partner_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": self.partner_id.name,
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.partner_id.id,
        }

    def action_view_facility(self):
        """Navigate to the facility."""
        self.ensure_one()
        if not self.facility_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": self.facility_id.name,
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.facility_id.id,
        }

    # ═════════════════════════════════════════════════════════
    # Actions
    # ═════════════════════════════════════════════════════════

    def action_match_to_buyers(self):
        """Run buyer matching engine on this intake.

        For web lead intakes without a partner, creates the partner first.
        Then calls matching engine, creates match lines sorted by score,
        transitions status to 'matched'.
        """
        for rec in self:
            if rec.status != "draft":
                raise UserError("Only draft intakes can be matched.")

            # Create partner from pending_company_name if not yet created
            if not rec.partner_id and rec.pending_company_name:
                rec._create_partner_from_pending()

            if not rec.partner_id:
                raise UserError(
                    "Cannot match without a company. Please set a company or ensure pending_company_name is filled."
                )

            # Clear any existing matches
            rec.match_line_ids.unlink()

            # TODO: Call buyer matching engine here
            # Engine should return list of dicts:
            # [
            #   {"buyer_id": 123, "match_score": 95.0, "match_reason": "Exact polymer match"},
            #   {"buyer_id": 456, "match_score": 87.5, "match_reason": "Similar form"},
            # ]
            # For now, placeholder - no matches until engine integrated
            matches = []

            # Create match lines from engine results
            for match in matches:
                self.env["plasticos.intake.match"].create(
                    {
                        "intake_id": rec.id,
                        "buyer_id": match.get("buyer_id"),
                        "match_score": match.get("match_score", 0),
                        "match_reason": match.get("match_reason", ""),
                        "typical_price": match.get("typical_price", 0),
                    }
                )

            rec.status = "matched"

    def _create_partner_from_pending(self):
        """Create partner from pending_company_name (web lead flow).

        Called when admin decides to buyer-match a web lead intake.
        Creates the partner, links it, and clears pending_company_name.
        """
        self.ensure_one()
        if not self.pending_company_name:
            return

        Partner = self.env["res.partner"]
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
            "lead_source": "web_lead",
            "comment": f"Created from web lead intake {self.name}",
        }

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
        """Reset this intake back to draft for editing."""
        for rec in self:
            rec.match_line_ids.unlink()
            rec.status = "draft"

    def action_send_offers(self):
        """Send offers to selected buyers.

        Opens offer creation wizard/form for selected match lines.
        """
        self.ensure_one()
        selected = self.match_line_ids.filtered("selected")
        if not selected:
            raise UserError("Please select at least one buyer to send offers to.")

        # TODO: When offer module exists, create offers here
        # For now, placeholder message
        raise UserError(
            f"Offer module not yet installed. "
            f"Would send offers to {len(selected)} buyer(s): "
            f"{', '.join(selected.mapped('buyer_name'))}"
        )
