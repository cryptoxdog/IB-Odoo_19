import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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

    # match_result_id disabled - plasticos_matching is external microservice
    # match_result_id = fields.Many2one(
    #     "plasticos.match.result",
    #     string="Match Result",
    #     index=True,
    #     ondelete="set null",
    #     help="The match result that originated this offer, if any.",
    # )
    intake_id = fields.Many2one(
        "plasticos.intake",
        string="Intake",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
        help="The intake record this offer is based on.",
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

    @api.depends("name", "intake_id", "buyer_id", "state")
    def _compute_display_name(self):
        for rec in self:
            # Display name without year: OFR-26-04001 → OFR-04001
            if rec.name and rec.name != "/":
                parts = rec.name.split("-")
                if len(parts) == 3:
                    short_name = f"{parts[0]}-{parts[2]}"
                else:
                    short_name = rec.name
                intake = rec.intake_id.display_name or "?"
                buyer = rec.buyer_id.name or "?"
                rec.display_name = f"{short_name}: {intake} → {buyer} [{rec.state or 'draft'}]"
            else:
                intake = rec.intake_id.display_name or "?"
                buyer = rec.buyer_id.name or "?"
                rec.display_name = f"Offer: {intake} → {buyer} [{rec.state or 'draft'}]"

    @api.model_create_multi
    def create(self, vals_list):
        """Create offer with auto-generated sequence number."""
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                sequence = self.env["ir.sequence"].next_by_code("plasticos.offer")
                if not sequence:
                    raise UserError(
                        "Unable to generate offer reference number. "
                        "Please ensure the sequence 'plasticos.offer' is configured."
                    )
                vals["name"] = sequence
        return super().create(vals_list)

    def write(self, vals):
        """Guard against modifying closed offers (except state changes)."""
        closed_states = ("accepted", "rejected", "expired", "cancelled")
        if "state" not in vals:
            for rec in self:
                if rec.state in closed_states:
                    raise UserError(
                        f"Cannot modify offer '{rec.name}' in state '{rec.state}'. Closed offers are immutable."
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
        """Mark offer as sent to the buyer."""
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft offers can be sent.")
            rec.write({"state": "sent"})
        _logger.info("Offers sent: %s", self.mapped("display_name"))

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
