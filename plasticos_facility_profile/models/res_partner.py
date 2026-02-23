from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    facility_profile_ids = fields.One2many("plasticos.facility.profile", "partner_id", string="Facility Capabilities")

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

    lead_source = fields.Selection(
        selection=[
            ("web_lead", "Web Lead"),
            ("magazine", "Magazine"),
            ("referral", "Referral"),
            ("trade_show", "Trade Show"),
            ("cold_call", "Cold Call"),
            ("existing_customer", "Existing Customer"),
            ("other", "Other"),
        ],
        string="Lead Source",
        tracking=True,
        help="How this counterparty was originally acquired. "
        "Set automatically when partner is created from a web lead.",
    )

    def write(self, vals):
        if "parent_id" in vals and not vals.get("parent_id"):
            for rec in self:
                if rec.facility_profile_ids:
                    raise ValidationError("Cannot convert facility to parent while " "capability profile exists.")
        return super().write(vals)
