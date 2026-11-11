import logging

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

RES_PARTNER = "res.partner"
IR_ATTACHMENT = "ir.attachment"
MAIL_MESSAGE = "mail.message"

# Context key the Send Offer composer carries. Only a composer opened by
# ``action_send`` and submitted through native Odoo Mail moves an offer to Sent.
OFFER_SEND_CONTEXT = "plasticos_offer_send"


class PlasticosOffer(models.Model):
    """Offer lifecycle: draft → sent → responded → accepted/rejected/expired.

    An offer is created from an accepted match result. It represents a
    concrete commercial proposal from a supplier to a buyer (or vice
    versa) for a specific material at a specific price.
    """

    _name = "plasticos.offer"
    _description = "Material Offer"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _rec_name = "name"

    # ═════════════════════════════════════════════════════════
    # Identity
    # ═════════════════════════════════════════════════════════

    name = fields.Char(
        string="Offer Reference",
        required=True,
        copy=False,
        readonly=True,
        default="/",
        index=True,
    )

    # ═════════════════════════════════════════════════════════
    # Origin
    # ═════════════════════════════════════════════════════════

    # ``match_result_id`` (Gate result lineage) is owned by plasticos_crm_bridge,
    # which depends on both this module and plasticos_matching.
    intake_id = fields.Many2one(
        "plasticos.intake",
        string="Intake",
        index=True,
        ondelete="restrict",
        tracking=True,
        help="Optional originating intake. An offer created from a native opportunity's Gate result has none.",
    )

    # ═════════════════════════════════════════════════════════
    # Parties
    # ═════════════════════════════════════════════════════════

    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
    )
    buyer_id = fields.Many2one(
        "res.partner",
        string="Buyer",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
    )

    # ═════════════════════════════════════════════════════════
    # Material Summary (denormalized for quick display)
    # ═════════════════════════════════════════════════════════

    polymer = fields.Char(
        related="intake_id.polymer_id.name",
        string="Polymer",
        store=True,
        index=True,
    )
    form = fields.Char(
        related="intake_id.form_id.name",
        string="Form",
        store=True,
    )

    # ═════════════════════════════════════════════════════════
    # Commercial Terms
    # ═════════════════════════════════════════════════════════

    price_per_lb = fields.Float(
        digits=(10, 4),
        tracking=True,
        help="Offered price per pound.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        ondelete="restrict",
    )
    quantity_lbs = fields.Float(
        tracking=True,
        help="Total quantity offered in pounds.",
    )
    loads = fields.Integer(
        help="Number of truckloads.",
    )
    total_value = fields.Float(
        string="Total Value",
        compute="_compute_total_value",
        store=True,
        help="Total deal value: price_per_lb × quantity_lbs.",
    )
    days_until_expiry = fields.Integer(
        string="Days Until Expiry",
        compute="_compute_days_until_expiry",
        help="Days remaining before this offer expires. Negative = already expired.",
    )
    delivery_terms = fields.Selection(
        [
            ("fob_origin", "FOB Origin"),
            ("fob_destination", "FOB Destination"),
            ("cif", "CIF"),
            ("exw", "EXW"),
            ("dap", "DAP"),
        ],
        tracking=True,
    )
    payment_terms = fields.Selection(
        [
            ("net_15", "Net 15"),
            ("net_30", "Net 30"),
            ("net_45", "Net 45"),
            ("net_60", "Net 60"),
            ("cod", "COD"),
            ("prepaid", "Prepaid"),
        ],
        tracking=True,
    )
    valid_until = fields.Date(
        tracking=True,
        help="Offer expiration date.",
    )
    notes = fields.Text(
        help="Additional terms, conditions, or notes.",
    )

    # ═════════════════════════════════════════════════════════
    # Buyer-facing content and email audience
    # ═════════════════════════════════════════════════════════

    material_summary = fields.Char(
        string="Material",
        help="Short material label shown in offer lists. Set from the originating material when the draft is made.",
    )
    material_description = fields.Text(
        string="Material Description",
        help="Buyer-facing material description sent in the offer email. Editable while Draft; frozen once sent.",
    )
    material_image_ids = fields.Many2many(
        IR_ATTACHMENT,
        "plasticos_offer_material_image_rel",
        "offer_id",
        "attachment_id",
        string="Material Pictures",
        help="Pictures referenced for the offer email. The source attachments are not copied while drafting; "
        "the pictures actually sent are stored on the offer when the email is submitted.",
    )
    material_image_count = fields.Integer(
        string="Pictures",
        compute="_compute_material_image_count",
        help="Number of material pictures selected for the offer email.",
    )
    recipient_partner_ids = fields.Many2many(
        RES_PARTNER,
        "plasticos_offer_recipient_partner_rel",
        "offer_id",
        "partner_id",
        string="Email Recipients",
        help="Contacts of the buyer company who receive this offer by email. They must belong to the buyer.",
    )
    recipient_count = fields.Integer(
        string="Recipients",
        compute="_compute_recipient_count",
        help="Number of buyer contacts selected to receive the offer email.",
    )
    sent_message_id = fields.Many2one(
        MAIL_MESSAGE,
        string="Sent Email",
        readonly=True,
        copy=False,
        index=True,
        ondelete="set null",
        help="Native Odoo Mail message submitted when the offer was sent. "
        "Queued by Odoo Mail; external delivery is shown on the message itself.",
    )
    sent_date = fields.Datetime(
        string="Sent On",
        readonly=True,
        copy=False,
        help="When the offer email was submitted to Odoo Mail.",
    )

    # ═════════════════════════════════════════════════════════
    # Lifecycle
    # ═════════════════════════════════════════════════════════

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent"),
            ("responded", "Responded"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        tracking=True,
        index=True,
        required=True,
    )

    # ═════════════════════════════════════════════════════════
    # Material Images (propagated from intake)
    # ═════════════════════════════════════════════════════════

    image_ids = fields.One2many(
        "ir.attachment",
        "res_id",
        string="Material Images",
        domain=[("res_model", "=", "plasticos.offer"), ("mimetype", "like", "image/")],
        help="Material photos propagated from the intake record.",
    )
    image_count = fields.Integer(
        string="Images",
        compute="_compute_image_count",
    )

    @api.depends("material_image_ids")
    def _compute_material_image_count(self):
        for rec in self:
            rec.material_image_count = len(rec.material_image_ids)

    @api.depends("recipient_partner_ids")
    def _compute_recipient_count(self):
        for rec in self:
            rec.recipient_count = len(rec.recipient_partner_ids)

    def _compute_image_count(self):
        Attachment = self.env["ir.attachment"]
        stored_ids = [record_id for record_id in self.ids if isinstance(record_id, int) and record_id > 0]
        counts = {}
        if stored_ids:
            # One grouped count for the whole recordset; unsaved records count 0.
            rows = Attachment._read_group(
                [
                    ("res_model", "=", "plasticos.offer"),
                    ("res_id", "in", stored_ids),
                    ("mimetype", "like", "image/"),
                ],
                ["res_id"],
                ["__count"],
            )
            counts = dict(rows)
        for rec in self:
            rec.image_count = counts.get(rec.id, 0) if isinstance(rec.id, int) else 0

    response_notes = fields.Text(
        help="Buyer's response or counter-offer notes.",
    )
    counter_price_per_lb = fields.Float(
        digits=(10, 4),
        help="Counter-offered price per pound from the buyer.",
    )

    accepted_by = fields.Many2one(
        "res.users",
        readonly=True,
        ondelete="restrict",
    )
    accepted_date = fields.Datetime(
        readonly=True,
    )
    rejection_reason = fields.Text()

    # ═════════════════════════════════════════════════════════
    # Display
    # ═════════════════════════════════════════════════════════

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    # ═════════════════════════════════════════════════════════
    # Constraints
    # ═════════════════════════════════════════════════════════

    _check_price_positive = models.Constraint(
        "check(price_per_lb >= 0)",
        "Price per pound cannot be negative.",
    )

    _check_quantity_positive = models.Constraint(
        "check(quantity_lbs >= 0)",
        "Quantity cannot be negative.",
    )

    # ═════════════════════════════════════════════════════════
    # Computed
    # ═════════════════════════════════════════════════════════

    @api.depends("name", "intake_id", "supplier_id", "buyer_id", "state")
    def _compute_display_name(self):
        for rec in self:
            # Display name without year: OFR-26-04001 → OFR-04001
            if rec.name and rec.name != "/":
                parts = rec.name.split("-")
                if len(parts) == 3:
                    short_name = f"{parts[0]}-{parts[2]}"
                else:
                    short_name = rec.name
            else:
                short_name = "Offer"
            supply = rec.intake_id.display_name or rec.supplier_id.name or "?"
            buyer = rec.buyer_id.name or "?"
            rec.display_name = f"{short_name}: {supply} → {buyer} [{rec.state or 'draft'}]"

    @api.model_create_multi
    def create(self, vals_list):
        """Create offer with auto-generated sequence number + propagate images."""
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                sequence = self.env["ir.sequence"].next_by_code("plasticos.offer")
                if not sequence:
                    raise UserError(
                        "Unable to generate offer reference number. "
                        "Please ensure the sequence 'plasticos.offer' is configured."
                    )
                vals["name"] = sequence
        records = super().create(vals_list)
        for rec in records:
            if rec.intake_id:
                rec.copy_images_from("plasticos.intake", rec.intake_id.id)
        return records

    # Commercial terms frozen once the offer leaves draft. State and response
    # fields stay writable; a changed deal is a new offer, never a rewritten one.
    _TERM_FIELDS = (
        "price_per_lb",
        "currency_id",
        "quantity_lbs",
        "loads",
        "delivery_terms",
        "payment_terms",
        "valid_until",
        "supplier_id",
        "buyer_id",
        "intake_id",
    )

    # Buyer-facing content frozen once sent. Any write to the relational ones is
    # refused after draft; the sent email and its recipients are the audit record.
    _FROZEN_CONTENT_FIELDS = (
        "material_description",
        "material_summary",
        "material_image_ids",
        "recipient_partner_ids",
    )

    def _plasticos_term_fields(self):
        """Fields frozen once the offer leaves draft. Bridges extend this tuple."""
        return self._TERM_FIELDS

    def _frozen_term_changes(self, vals):
        """Term fields in ``vals`` whose value differs from the stored one."""
        self.ensure_one()
        changed = []
        for name in self._plasticos_term_fields():
            if name not in vals:
                continue
            current = self[name]
            current = current.id if hasattr(current, "id") else current
            if current != vals[name]:
                changed.append(name)
        for name in self._FROZEN_CONTENT_FIELDS:
            if name not in vals:
                continue
            field = self._fields[name]
            if field.type in ("many2many", "one2many") or self[name] != vals[name]:
                changed.append(name)
        return changed

    def _plasticos_check_sent_evidence(self, vals):
        """Sent is reachable only with the native Odoo Mail message submitted for this offer."""
        if vals.get("state") != "sent":
            return
        message = self.env[MAIL_MESSAGE].browse(vals.get("sent_message_id") or [])
        for rec in self:
            if rec.state == "sent":
                continue
            if not message or message.model != self._name or message.res_id != rec.id:
                raise UserError(
                    _(
                        "Offer %(offer)s can only become Sent by sending its email with Send Offer. "
                        "No email was submitted for it.",
                        offer=rec.name,
                    )
                )

    def write(self, vals):
        """Guard against modifying closed offers (except state changes) and against term rewrites after draft."""
        self._plasticos_check_sent_evidence(vals)
        closed_states = ("accepted", "rejected", "expired", "cancelled")
        if "state" not in vals:
            for rec in self:
                if rec.state in closed_states:
                    raise UserError(
                        f"Cannot modify offer '{rec.name}' in state '{rec.state}'. Closed offers are immutable."
                    )
        for rec in self:
            if rec.state == "draft":
                continue
            changed = rec._frozen_term_changes(vals)
            if changed:
                raise UserError(
                    f"Offer '{rec.name}' was sent; its terms ({', '.join(changed)}) are immutable. "
                    "Create a new offer instead."
                )
        return super().write(vals)

    def unlink(self):
        """Prevent deletion of accepted/rejected offers."""
        for rec in self:
            if rec.state in ("accepted", "rejected"):
                raise UserError(
                    f"Cannot delete offer '{rec.name}' after acceptance/rejection. Offers must be preserved for audit."
                )
        return super().unlink()

    @api.depends("price_per_lb", "quantity_lbs")
    def _compute_total_value(self):
        """Total deal value = price × quantity."""
        for rec in self:
            rec.total_value = (rec.price_per_lb or 0) * (rec.quantity_lbs or 0)

    @api.depends("valid_until")
    def _compute_days_until_expiry(self):
        """Days remaining before expiry. Negative = expired."""
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.valid_until:
                rec.days_until_expiry = (rec.valid_until - today).days
            else:
                rec.days_until_expiry = 999

    # ═════════════════════════════════════════════════════════
    # Navigation Actions (for smart buttons)
    # ═════════════════════════════════════════════════════════

    def action_view_intake(self):
        """Navigate to the linked intake."""
        self.ensure_one()
        if not self.intake_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": f"Intake — {self.intake_id.name}",
            "res_model": "plasticos.intake",
            "view_mode": "form",
            "res_id": self.intake_id.id,
        }

    def action_view_supplier(self):
        """Navigate to the supplier partner."""
        self.ensure_one()
        if not self.supplier_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": self.supplier_id.name,
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.supplier_id.id,
        }

    def action_view_buyer(self):
        """Navigate to the buyer partner."""
        self.ensure_one()
        if not self.buyer_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": self.buyer_id.name,
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.buyer_id.id,
        }

    # ═════════════════════════════════════════════════════════
    # State Transitions
    # ═════════════════════════════════════════════════════════

    def action_send(self):
        """Open the native Odoo email composer for this offer. Opening it changes nothing.

        The offer becomes Sent only when the composer submits the email through
        native Odoo Mail (``mail.compose.message`` extension in this module).
        Discarding the composer leaves the offer in Draft.
        """
        if len(self) != 1:
            raise UserError(_("Send one offer at a time: open the offer and use Send Offer to review its email."))
        self._plasticos_raise_send_blockers()
        recipients = self._plasticos_default_recipients()
        attachments = self._plasticos_email_attachments()
        return {
            "type": "ir.actions.act_window",
            "name": _("Send Offer"),
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {
                "default_model": self._name,
                "default_res_ids": [self.id],
                "default_composition_mode": "comment",
                "default_message_type": "comment",
                "default_subtype_xmlid": "mail.mt_comment",
                "default_partner_ids": recipients.ids,
                "default_subject": self._plasticos_offer_email_subject(),
                "default_body": self._plasticos_offer_email_body(with_pictures=bool(attachments)),
                "default_attachment_ids": attachments.ids,
                "default_notify_skip_followers": True,
                "mail_post_autofollow": False,
                OFFER_SEND_CONTEXT: True,
            },
        }

    # ── Send Offer: validation, content, recipients ─────────────

    def _plasticos_partner_in_buyer(self, partner):
        """True when ``partner`` is the buyer company or one of its contacts/sites (``child_of``)."""
        self.ensure_one()
        buyer = self.buyer_id
        node = partner
        seen = set()
        while node and node.id not in seen:
            if node == buyer:
                return True
            seen.add(node.id)
            node = node.parent_id
        return False

    def _plasticos_check_recipients(self, partners):
        """Refuse an email audience outside this offer's buyer. Returns the deliverable partners."""
        self.ensure_one()
        if not partners:
            raise UserError(_("Offer %s has no email recipient. Add a buyer contact with an email.") % self.name)
        outsiders = partners.filtered(lambda partner: not self._plasticos_partner_in_buyer(partner))
        if outsiders:
            raise UserError(
                _(
                    "Offer %(offer)s may only be emailed to contacts of %(buyer)s. Remove: %(names)s.",
                    offer=self.name,
                    buyer=self.buyer_id.display_name,
                    names=", ".join(outsiders.mapped("display_name")),
                )
            )
        missing = partners.filtered(lambda partner: not partner.email)
        if missing:
            raise UserError(
                _(
                    "These recipients have no email address: %(names)s. Add an email to the contact or remove it.",
                    names=", ".join(missing.mapped("display_name")),
                )
            )
        return partners

    def _plasticos_send_blockers(self):
        """Business reasons this offer cannot be emailed now. Bridges extend the list."""
        self.ensure_one()
        blockers = []
        if self.state != "draft":
            blockers.append(_("Only a draft offer can be sent; this one is %s.") % self.state)
        if not self.buyer_id:
            blockers.append(_("Select the buyer."))
        if not self.supplier_id:
            blockers.append(_("Select the supplier."))
        if (self.price_per_lb or 0.0) <= 0.0:
            blockers.append(_("Enter the buyer price per lb. An unpriced offer cannot be sent."))
        if (self.quantity_lbs or 0.0) <= 0.0:
            blockers.append(_("Enter the quantity in lbs."))
        if self.valid_until and self.valid_until < fields.Date.context_today(self):
            blockers.append(_("The offer expiry date is in the past."))
        return blockers

    def _plasticos_raise_send_blockers(self):
        self.ensure_one()
        blockers = self._plasticos_send_blockers()
        if blockers:
            raise UserError(
                _("Offer %(offer)s cannot be sent yet:\n- %(why)s", offer=self.name, why="\n- ".join(blockers))
            )

    def _plasticos_default_recipients(self):
        """The selected buyer contacts, or the buyer company itself when it has an email."""
        self.ensure_one()
        partners = self.recipient_partner_ids
        if not partners and self.buyer_id.email:
            partners = self.buyer_id
        return self._plasticos_check_recipients(partners)

    def _plasticos_email_attachments(self):
        """Selected material pictures plus offer-owned pictures, one per distinct content."""
        self.ensure_one()
        candidates = self.material_image_ids | self.image_ids
        chosen = self.env[IR_ATTACHMENT]
        checksums = set()
        for attachment in candidates.sorted("id"):
            if not (attachment.mimetype or "").startswith("image/"):
                continue
            key = attachment.checksum or attachment.id
            if key in checksums:
                continue
            checksums.add(key)
            chosen |= attachment
        return chosen

    def _plasticos_allowed_email_attachments(self):
        """Attachments the Send Offer composer may carry besides files uploaded in the composer."""
        self.ensure_one()
        return self.material_image_ids | self.env[IR_ATTACHMENT].search(
            [("res_model", "=", self._name), ("res_id", "=", self.id)]
        )

    def _plasticos_short_reference(self):
        self.ensure_one()
        parts = (self.name or "").split("-")
        return f"{parts[0]}-{parts[2]}" if len(parts) == 3 else (self.name or "")

    def _plasticos_material_label(self):
        self.ensure_one()
        if self.material_summary:
            return self.material_summary
        label = " ".join(part for part in (self.polymer, self.form) if part)
        return label or _("Material")

    def _plasticos_offer_email_subject(self):
        self.ensure_one()
        return _(
            "Material Offer: %(material)s | %(ref)s",
            material=self._plasticos_material_label(),
            ref=self._plasticos_short_reference(),
        )

    def _plasticos_selection_label(self, field_name):
        self.ensure_one()
        value = self[field_name]
        if not value:
            return ""
        return dict(self._fields[field_name]._description_selection(self.env)).get(value, value)

    def _plasticos_offer_email_body(self, with_pictures=False):
        """Buyer-facing HTML body. Every value is escaped; nothing internal is included."""
        self.ensure_one()
        currency = self.currency_id.name or ""
        greeting = self.buyer_id.name or _("there")
        rows = [
            (_("Quantity"), _("%(qty)s lbs", qty=f"{self.quantity_lbs:,.0f}")),
            (_("Price"), f"{self.price_per_lb:,.4f} {currency} / lb".strip()),
        ]
        if self.loads:
            rows.append((_("Loads"), str(self.loads)))
        if self.delivery_terms:
            rows.append((_("Delivery terms"), self._plasticos_selection_label("delivery_terms")))
        if self.payment_terms:
            rows.append((_("Payment terms"), self._plasticos_selection_label("payment_terms")))
        if self.valid_until:
            rows.append((_("Offer valid until"), fields.Date.to_string(self.valid_until)))
        description = self.material_description or self._plasticos_material_label()
        description_html = Markup("<br/>").join(escape(line) for line in description.splitlines())
        parts = [
            Markup("<p>%s</p>") % _("Hello %s,", greeting),
            Markup("<p>%s</p>")
            % _("We can offer the following material (offer %s):", self._plasticos_short_reference()),
            Markup("<p>%s</p>") % description_html,
            Markup("<ul>%s</ul>")
            % Markup("").join(Markup("<li><b>%s:</b> %s</li>") % (label, value) for label, value in rows),
        ]
        if self.notes:
            parts.append(Markup("<p>%s</p>") % Markup("<br/>").join(escape(line) for line in self.notes.splitlines()))
        if with_pictures:
            parts.append(Markup("<p>%s</p>") % _("Material pictures are attached."))
        return Markup("").join(parts)

    def _plasticos_freeze_on_send_vals(self):
        """Extra values frozen together with the Sent state. Bridges extend this."""
        self.ensure_one()
        return {}

    def _plasticos_mark_sent(self, message):
        """Record Sent with the native mail message that was submitted. Called by the composer only."""
        self.ensure_one()
        vals = {
            "state": "sent",
            "sent_message_id": message.id,
            "sent_date": fields.Datetime.now(),
        }
        vals.update(self._plasticos_freeze_on_send_vals())
        self.write(vals)
        _logger.info("Offer %s sent by email (mail.message %s).", self.name, message.id)

    def action_mark_responded(self):
        """Mark that the buyer has responded."""
        for rec in self:
            if rec.state != "sent":
                raise UserError("Only sent offers can be marked as responded.")
            rec.write({"state": "responded"})

    def action_accept(self):
        """Accept this offer — ready for transaction creation."""
        for rec in self:
            if rec.state not in ("sent", "responded"):
                raise UserError("Only sent or responded offers can be accepted.")
            rec.write(
                {
                    "state": "accepted",
                    "accepted_by": self.env.uid,
                    "accepted_date": fields.Datetime.now(),
                }
            )
        _logger.info("Offers accepted: %s", self.mapped("display_name"))

    def action_reject(self):
        """Reject this offer."""
        for rec in self:
            if rec.state in ("accepted", "cancelled", "expired"):
                raise UserError("Cannot reject an accepted, cancelled, or expired offer.")
            rec.write({"state": "rejected"})
        _logger.info("Offers rejected: %s", self.mapped("display_name"))

    def action_cancel(self):
        """Cancel this offer."""
        for rec in self:
            if rec.state == "accepted":
                raise UserError("Cannot cancel an accepted offer.")
            rec.write({"state": "cancelled"})

    def action_reset_to_draft(self):
        """Reset a rejected or cancelled offer back to draft."""
        for rec in self:
            if rec.state not in ("rejected", "cancelled"):
                raise UserError("Only rejected or cancelled offers can be reset.")
            rec.write({"state": "draft"})

    # ═════════════════════════════════════════════════════════
    # Image Propagation & Email
    # ═════════════════════════════════════════════════════════

    def copy_images_from(self, source_model, source_id):
        """Copy image attachments from another record to this offer."""
        self.ensure_one()
        Attachment = self.env["ir.attachment"]
        source_images = Attachment.search(
            [
                ("res_model", "=", source_model),
                ("res_id", "=", source_id),
                ("mimetype", "like", "image/"),
            ]
        )
        for img in source_images:
            img.copy(
                {
                    "res_model": "plasticos.offer",
                    "res_id": self.id,
                }
            )
        if source_images:
            _logger.info(
                "Copied %d image(s) from %s/%s to offer %s.",
                len(source_images),
                source_model,
                source_id,
                self.id,
            )

    def action_email_images(self):
        """Open email composer with material images pre-attached."""
        self.ensure_one()
        Attachment = self.env["ir.attachment"]
        images = Attachment.search(
            [
                ("res_model", "=", "plasticos.offer"),
                ("res_id", "=", self.id),
                ("mimetype", "like", "image/"),
            ]
        )
        if not images:
            raise UserError("No material images to send.")

        subject = f"Material Images — {self.display_name}"
        return {
            "type": "ir.actions.act_window",
            "name": "Send Material Images",
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_model": "plasticos.offer",
                "default_res_ids": [self.id],
                "default_subject": subject,
                "default_attachment_ids": images.ids,
                "default_body": (
                    f"<p>Please find attached material images for offer <b>{self.name}</b>.</p>"
                    f"<p>{len(images)} image(s) attached.</p>"
                ),
            },
        }

    @api.model
    def cron_expire_offers(self):
        """Auto-expire offers past their valid_until date.

        Runs daily to transition non-terminal offers to 'expired' state.
        """
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_offer.ir_cron_expire_offers"])
        locked = self.env.cr.fetchone()[0]
        if not locked:
            return

        try:
            today = fields.Date.today()
            offers_to_expire = self.search(
                [
                    ("valid_until", "<", today),
                    ("state", "in", ("draft", "sent", "responded")),
                ],
                order="valid_until ASC, id ASC",
                limit=500,
            )
            if offers_to_expire:
                offers_to_expire.write({"state": "expired"})
                _logger.info(
                    "Cron: expired %d offers past valid_until: %s",
                    len(offers_to_expire),
                    offers_to_expire.mapped("display_name"),
                )
        finally:
            self.env.cr.execute("SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_offer.ir_cron_expire_offers"])
