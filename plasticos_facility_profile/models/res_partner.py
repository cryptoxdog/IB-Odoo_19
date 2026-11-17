import base64

from odoo import api, fields, models, tools
from odoo.exceptions import UserError, ValidationError

from ..address_meaning import address_type_meaning, contact_type, contact_type_inverse, is_site, site_domain

# Commercial documents that keep a closed location in history instead of a delete.
_LOCATION_REFERENCE_MODELS = (
    ("sale.order", ("partner_id", "partner_invoice_id", "partner_shipping_id")),
    ("purchase.order", ("partner_id",)),
    ("account.move", ("partner_id",)),
    ("stock.picking", ("partner_id",)),
    ("crm.lead", ("partner_id",)),
    ("plasticos.intake", ("partner_id", "facility_id")),
    ("plasticos.opportunity.approval", ("partner_id",)),
)


class ResPartner(models.Model):
    _inherit = "res.partner"

    # ── Stored company_type override (enables domain search) ──────────
    # Site is the third Contact type (ADR-131): an address of a company, in
    # either shape (native delivery/invoice address, or a company parented
    # under a company). No new column; the stored company_type carries it.
    company_type = fields.Selection(
        selection_add=[("site", "Site")],
        ondelete={"site": lambda partners: partners._plasticos_drop_site_company_type()},
        store=True,
        compute="_compute_company_type",
        inverse="_inverse_company_type",
        help="Company, Person, or Site (an address of a company). Stored to enable search domains.",
    )

    def _plasticos_is_site(self):
        """True when this partner is a site of a company (either shape)."""
        self.ensure_one()
        return is_site(has_parent=bool(self.parent_id), partner_type=self.type, is_company=self.is_company)

    @api.model
    def _plasticos_site_domain(self):
        """Search domain equal to ``_plasticos_is_site``."""
        return site_domain()

    def _plasticos_drop_site_company_type(self):
        """Uninstall: fall back to the two base values."""
        for partner in self:
            partner.company_type = "company" if partner.is_company else "person"

    @api.depends("is_company", "parent_id", "type")
    def _compute_company_type(self):
        for partner in self:
            partner.company_type = contact_type(
                has_parent=bool(partner.parent_id), partner_type=partner.type, is_company=partner.is_company
            )

    def _inverse_company_type(self):
        for partner in self:
            is_company, partner_type = contact_type_inverse(partner.company_type, partner.type)
            partner.is_company = is_company
            if partner_type != partner.type:
                partner.type = partner_type

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
        ondelete="restrict",
    )

    # ═══════════════════════════════════════════════════════════════════
    # FACILITY ROLE — granular specialization within the broad partner type
    # Set via enrichment or manual entry. NOT derived from partner_type_id.
    # Synced to Neo4j for buyer-match graph traversal.
    # ═══════════════════════════════════════════════════════════════════
    facility_role = fields.Selection(
        selection=[
            ("commercial_recycler", "Commercial Recycler"),
            ("pallet_recycler", "Pallet Recycler"),
            ("ag_recycler", "Ag Recycler"),
            ("ewaste", "E-Waste"),
            ("drum_reconditioner", "Drum Reconditioner"),
            ("thrift_store", "Thrift Store"),
            ("molder", "Molder"),
            ("extruder", "Extruder"),
            ("thermoformer", "Thermoformer"),
            ("film_producer", "Film Producer"),
            ("regrinder", "Regrinder"),
            ("pelletizer", "Pelletizer"),
            ("compounder", "Compounder"),
            ("warehouse", "Warehouse"),
            ("other", "Other"),
        ],
        string="Facility Role",
        store=True,
        index=True,
        help=(
            "Specific facility specialization within the broad partner type. "
            "Set via enrichment or manual entry. NOT derived from partner_type_id. "
            "Synced to Neo4j for buyer matching."
        ),
    )

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
            ("carrier", "Carrier"),
            ("broker", "Broker"),
            ("internal", "Internal"),
            ("prospect", "Prospect"),
            ("other", "Other"),
        ],
        string="Company Role",
        index=True,
        tracking=True,
        help=(
            "Trade-facing role. Drives supplier_rank / customer_rank visibility, "
            "partner form UX, and CEG node classification. "
            "Set during import; can be updated manually on partner record. "
            "A company that is both a buyer and a supplier keeps that on "
            "Company Roles instead of this badge."
        ),
    )
    company_role_tag_ids = fields.Many2many(
        "plasticos.company.role.tag",
        "plasticos_partner_company_role_tag_rel",
        "partner_id",
        "tag_id",
        string="Company Roles",
        help="Trade roles from the ERP letter. A company can carry more than one.",
    )

    _SUPPLIER_ROLES = {"supplier", "broker"}
    _CUSTOMER_ROLES = {"buyer"}

    def _sync_rank_from_role(self):
        """Ensure supplier_rank / customer_rank reflect company_role."""
        for rec in self:
            if rec.company_role in self._SUPPLIER_ROLES:
                if not rec.supplier_rank:
                    rec.supplier_rank = 1
            if rec.company_role in self._CUSTOMER_ROLES:
                if not rec.customer_rank:
                    rec.customer_rank = 1

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

    @api.depends("is_company", "parent_id", "type", "child_ids", "child_ids.is_company", "child_ids.type")
    def _compute_is_facility(self):
        for rec in self:
            if rec._plasticos_is_site():
                rec.is_facility = True
            elif not rec.is_company:
                rec.is_facility = False
            else:
                has_sites = any(child._plasticos_is_site() for child in rec.child_ids)
                rec.is_facility = not has_sites

    # ── Preferred Contact ─────────────────────────────────────────────
    preferred_contact_id = fields.Many2one(
        "res.partner",
        string="Preferred Contact",
        help=(
            "Last-selected contact for this company/facility. "
            "Auto-populated when a user selects a contact on an intake. "
            "Used to auto-fill contact on subsequent intakes."
        ),
        ondelete="restrict",
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
        ondelete="restrict",
    )

    # ── Trade Role — supply vs demand side ────────────────────────────
    plasticos_trade_role = fields.Selection(
        selection=[
            ("supplier", "Supplier"),
            ("buyer", "Buyer"),
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
    lead_source_id = fields.Many2one(
        "utm.source",
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

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered("company_role")._sync_rank_from_role()
        return records

    erp_address_label = fields.Char(
        string="Source Address Label",
        help="ERP Address.Type. Tells a pickup from a ship-to on a broker or a carrier.",
    )
    phone_line_ids = fields.One2many(
        "plasticos.partner.phone",
        "partner_id",
        string="Other Phones",
        help="Extra numbers kept for import. Phone and Mobile are the fields on the form.",
    )
    # Odoo 19 base has no res.partner.mobile column (phone only); this field is
    # new here and projects the "mobile" phone line, so no stored value exists
    # to migrate. The search method keeps it usable in domains and filters.
    mobile = fields.Char(
        string="Mobile",
        compute="_compute_mobile",
        inverse="_inverse_mobile",
        search="_search_mobile",
        help="Mobile number. Stored with the partner's other phone lines.",
    )
    contact_header_name = fields.Char(
        string="Contact Names",
        compute="_compute_contact_header_name",
        help="People at this company, or the people linked to this location.",
    )
    first_name = fields.Char(
        string="First Name",
        compute="_compute_name_parts",
        store=True,
        help="First word of a person's name. Blank on a company or a location.",
    )
    last_name = fields.Char(
        string="Last Name",
        compute="_compute_name_parts",
        store=True,
        help="Last word of a person's name. Blank on a company, a location, or a one-word name.",
    )
    linked_person_email = fields.Char(
        string="Linked Person Email",
        compute="_compute_linked_person_channels",
        help="A location's own email, or the email of the first linked person when the location has none.",
    )
    linked_person_mobile = fields.Char(
        string="Linked Person Mobile",
        compute="_compute_linked_person_channels",
        help="A location's own mobile, or the mobile of the first linked person when the location has none.",
    )
    location_child_ids = fields.Many2many(
        "res.partner",
        compute="_compute_location_child_ids",
        string="Locations",
        help="Child locations of this company.",
    )
    location_partner_ids = fields.Many2many(
        "res.partner",
        "plasticos_partner_location_rel",
        "person_id",
        "location_id",
        string="Sites",
        help="Locations this person works at.",
    )
    site_person_ids = fields.Many2many(
        "res.partner",
        "plasticos_partner_location_rel",
        "location_id",
        "person_id",
        string="People",
        help="People linked to this location.",
    )
    address_type_meaning = fields.Char(
        string="Address Meaning",
        compute="_compute_address_type_meaning",
        help="What Address Type means for this company.",
    )

    @api.depends(
        "type",
        "is_company",
        "parent_id",
        "company_role",
        "erp_address_label",
        "commercial_partner_id.customer_rank",
        "commercial_partner_id.supplier_rank",
        "parent_id.commercial_partner_id.customer_rank",
        "parent_id.commercial_partner_id.supplier_rank",
    )
    def _compute_address_type_meaning(self):
        for partner in self:
            site = partner._plasticos_is_site()
            # The site's company: the parent's commercial entity (a site with
            # is_company is its own commercial partner in standard Odoo).
            company = partner.parent_id.commercial_partner_id if site else partner.commercial_partner_id
            partner.address_type_meaning = address_type_meaning(
                partner.type,
                is_company=partner.is_company,
                company_role=partner.company_role,
                source_label=partner.erp_address_label,
                site=site,
                buyer_and_supplier=bool(company.customer_rank > 0 and company.supplier_rank > 0),
            )

    @api.depends("name", "is_company", "parent_id", "type")
    def _compute_name_parts(self):
        for partner in self:
            not_a_person = partner.is_company or partner._plasticos_is_site()
            words = [] if not_a_person or not partner.name else partner.name.split()
            partner.first_name = words[0] if words else False
            partner.last_name = words[-1] if len(words) > 1 else False

    @api.depends(
        "is_company",
        "parent_id",
        "type",
        "email",
        "mobile",
        "site_person_ids.email",
        "site_person_ids.mobile",
    )
    def _compute_linked_person_channels(self):
        for partner in self:
            email = False
            mobile = False
            if partner._plasticos_is_site():
                person_email = partner.site_person_ids.filtered("email")[:1]
                person_mobile = partner.site_person_ids.filtered("mobile")[:1]
                email = partner.email or (person_email.email if person_email else False)
                mobile = partner.mobile or (person_mobile.mobile if person_mobile else False)
            partner.linked_person_email = email
            partner.linked_person_mobile = mobile

    def _plasticos_child_contacts(self):
        """People parented here, excluding locations and non-contact addresses."""
        self.ensure_one()
        return self.child_ids.filtered(lambda child: not child.is_company and child.type in ("contact", False))

    def _plasticos_reach_candidates(self):
        """People who may be reached for this partner. Empty means do not guess.

        A location uses its People list. With nobody linked, one child contact
        is that child, and several child contacts are left for the broker.
        No child contact falls back to the parent company's people. A company
        with no parent is chosen only when it has exactly one child contact.
        """
        self.ensure_one()
        if self._plasticos_is_site():
            if self.site_person_ids:
                return self.site_person_ids
            children = self._plasticos_child_contacts()
            if len(children) == 1:
                return children
            if children:
                return self.browse()
            return self.parent_id._plasticos_child_contacts()
        if not self.is_company:
            return self
        children = self._plasticos_child_contacts()
        if len(children) == 1:
            return children
        return self.browse()

    def _plasticos_reach_person(self):
        """The person whose name and email follow this partner onto a lead and an intake.

        ``preferred_contact_id`` wins only when it is already one of the candidates.
        Otherwise the first candidate with an email wins, matching the location
        header. A linked person with no email is still returned: the parent is
        not used while anyone is linked.
        """
        self.ensure_one()
        candidates = self._plasticos_reach_candidates()
        if not candidates:
            return self.browse()
        preferred = self.preferred_contact_id
        if preferred and preferred in candidates:
            return preferred
        return candidates.filtered("email")[:1] or candidates[:1]

    def _salesperson_from_parent(self):
        """The parent's salesperson, or the parent's parent when the parent has none."""
        self.ensure_one()
        parent = self.parent_id
        if parent.user_id:
            return parent.user_id
        if parent.parent_id.user_id:
            return parent.parent_id.user_id
        return self.env["res.users"]

    # Base declares user_id with compute="_compute_user_id". The override below
    # depends on parent_id.user_id, the field itself, so Odoo requires
    # recursive=True; without it the registry sets the flag and logs a UserWarning.
    user_id = fields.Many2one(recursive=True)

    @api.depends("parent_id", "parent_id.user_id", "parent_id.parent_id.user_id")
    def _compute_user_id(self):
        """A child takes the company salesperson. An empty parent salesperson is left alone."""
        for partner in self:
            if not partner.parent_id:
                continue
            source = partner._salesperson_from_parent()
            if source:
                partner.user_id = source

    property_supplier_payment_term_id = fields.Many2one(
        compute="_compute_supplier_payment_term_id",
        store=True,
        readonly=False,
        recursive=True,
    )

    def _supplier_payment_term_from_parent(self):
        """The parent's vendor term, or the parent's parent when the parent has none."""
        self.ensure_one()
        parent = self.parent_id
        if parent.property_supplier_payment_term_id:
            return parent.property_supplier_payment_term_id
        if parent.parent_id.property_supplier_payment_term_id:
            return parent.parent_id.property_supplier_payment_term_id
        return self.env["account.payment.term"]

    @api.depends(
        "parent_id",
        "parent_id.property_supplier_payment_term_id",
        "parent_id.parent_id.property_supplier_payment_term_id",
    )
    def _compute_supplier_payment_term_id(self):
        """A child takes the company vendor term. An empty ancestor term is left alone."""
        for partner in self:
            if not partner.parent_id:
                continue
            source = partner._supplier_payment_term_from_parent()
            if source:
                partner.property_supplier_payment_term_id = source

    @api.depends("phone_line_ids.label", "phone_line_ids.number")
    def _compute_mobile(self):
        for partner in self:
            line = partner.phone_line_ids.filtered(lambda row: row.label == "mobile")[:1]
            partner.mobile = line.number or False

    def _search_mobile(self, operator, value):
        return [("phone_line_ids", "any", [("label", "=", "mobile"), ("number", operator, value)])]

    def _inverse_mobile(self):
        phone_model = self.env["plasticos.partner.phone"]
        new_lines = []
        for partner in self:
            number = (partner.mobile or "").strip()
            lines = partner.phone_line_ids.filtered(lambda row: row.label == "mobile")
            if not number:
                lines.unlink()
                continue
            if lines:
                lines[:1].number = number
            else:
                new_lines.append({"partner_id": partner.id, "label": "mobile", "number": number})
        if new_lines:
            # One create for every partner that had no mobile line yet.
            phone_model.create(new_lines)

    @api.depends(
        "is_company",
        "parent_id",
        "type",
        "child_ids.name",
        "child_ids.is_company",
        "child_ids.type",
        "site_person_ids.name",
    )
    def _compute_contact_header_name(self):
        for partner in self:
            if partner._plasticos_is_site():
                people = partner.site_person_ids
            elif not partner.is_company:
                partner.contact_header_name = False
                continue
            else:
                people = partner.child_ids.filtered(
                    lambda child: not child.is_company and not child._plasticos_is_site()
                )
            names = ", ".join(people.mapped("name"))
            partner.contact_header_name = names

    @api.depends("child_ids", "child_ids.is_company", "child_ids.type")
    def _compute_location_child_ids(self):
        for partner in self:
            partner.location_child_ids = partner.child_ids.filtered(lambda child: child._plasticos_is_site())

    def _location_reference_count(self, model_name, field_names):
        """How many installed-model rows point at this location. No elevated read."""
        self.ensure_one()
        if model_name not in self.env:
            return 0
        model = self.env[model_name].with_context(active_test=False)
        names = [name for name in field_names if name in model._fields]
        if not names:
            return 0
        domain = [(name, "=", self.id) for name in names]
        if len(domain) > 1:
            domain = ["|"] * (len(domain) - 1) + domain
        return model.search_count(domain)

    def _location_is_referenced(self):
        """True when people, profiles, or commercial documents still use this location."""
        self.ensure_one()
        partners = self.env["res.partner"].with_context(active_test=False)
        if partners.search_count([("parent_id", "=", self.id)]):
            return True
        location = self.with_context(active_test=False)
        if location.site_person_ids or location.material_profile_ids or location.facility_profile_ids:
            return True
        return any(
            self._location_reference_count(model_name, field_names)
            for model_name, field_names in _LOCATION_REFERENCE_MODELS
        )

    def action_remove_location(self):
        """Delete an unused child location, or archive one that history still uses.

        The row leaves the company Locations list either way. The parent company
        itself is refused.
        """
        self.ensure_one()
        self.check_access("read")
        parent = self.parent_id
        parent.check_access("read")
        if not self._plasticos_is_site():
            raise UserError("Only a location of a company can be removed from this list.")
        referenced = self._location_is_referenced()
        elevated = self.sudo()  # sudo: caller read this child location and lacks partner unlink
        if referenced:
            elevated.write({"active": False, "entity_status": "inactive"})
        else:
            elevated.unlink()
        return True

    def _avatar_get_placeholder_path(self):
        if self.is_company:
            if self.company_role == "carrier":
                return "base/static/img/truck.png"
            return "base/static/img/company_image.png"
        return super()._avatar_get_placeholder_path()

    def _compute_avatar(self, avatar_field, image_field):
        """A company picture follows the company, not the Contact address type.

        Odoo sends every Contact address to the initials picture before it
        considers the company placeholder. A counterparty is type Contact, so
        that path would leave a letter on a company. An uploaded photo still wins.
        """
        companies = self.filtered("is_company")
        others = self - companies
        if others:
            super(ResPartner, others)._compute_avatar(avatar_field, image_field)
        photographed = companies.filtered(lambda partner: partner[image_field])
        for partner in photographed:
            partner[avatar_field] = partner[image_field]
        bare = companies - photographed
        for _path, group in tools.groupby(bare, key=lambda partner: partner._avatar_get_placeholder_path()):
            grouped = self.env["res.partner"].concat(*group)
            grouped[avatar_field] = base64.b64encode(grouped[0]._avatar_get_placeholder())

    @api.depends("name", "user_ids.share", "image_128", "is_company", "type", "company_role")
    def _compute_avatar_128(self):
        self._compute_avatar("avatar_128", "image_128")

    def write(self, vals):
        if "parent_id" in vals and not vals.get("parent_id"):
            for rec in self:
                if rec.facility_profile_ids:
                    raise ValidationError("Cannot convert facility to parent while capability profile exists.")
        res = super().write(vals)
        if "company_role" in vals:
            self._sync_rank_from_role()
        return res
