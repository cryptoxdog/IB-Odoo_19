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
    _rec_name = "display_name"

    # ═════════════════════════════════════════════════════════
    # Origin
    # ═════════════════════════════════════════════════════════

    match_result_id = fields.Many2one(
        "plasticos.match.result",
        string="Match Result",
        index=True,
        ondelete="set null",
        help="The match result that originated this offer, if any.",
    )
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
    )
    quantity_lbs = fields.Float(
        tracking=True,
        help="Total quantity offered in pounds.",
    )
    loads = fields.Integer(
        help="Number of truckloads.",
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

    _sql_constraints = [
        (
            "check_price_positive",
            "check(price_per_lb >= 0)",
            "Price per pound cannot be negative.",
        ),
        (
            "check_quantity_positive",
            "check(quantity_lbs >= 0)",
            "Quantity cannot be negative.",
        ),
    ]

    # ═════════════════════════════════════════════════════════
    # Computed
    # ═════════════════════════════════════════════════════════

    @api.depends("intake_id", "buyer_id", "state")
    def _compute_display_name(self):
        for rec in self:
            intake = rec.intake_id.name or "?"
            buyer = rec.buyer_id.name or "?"
            rec.display_name = f"Offer: {intake} → {buyer} [{rec.state or 'draft'}]"

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
        today = fields.Date.today()
        offers_to_expire = self.search(
            [
                ("valid_until", "<", today),
                ("state", "in", ("draft", "sent", "responded")),
            ]
        )
        if offers_to_expire:
            offers_to_expire.write({"state": "expired"})
            _logger.info(
                "Cron: expired %d offers past valid_until: %s",
                len(offers_to_expire),
                offers_to_expire.mapped("display_name"),
            )
