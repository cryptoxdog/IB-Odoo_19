"""Manual buyer selection on a native Opportunity: one draft offer per buyer company.

The broker picks existing Contacts with the native Contacts search (filters,
favorites, tags, location). Selected contacts are grouped by their commercial
company (``res.partner.commercial_partner_id``); each company gets one Draft
``plasticos.offer`` linked directly to the opportunity, with the selected
contacts as email recipients. A Draft for that company that already exists is
reused. Nothing is sent and Gate is not called.
"""

from __future__ import annotations

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

OFFER_MODEL = "plasticos.offer"
RES_PARTNER = "res.partner"

# Opportunity material fields described to the buyer, in order. Supplier price,
# coordinates, internal notes and profile links are never described.
_DESCRIBED_RELATIONS = (
    ("color_id", "Color"),
    ("packaging_type_id", "Packaging"),
    ("source_type_id", "Source"),
)
# A zero is omitted: the ORM cannot tell an unrecorded value from a recorded 0,
# and the offer must not claim a measurement nobody took.
_DESCRIBED_MEASURES = (
    ("melt_flow_index", "Melt flow index", "{:g}"),
    ("density", "Density", "{:g}"),
    ("moisture_percent", "Moisture", "{:g}%"),
    ("contamination_percent", "Contamination", "{:g}%"),
)


def material_label(material):
    parts = [material.polymer_id.name, material.material_grade_id.name, material.form_id.name]
    return " ".join(part for part in parts if part)


def buyer_material_description(material):
    """Buyer-facing description of an opportunity material row. No price or internal data."""
    lines = []
    label = material_label(material)
    if label:
        lines.append(_("Material: %s", label))
    for field_name, caption in _DESCRIBED_RELATIONS:
        value = material[field_name]
        if value:
            lines.append(f"{caption}: {value.display_name}")
    if material.filler_type_id:
        filler = material.filler_type_id.display_name
        if material.filler_pct:
            filler = f"{filler} ({material.filler_pct:g}%)"
        lines.append(_("Filler: %s", filler))
    if material.origin_process_type:
        selection = dict(material._fields["origin_process_type"]._description_selection(material.env))
        lines.append(_("Origin process: %s", selection.get(material.origin_process_type, material.origin_process_type)))
    for field_name, caption, pattern in _DESCRIBED_MEASURES:
        value = material[field_name]
        if value:
            lines.append(f"{caption}: {pattern.format(value)}")
    if material.material_attribute_ids:
        lines.append(_("Attributes: %s", ", ".join(material.material_attribute_ids.mapped("display_name"))))
    if material.quantity_per_load_lbs:
        lines.append(_("Quantity per load: %s lbs", f"{material.quantity_per_load_lbs:,.0f}"))
    return "\n".join(lines)


