from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # ── Stored company_type override (enables domain search) ──────────
    company_type = fields.Selection(
        store=True,
        compute="_compute_company_type",
        inverse="_inverse_company_type",
        help="Company type - stored override to enable search domains.",
    )

    @api.depends("is_company")
    def _compute_company_type(self):
        for partner in self:
            partner.company_type = "company" if partner.is_company else "person"

    def _inverse_company_type(self):
        for partner in self:
            partner.is_company = partner.company_type == "company"

    # ── Facility Profile link ─────────────────────────────────────────
    facility_profile_ids = fields.One2many("plasticos.facility.profile", "partner_id", string="Facility Capabilities")
    facility_profile_count = fields.Integer(
        string="Capabilities",
        compute="_compute_facility_profile_count",
    )

    # ═══════════════════════════════════════════════════════════════════
    # PARTNER TYPE — canonical plasticos.partner.type record
    # Single source of truth for facility_role.
    # ═══════════════════════════════════════════════════════════════════
    partner_type_id = fields.Many2one(
        "plasticos.partner.type",
        string="Partner Type",
        help="Canonical partner/facility type from master registry.",
    )

    # ═══════════════════════════════════════════════════════════════════
    # FACILITY ROLE — derived from partner_type_id.code
    # Synced to Neo4j for buyer-match graph traversal.
    # NOT the same as company_type (person/company).
    # ═══════════════════════════════════════════════════════════════════
    facility_role = fields.Selection(
        selection=[
            ("processor", "Processor"),
            ("broker", "Broker"),
            ("manufacturer", "Manufacturer"),
            ("mrf", "MRF"),
            ("compounder", "Compounder"),
            ("recycler", "Recycler"),
            ("distributor", "Distributor"),
            ("carrier", "Carrier"),
            ("other", "Other"),
        ],
        compute="_compute_facility_role",
        inverse="_inverse_facility_role",
        store=True,
        help=(
            "Business role of this facility. Computed from partner_type_id. "
            "NOT the same as company_type (person/company). "
            "Synced to Neo4j as 'facility_role' for buyer matching."
        ),
    )

    @api.depends("partner_type_id", "partner_type_id.code")
    def _compute_facility_role(self):
        for rec in self:
            rec.facility_role = rec.partner_type_id.code if rec.partner_type_id else False

    def _inverse_facility_role(self):
        PartnerType = self.env["plasticos.partner.type"]
        for rec in self:
            if rec.facility_role:
                pt = PartnerType.search([("code", "=", rec.facility_role)], limit=1)
                rec.partner_type_id = pt.id if pt else False
            else:
                rec.partner_type_id = False

    # ═══════════════════════════════════════════════════════════════════
    # COMPANY ROLE — trade-facing classification
    # (Buyer / Supplier / Both / Carrier / Broker / Internal / Prospect)
    # Used in import service, CRM bridge, and partner form UX.
    # NEW FIELD — requires -u plasticos_facility_profile after deploy.
    # ═══════════════════════════════════════════════════════════════════
    company_role = fields.Selection(
        selection=[
            ("buyer", "Buyer"),
            ("supplier", "Supplier"),
            ("both", "Buyer & Supplier"),
            ("carrier", "Carrier"),
            ("broker", "Broker"),
            ("internal", "Internal"),
            ("prospect", "Prospect"),
        ],
        string="Company Role",
        index=True,
        tracking=True,
        help=(
            "Trade-facing role. Drives supplier_rank / customer_rank visibility, "
            "partner form UX, and CEG node classification. "
            "Set during import; can be updated manually on partner record."
        ),
    )

    @api.onchange("company_role")
    def _onchange_company_role(self):
        """Sync supplier_rank / customer_rank when role changes manually."""
        SUPPLIER_ROLES = {"supplier", "both", "broker"}
        CUSTOMER_ROLES = {"buyer", "both"}
        for rec in self:
            if rec.company_role in SUPPLIER_ROLES:
                rec.supplier_rank = max(rec.supplier_rank or 0, 1)
            if rec.company_role in CUSTOMER_ROLES:
                rec.customer_rank = max(rec.customer_rank or 0, 1)

    # ═══════════════════════════════════════════════════════════════════
    # IS_FACILITY — computed gate for Capability Profile tab visibility
    # True:  child company partners (facility locations)
    #        standalone companies with no company children
    # False: top-level parent companies with children; person contacts
    # ═══════════════════════════════════════════════════════════════════
    is_facility = fields.Boolean(
        compute="_compute_is_facility",
        store=True,
        index=True,
        help=(
            "True when this partner is a facility-level entity: "
            "a child company location, or a standalone company with no "
            "child company partners. False for top-level parent companies "
            "that have children, and for person contacts. "
            "Controls Capability Profile tab visibility on partner form."
        ),
    )

    @api.depends("is_company", "parent_id", "child_ids")
    def _compute_is_facility(self):
        for rec in self:
            if not rec.is_company:
                rec.is_facility = False
            elif rec.parent_id:
                rec.is_facility = True
            else:
                has_company_children = any(c.is_company for c in rec.child_ids)
                rec.is_facility = not has_company_children

    # ── Preferred Contact ─────────────────────────────────────────────
    preferred_contact_id = fields.Many2one(
        "res.partner",
        string="Preferred Contact",
        help=(
            "Last-selected contact for this company/facility. "
            "Auto-populated when a user selects a contact on an intake. "
            "Used to auto-fill contact on subsequent intakes."
        ),
    )

    # ── Preferred Supplier Profile (dual-profile support) ────────────
    preferred_supplier_profile_id = fields.Many2one(
        "plasticos.facility.profile",
        string="Preferred Supplier Profile",
        help=(
            "When a supplier has multiple facility profiles, this is the "
            "profile used as source of truth for intake matching. "
            "Set manually by broker or auto-selected on first profile creation."
        ),
    )

    # ── Trade Role — supply vs demand side ────────────────────────────
    plasticos_trade_role = fields.Selection(
        selection=[
            ("supplier", "Supplier"),
            ("buyer", "Buyer"),
            ("both", "Buyer & Supplier"),
            ("other", "Other"),
        ],
        string="Trade Role",
        index=True,
        tracking=True,
        help=(
            "Supply vs demand side classification for buyer-match routing. "
            "Set by import service and enrichment. Used by CEG matching engine."
        ),
    )

    # ── Origin Sector ────────────────────────────────────────────────
    plasticos_origin_sector = fields.Selection(
        selection=[
            ("agriculture", "Agriculture"),
            ("distribution_logistics", "Distribution / Logistics"),
            ("industrial", "Industrial / Manufacturing"),
            ("municipal", "Municipal / MRF"),
            ("commercial", "Commercial"),
            ("other", "Other"),
        ],
        string="Origin Sector",
        index=True,
        help="Sector that generates the material. Auto-set at import for known roles.",
    )

    # ── Lead Source ───────────────────────────────────────────────────
    lead_source_id = fields.Many2one(        "utm.source",
        string="Lead Source",
        tracking=True,
        index=True,
        ondelete="restrict",
        help=(
            "How this counterparty was originally acquired. "
            "Set automatically when partner is created from a web lead or intake."
        ),
    )

    # ── Entity Status ─────────────────────────────────────────────────
    entity_status = fields.Selection(
        selection=[
            ("active", "Active"),
            ("inactive", "Inactive"),
            ("blocked", "Blocked"),
        ],
        string="Entity Status",
        default="active",
        tracking=True,
        help=(
            "Operational status of this entity. "
            "Active = normal operations. "
            "Inactive = temporarily paused. "
            "Blocked = suspended from transactions."
        ),
    )

    # ═══════════════════════════════════════════════════════════════════
    # PERSONAL INTEL
    # ───────────────────────────────────────────────────────────────────
    # Freeform rich-text field for person-level contacts (is_company = False).
    # Deliberately separate from the standard Notes (comment) field, which
    # is used for business context.  Personal Intel captures the human side:
    # personality, communication style, motivators, rapport hooks, family
    # mentions, hobbies, sports teams — anything that makes a broker
    # remember who they're talking to before every call.
    #
    # VISIBILITY: controlled by view (invisible="is_company").
    # SECURITY NOTE: contains sensitive personal context.
    #   - Not exported in standard partner exports.
    #   - Not surfaced in portal or website views.
    #   - Access follows standard res.partner record rules.
    # ═══════════════════════════════════════════════════════════════════
    personal_intel = fields.Html(
        string="Personal Intel",
        sanitize=True,
        sanitize_overridable=False,
        help=(
            "Private broker notes on this contact as a person — "
            "personality, communication style, motivators, family context, "
            "hobbies, rapport hooks. Separate from business Notes. "
            "Visible on person contacts only (not companies or facilities)."
        ),
    )

    # ─────────────────────────────────────────────────────────────────
    @api.depends("facility_profile_ids")
    def _compute_facility_profile_count(self):
        for rec in self:
            rec.facility_profile_count = len(rec.facility_profile_ids)

    def action_view_facility_profiles(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Capabilities — {self.name}",
            "res_model": "plasticos.facility.profile",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }

    def write(self, vals):
        if "parent_id" in vals and not vals.get("parent_id"):
            for rec in self:
                if rec.facility_profile_ids:
                    raise ValidationError("Cannot convert facility to parent while capability profile exists.")
        return super().write(vals)
