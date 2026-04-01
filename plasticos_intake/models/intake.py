import logging

from odoo import api, fields, models
from odoo.addons.plasticos_base.models.matching_engine_icp import matching_engine_require_enabled_for_ui
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


def _get_process_selection(self):
    """Lazy load PROCESS_SELECTION from plasticos_material_profile."""
    from odoo.addons.plasticos_material_profile.process_codes import PROCESS_SELECTION

    return PROCESS_SELECTION


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
        "res.partner",
        string="Company",
        required=False,
        tracking=True,
        index=True,
        domain="[('is_company', '=', True)]",
        help="The parent company. Optional for web lead intakes pending review.",
        ondelete="restrict",
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
        "res.partner",
        string="Facility",
        tracking=True,
        index=True,
        domain="['|', ('id', '=', partner_id), ('parent_id', '=', partner_id)]",
        help="The facility (child location) or the company itself when it is also the processing site.",
        ondelete="restrict",
    )
    contact_id = fields.Many2one(
        "res.partner",
        string="Contact Person",
        tracking=True,
        index=True,
        domain="[('is_company', '=', False), '|', ('parent_id', '=', facility_id), ('parent_id', '=', partner_id)]",
        help="The person at the facility you are dealing with. Auto-selected from preferred contact memory.",
        ondelete="restrict",
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
        ondelete="restrict",
    )

    # ═════════════════════════════════════════════════════════
    # Contact Details (auto-pulled, never manually entered)
    # ═════════════════════════════════════════════════════════

    contact_phone = fields.Char(
        related="contact_id.phone",
        string="Contact Phone",
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
        domain="['|', ('partner_id', '=', facility_id), ('partner_id', '=', partner_id)]",
        help="Link to the canonical material profile. When set, snapshot fields below auto-populate from the profile.",
    )

    # ═════════════════════════════════════════════════════════
    # Material Snapshot (Schema-Aligned)
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

    origin_form_id = fields.Many2one(
        "plasticos.material.form",
        string="Origin Form",
        help="What the material was before processing (Drums, Bottles, Film). Optional.",
        ondelete="restrict",
    )

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

    @api.depends("contamination_pct")
    def _compute_has_residue(self):
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
        selection=_get_process_selection,
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
    # Status
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

    lat = fields.Float(string="Latitude")
    lon = fields.Float(string="Longitude")

    # ═════════════════════════════════════════════════════════
    # Material Images (from web lead attachments)
    # ═════════════════════════════════════════════════════════

    image_ids = fields.One2many(
        "ir.attachment",
        "res_id",
        string="Material Images",
        domain=[("res_model", "=", "plasticos.intake"), ("mimetype", "like", "image/")],
        help="Images attached to this intake (uploaded via web lead form or manually).",
    )
    image_count = fields.Integer(
        string="Images",
        compute="_compute_image_count",
    )

    def _compute_image_count(self):
        Attachment = self.env["ir.attachment"]
        for rec in self:
            rec.image_count = Attachment.search_count(
                [
                    ("res_model", "=", "plasticos.intake"),
                    ("res_id", "=", rec.id),
                    ("mimetype", "like", "image/"),
                ]
            )

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
    best_match_score = fields.Float(
        string="Best Match Score",
        compute="_compute_best_match_score",
        store=True,
        help="Highest match score among all buyer matches for this intake.",
    )
    offer_count = fields.Integer(
        string="Offers",
        compute="_compute_offer_count",
        help="Number of offers created from this intake.",
    )

    @api.depends("match_line_ids", "match_line_ids.selected")
    def _compute_match_count(self):
        for rec in self:
            rec.match_count = len(rec.match_line_ids)
            rec.selected_count = len(rec.match_line_ids.filtered("selected"))

    @api.depends("match_line_ids.match_score")
    def _compute_best_match_score(self):
        for rec in self:
            scores = rec.match_line_ids.mapped("match_score")
            rec.best_match_score = max(scores) if scores else 0.0

    def _compute_offer_count(self):
        if "plasticos.offer" not in self.env:
            for rec in self:
                rec.offer_count = 0
            return
        for rec in self:
            rec.offer_count = self.env["plasticos.offer"].search_count([("intake_id", "=", rec.id)])

    @api.depends("name")
    def _compute_display_name(self):
        for rec in self:
            if rec.name and rec.name != "/":
                parts = rec.name.split("-")
                if len(parts) == 3:
                    rec.display_name = f"{parts[0]}-{parts[2]}"
                else:
                    rec.display_name = rec.name
            else:
                rec.display_name = f"INT-{rec.id or 'New'}"

    @api.model_create_multi
    def create(self, vals_list):
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
        for rec in self:
            if rec.partner_id:
                rec.company_display = rec.partner_id.name
            elif rec.pending_company_name:
                rec.company_display = f"⏳ {rec.pending_company_name}"
            else:
                rec.company_display = "Unknown"

    # ═════════════════════════════════════════════════════════
    # Onchange — Smart Cascade
    # ═════════════════════════════════════════════════════════

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        """Auto-select facility when company has exactly one."""
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
            self.facility_id = partner.id
        elif len(children) == 1:
            self.facility_id = children[0].id

    @api.onchange("facility_id")
    def _onchange_facility_id(self):
        """Auto-select contact from preferred memory or single contact."""
        self.contact_id = False
        if not self.facility_id:
            return

        facility = self.facility_id

        preferred = facility.preferred_contact_id
        if preferred and preferred.parent_id.id == facility.id:
            self.contact_id = preferred.id
            return

        if facility.id == self.partner_id.id:
            preferred = facility.preferred_contact_id
            if preferred:
                self.contact_id = preferred.id
                return

        contacts = self.env["res.partner"].search(
            [
                ("parent_id", "=", facility.id),
                ("is_company", "=", False),
                ("type", "in", ["contact", False]),
            ]
        )
        if len(contacts) == 1:
            self.contact_id = contacts[0].id

    # NOTE: _onchange_contact_id and _onchange_lead_source_id removed.
    # Both were empty stubs that caused unnecessary RPC roundtrips from the web
    # client. The actual cross-model syncs are handled in write() below.

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
        if mp.packaging_type_id:
            self.packaging_type_ids = [(4, mp.packaging_type_id.id)]
        self.mfi_value = mp.melt_flow_index or self.mfi_value
        self.density_value = mp.density or self.density_value
        self.contamination_pct = mp.contamination_percent or self.contamination_pct
        if mp.material_attribute_ids:
            self.material_attribute_ids = [(6, 0, mp.material_attribute_ids.ids)]

    # ═════════════════════════════════════════════════════════
    # CRUD Overrides
    # ═════════════════════════════════════════════════════════

    def write(self, vals):
        """Override write to sync cross-model fields on actual save.

        Deferred from @api.onchange to avoid committing changes when
        the user cancels the form.
        """
        res = super().write(vals)
        if "contact_id" in vals or "facility_id" in vals:
            self._sync_preferred_contact()
        if "lead_source_id" in vals or "partner_id" in vals:
            self._sync_lead_source()
        return res

    def _sync_preferred_contact(self):
        """Batch-write preferred_contact_id on facilities when contact changes.

        Collects unique (facility → contact) pairs first to minimise
        the number of sudo().write() SQL UPDATE statements.
        """
        facility_updates = {}
        for record in self:
            if record.contact_id and record.facility_id:
                facility_updates[record.facility_id] = record.contact_id.id

        for facility, contact_id in facility_updates.items():
            if facility.preferred_contact_id.id != contact_id:
                facility.sudo().write({"preferred_contact_id": contact_id})

    def _sync_lead_source(self):
        """Batch-write lead_source_id on partners when first set from intake.

        Collects unique (partner → source) pairs first to minimise
        the number of sudo().write() SQL UPDATE statements.
        """
        partner_updates = {}
        for record in self:
            if record.lead_source_id and record.partner_id and not record.partner_id.lead_source_id:
                partner_updates[record.partner_id] = record.lead_source_id.id

        for partner, source_id in partner_updates.items():
            partner.sudo().write({"lead_source_id": source_id})

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
    # Navigation Actions
    # ═════════════════════════════════════════════════════════

    def action_view_material_profile(self):
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

    def action_view_offers(self):
        self.ensure_one()
        if "plasticos.offer" not in self.env:
            return
        return {
            "type": "ir.actions.act_window",
            "name": f"Offers — {self.name}",
            "res_model": "plasticos.offer",
            "view_mode": "list,form",
            "domain": [("intake_id", "=", self.id)],
            "context": {"default_intake_id": self.id},
        }

    def action_view_matches(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Matches — {self.name}",
            "res_model": "plasticos.intake.match",
            "view_mode": "list,form",
            "domain": [("intake_id", "=", self.id)],
            "context": {"default_intake_id": self.id},
        }

    def action_view_best_match(self):
        self.ensure_one()
        best = self.match_line_ids.sorted("match_score", reverse=True)[:1]
        if best:
            return {
                "type": "ir.actions.act_window",
                "name": f"Best Match — {self.name}",
                "res_model": "plasticos.intake.match",
                "view_mode": "form",
                "res_id": best.id,
            }
        return self.action_view_matches()

    # ═════════════════════════════════════════════════════════
    # Status Transition Actions
    # ═════════════════════════════════════════════════════════

    def _assert_status(self, *allowed):
        self.ensure_one()
        if self.status not in allowed:
            raise UserError(f"Cannot perform this action from status '{self.status}'. Allowed: {', '.join(allowed)}")

    def action_mark_processing(self):
        for rec in self:
            rec._assert_status("offer_sent")
            rec.status = "processing"
            rec.message_post(body="Intake moved to processing.")

    def action_mark_won(self):
        for rec in self:
            rec._assert_status("offer_sent", "processing")
            rec.status = "won"
            rec.message_post(body="Deal closed — PO created.")

    def action_mark_lost(self):
        for rec in self:
            rec.status = "lost"
            rec.message_post(body="Deal marked as lost.")

    def action_mark_expired(self):
        for rec in self:
            rec.status = "expired"
            rec.message_post(body="Intake expired — no activity.")

    # ═════════════════════════════════════════════════════════
    # Actions
    # ═════════════════════════════════════════════════════════

    def action_match_to_buyers(self):
        """Run buyer matching via external microservice."""
        self.ensure_one()

        matching_engine_require_enabled_for_ui(self.env)

        if not self.partner_id and self.pending_company_name:
            self._create_partner_from_pending()

        if not self.partner_id:
            raise UserError(
                "Cannot match buyers without a company.\n\nPlease set a Company or enter a Pending Company Name first."
            )

        if not self.material_profile_id:
            self._create_material_profile_from_intake()

        icp = self.env["ir.config_parameter"].sudo()
        base_url = icp.get_param("plasticos.matching_engine.url", "http://localhost:8001")

        _logger.info(
            "Matching microservice call: intake=%s partner=%s url=%s",
            self.id,
            self.partner_id.id,
            base_url,
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Matching Engine",
                "message": f"Matching request sent for {self.display_name}. Results will appear shortly.",
                "type": "info",
                "sticky": False,
            },
        }

    def _create_material_profile_from_intake(self):
        self.ensure_one()
        MaterialProfile = self.env["plasticos.material.profile"]

        profile_partner = self.facility_id or self.partner_id
        if not profile_partner:
            return

        profile_vals = {
            "partner_id": profile_partner.id,
            "polymer_id": self.polymer_id.id if self.polymer_id else False,
            "form_id": self.form_id.id if self.form_id else False,
            "color_id": self.color_id.id if self.color_id else False,
            "source_type_id": self.source_type_id.id if self.source_type_id else False,
            "origin_form_id": self.origin_form_id.id if self.origin_form_id else False,
            "melt_flow_index": self.mfi_value or 0,
            "density": self.density_value or 0,
            "moisture_percent": self.moisture_pct or 0,
            "contamination_percent": self.contamination_pct or 0,
        }

        if self.material_attribute_ids:
            profile_vals["material_attribute_ids"] = [(6, 0, self.material_attribute_ids.ids)]

        profile = MaterialProfile.create(profile_vals)
        self.write({"material_profile_id": profile.id})

        if hasattr(profile, "copy_images_from"):
            profile.copy_images_from("plasticos.intake", self.id)

        self.message_post(
            body=(
                f"Auto-created material profile: "
                f"{profile.polymer_id.name or 'Unknown'} — "
                f"{profile.partner_id.name} (ID: {profile.id})"
            ),
            message_type="notification",
        )

    def _create_partner_from_pending(self):
        self.ensure_one()
        if not self.pending_company_name:
            return

        Partner = self.env["res.partner"]
        name = self.pending_company_name

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

        partner_vals = {
            "name": name,
            "is_company": True,
            "supplier_rank": 1,
            "comment": f"Created from web lead intake {self.name}",
        }

        if self.lead_source_id:
            partner_vals["lead_source_id"] = self.lead_source_id.id
        else:
            web_lead_source = self.env["utm.source"].search([("name", "=", "Web Lead Form")], limit=1)
            if web_lead_source:
                partner_vals["lead_source_id"] = web_lead_source.id

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
        for rec in self:
            if rec.status == "won":
                raise UserError("Cannot reset a Won intake. Create a new one instead.")
            rec.match_line_ids.unlink()
            rec.status = "draft"
            rec.message_post(body="Reset to draft for editing.")

    def action_send_offers(self):
        """Create plasticos.offer records for each selected match line."""
        self.ensure_one()
        self._assert_status("matched")
        selected = self.match_line_ids.filtered("selected")
        if not selected:
            raise UserError("Please select at least one buyer to send offers to.")

        if not self.partner_id:
            raise UserError("Cannot send offers without a supplier. Set the Company on this intake first.")

        offer_model = "plasticos.offer"
        if offer_model not in self.env:
            raise UserError("Offer module not installed.\n\nInstall 'PlasticOS Offers' to enable offer creation.")

        Offer = self.env[offer_model]
        offers_created = Offer
        for match in selected:
            if not match.buyer_id:
                _logger.warning(
                    "Skipping match line %s — no buyer_id set (buyer_name=%s)",
                    match.id,
                    match.buyer_name,
                )
                continue
            offer = Offer.create(
                {
                    "intake_id": self.id,
                    "supplier_id": self.partner_id.id,
                    "buyer_id": match.buyer_id.id,
                    "price_per_lb": match.typical_price or 0.0,
                    "quantity_lbs": float(self.quantity_per_load_lbs or 0),
                }
            )
            offers_created |= offer

        if not offers_created:
            raise UserError(
                "No offers were created. Ensure selected buyer match lines have a Buyer set.\n\n"
                "Use the bulk assign wizard to assign buyers to unresolved match lines."
            )

        self.status = "offer_sent"
        self.message_post(
            body=(
                f"Offers sent to {len(offers_created)} buyer(s): {', '.join(offers_created.mapped('buyer_id.name'))}"
            ),
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

        return {
            "type": "ir.actions.act_window",
            "name": "Offers Created",
            "res_model": offer_model,
            "view_mode": "list,form",
            "domain": [("intake_id", "=", self.id)],
            "target": "current",
        }

    def action_make_po(self):
        """Create transaction from intake and close as Won."""
        self.ensure_one()
        self._assert_status("offer_sent", "processing", "matched")

        if not self.partner_id:
            raise UserError("Cannot create PO without a supplier partner.")

        if "plasticos.transaction" not in self.env:
            raise UserError(
                "Transaction module not installed.\n\nInstall 'PlasticOS Transactions' to enable PO creation."
            )
        Transaction = self.env["plasticos.transaction"]

        tx_vals = {
            "intake_id": self.id,
            "supplier_id": self.partner_id.id,
            "quantity": self.quantity_per_load_lbs,
        }

        if self.material_profile_id:
            tx_vals["supplier_profile_id"] = self.material_profile_id.id

        selected_match = self.match_line_ids.filtered("selected").sorted("match_score", reverse=True)[:1]
        if selected_match:
            buyer = self.env["res.partner"].search([("name", "=", selected_match.buyer_name)], limit=1)
            if buyer:
                tx_vals["buyer_id"] = buyer.id

        tx = Transaction.create(tx_vals)

        self.status = "won"
        self.message_post(
            body=f"PO created → Transaction "
            f'<a href="#" data-oe-model="plasticos.transaction" '
            f'data-oe-id="{tx.id}">{tx.name or tx.id}</a>'
        )

        return {
            "type": "ir.actions.act_window",
            "name": f"Transaction — {self.name}",
            "res_model": "plasticos.transaction",
            "res_id": tx.id,
            "view_mode": "form",
            "target": "current",
        }
