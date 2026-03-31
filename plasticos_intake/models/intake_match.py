from odoo import api, fields, models


class IntakeBuyerMatch(models.Model):
    """Buyer match result line for an intake.

    Each line represents one potential buyer match with score and selection.
    Sorted by match_score descending (best matches first).
    """

    _name = "plasticos.intake.match"
    _description = "Intake Buyer Match"
    _order = "match_score desc, id"

    intake_id = fields.Many2one(
        "plasticos.intake",
        string="Intake",
        required=True,
        ondelete="cascade",
        index=True,
    )
    buyer_id = fields.Many2one(
        "res.partner",
        string="Buyer",
        required=True,
        domain="[('is_company', '=', True)]",
        index=True,
        ondelete="restrict",
    )
    buyer_name = fields.Char(
        related="buyer_id.name",
        string="Company Name",
        store=True,
    )
    buyer_city = fields.Char(
        related="buyer_id.city",
        string="City",
    )
    buyer_state = fields.Char(
        related="buyer_id.state_id.code",
        string="State",
    )

    # Match quality
    match_score = fields.Float(
        string="Match %",
        digits=(5, 1),
        help="Match score from 0-100. Higher = better match.",
    )
    match_reason = fields.Char(
        string="Why Matched",
        help="Brief explanation of why this buyer matched.",
    )

    # Selection for offer
    selected = fields.Boolean(
        string="Send Offer",
        default=False,
        help="Check to include this buyer in the offer.",
    )

    # Pricing (optional, from buyer preferences)
    typical_price = fields.Float(
        string="Typical Price",
        digits=(10, 2),
        help="Buyer's typical price per lb for this material type.",
    )

    @api.depends("buyer_id", "match_score")
    def _compute_display_name(self):
        for rec in self:
            if rec.buyer_id:
                rec.display_name = f"{rec.buyer_id.name} ({rec.match_score:.0f}%)"
            else:
                rec.display_name = "New Match"
