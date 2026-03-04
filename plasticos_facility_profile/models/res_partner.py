from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Override company_type to be stored (Odoo core has it as computed/non-stored)
    # This allows searching by company_type in domains
    company_type = fields.Selection(
        selection=[("company", "Company"), ("person", "Individual")],
        string="Company Type",
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

    facility_profile_ids = fields.One2many("plasticos.facility.profile", "partner_id", string="Facility Capabilities")

    facility_profile_count = fields.Integer(
        string="Capabilities",
        compute="_compute_facility_profile_count",
    )

    partner_type_id = fields.Many2one(
        "plasticos.partner.type",
        string="Partner Type",
        help="Canonical partner/facility type from master registry.",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # IMPORTANT: x_facility_role vs company_type
    # ───────────────────────────────────────────────────────────────────────
    # company_type (Odoo core) = "person" or "company" (legal entity type)
    # x_facility_role (below) = BUSINESS ROLE (broker, processor, mrf, etc.)
    #
    # This field is synced to Neo4j as "facility_role" and used in Cypher
    # to exclude brokers from equipment gates (they resell, not process).
    # ═══════════════════════════════════════════════════════════════════════
    x_facility_role = fields.Selection(
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
        compute="_compute_x_facility_role",
        inverse="_inverse_x_facility_role",
        store=True,
        help="Business role of this facility. Computed from partner_type_id. "
        "NOT the same as company_type (person/company). "
        "Synced to Neo4j as 'facility_role' for buyer matching.",
    )

    @api.depends("partner_type_id", "partner_type_id.code")
    def _compute_x_facility_role(self):
        for rec in self:
            rec.x_facility_role = rec.partner_type_id.code if rec.partner_type_id else False

    def _inverse_x_facility_role(self):
        PartnerType = self.env["plasticos.partner.type"]
        for rec in self:
            if rec.x_facility_role:
                partner_type = PartnerType.search([("code", "=", rec.x_facility_role)], limit=1)
                rec.partner_type_id = partner_type.id if partner_type else False
            else:
                rec.partner_type_id = False

    x_preferred_contact_id = fields.Many2one(
        "res.partner",
        string="Preferred Contact",
        help="Last-selected contact for this company/facility. "
        "Auto-populated when a user selects a contact on an intake. "
        "Used to auto-fill contact on subsequent intakes.",
    )

    lead_source_id = fields.Many2one(
        "plasticos.lead.source",
        string="Lead Source",
        tracking=True,
        index=True,
        ondelete="restrict",
        help="How this counterparty was originally acquired. "
        "Set automatically when partner is created from a web lead or intake.",
    )

    entity_status = fields.Selection(
        selection=[
            ("active", "Active"),
            ("inactive", "Inactive"),
            ("blocked", "Blocked"),
        ],
        string="Entity Status",
        default="active",
        tracking=True,
        help="Operational status of this entity. "
        "Active = normal operations. "
        "Inactive = temporarily paused. "
        "Blocked = suspended from transactions.",
    )

    def _compute_facility_profile_count(self):
        """Count facility profiles linked to this partner."""
        for rec in self:
            rec.facility_profile_count = len(rec.facility_profile_ids)

    def action_view_facility_profiles(self):
        """Navigate to facility profiles for this partner."""
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