class PlasticosOfferBuyerSelectionWizard(models.TransientModel):
    _name = "plasticos.offer.buyer.selection.wizard"
    _description = "Select Buyers for Draft Offers"

    opportunity_id = fields.Many2one(
        "crm.lead",
        string="Opportunity",
        required=True,
        readonly=True,
        ondelete="cascade",
        help="Opportunity the draft offers are generated for.",
    )
    supplier_partner_id = fields.Many2one(
        related="opportunity_id.partner_id",
        string="Supplier",
        help="Supplier of the opportunity. It cannot be selected as a buyer.",
    )
    contact_ids = fields.Many2many(
        RES_PARTNER,
        "plasticos_offer_buyer_wizard_partner_rel",
        "wizard_id",
        "partner_id",
        string="Buyer Contacts",
        help="Existing buyer companies or their contacts. Contacts of one company share one draft offer.",
    )
    buyer_count = fields.Integer(
        string="Buyer Companies",
        compute="_compute_selection_summary",
        help="Distinct buyer companies in the selection: one draft offer each.",
    )
    contact_count = fields.Integer(
        string="Contacts",
        compute="_compute_selection_summary",
        help="Selected contacts.",
    )
    selected_buyer_summary = fields.Text(
        string="Draft Offers to Generate",
        compute="_compute_selection_summary",
        help="Selected contacts grouped by buyer company.",
    )

    @api.depends("contact_ids", "contact_ids.commercial_partner_id", "contact_ids.email")
    def _compute_selection_summary(self):
        for wizard in self:
            groups = wizard._plasticos_group_contacts(wizard.contact_ids)
            wizard.buyer_count = len(groups)
            wizard.contact_count = len(wizard.contact_ids)
            lines = []
            for buyer, contacts in groups:
                recipients = wizard._plasticos_recipients(buyer, contacts)
                names = ", ".join(recipients.mapped("display_name")) or _("no contact with an email")
                lines.append(f"{buyer.display_name}: {names}")
            wizard.selected_buyer_summary = "\n".join(lines)

    @staticmethod
    def _plasticos_group_contacts(contacts):
        """[(buyer company, selected contacts)] keyed by commercial partner id, in first-seen order."""
        groups = {}
        for contact in contacts:
            buyer = contact.commercial_partner_id or contact
            entry = groups.setdefault(buyer.id, [buyer, contact.browse()])
            entry[1] |= contact
        return [tuple(entry) for entry in groups.values()]

    @staticmethod
    def _plasticos_recipients(buyer, contacts):
        """Selected contacts with an email. A selected company without an email is not a recipient."""
        return contacts.filtered(lambda partner: partner.email)

    def _plasticos_validated_groups(self, opportunity):
        """Server-side check of the selection; never trusts the dialog domain."""
        self.ensure_one()
        contacts = self.contact_ids
        if not contacts:
            raise UserError(_("Select at least one buyer contact."))
        contacts.check_access("read")
        archived = contacts.filtered(lambda partner: not partner.active)
        if archived:
            raise UserError(_("Archived contacts cannot receive offers: %s.") % ", ".join(archived.mapped("name")))
        allowed_companies = self.env.companies
        foreign = contacts.filtered(lambda partner: partner.company_id and partner.company_id not in allowed_companies)
        if foreign:
            raise UserError(
                _("These contacts belong to a company you are not working in: %s.") % ", ".join(foreign.mapped("name"))
            )
        supplier = opportunity.partner_id.commercial_partner_id
        groups = self._plasticos_group_contacts(contacts)
        undeliverable = []
        for buyer, group_contacts in groups:
            if buyer == supplier:
                raise UserError(
                    _("%s is the supplier of this opportunity and cannot be offered its own material.")
                    % buyer.display_name
                )
            if not buyer.active:
                raise UserError(_("Buyer company %s is archived.") % buyer.display_name)
            if not self._plasticos_recipients(buyer, group_contacts):
                undeliverable.append(buyer.display_name)
        if undeliverable:
            raise UserError(
                _(
                    "Select a contact with an email for: %s. No email address is invented; add one to the contact "
                    "or select another contact of that company.",
                    ", ".join(undeliverable),
                )
            )
        return groups

    def _plasticos_draft_vals(self, opportunity, material, buyer, recipients):
        images = material.image_attachment_ids.filtered(lambda att: (att.mimetype or "").startswith("image/"))
        return {
            "supplier_id": opportunity.partner_id.id,
            "buyer_id": buyer.id,
            "opportunity_id": opportunity.id,
            "material_source_id": material.id,
            "quantity_lbs": material.quantity_per_load_lbs or 0.0,
            "loads": 1,
            "material_summary": material_label(material) or False,
            "material_description": buyer_material_description(material) or False,
            "material_image_ids": [Command.set(images.ids)],
            "recipient_partner_ids": [Command.set(recipients.ids)],
        }

    def action_generate_draft_offers(self):
        """Create or reuse one Draft offer per selected buyer company and open them."""
        self.ensure_one()
        opportunity = self.opportunity_id
        opportunity.check_access("write")
        material = opportunity._plasticos_manual_offer_material()
        groups = self._plasticos_validated_groups(opportunity)
        Offer = self.env[OFFER_MODEL]
        # Serialize draft generation per opportunity; the partial unique index on
        # (opportunity_id, buyer_id) for manual drafts is the database backstop.
        self.env.cr.execute("SELECT id FROM crm_lead WHERE id = %s FOR UPDATE", [opportunity.id])
        buyers = self.env[RES_PARTNER].union(*[buyer for buyer, _contacts in groups])
        existing = Offer.search(
            [
                ("opportunity_id", "=", opportunity.id),
                ("buyer_id", "in", buyers.ids),
                ("match_result_id", "=", False),
                ("state", "=", "draft"),
            ]
        )
        draft_by_buyer = {offer.buyer_id.id: offer for offer in existing}
        offers = Offer
        vals_list = []
        for buyer, contacts in groups:
            recipients = self._plasticos_recipients(buyer, contacts)
            draft = draft_by_buyer.get(buyer.id)
            if draft:
                new_recipients = recipients - draft.recipient_partner_ids
                if new_recipients:
                    draft.write({"recipient_partner_ids": [Command.link(partner.id) for partner in new_recipients]})
                offers |= draft
            else:
                vals_list.append(self._plasticos_draft_vals(opportunity, material, buyer, recipients))
        created = Offer.create(vals_list) if vals_list else Offer
        offers |= created
        if created:
            opportunity.message_post(
                body=_(
                    "Created %(count)s draft offer(s) for manually selected buyers: %(buyers)s. Nothing was sent.",
                    count=len(created),
                    buyers=", ".join(created.mapped("buyer_id.display_name")),
                ),
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Draft Offers — %s") % opportunity.name,
            "res_model": OFFER_MODEL,
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [("id", "in", offers.ids)],
            "context": {"create": False},
            "target": "current",
        }
