# plasticos_intake/models/intake_match.py
# TIER-2 ADDITION (2026-04-01):
# offer_id Many2one added — enables idempotent offer creation
# and powers offer_count computed field on plasticos.intake.
# DB migration: nullable FK on plasticos_intake_match. Backwards-compatible.
# Requires: -u plasticos_intake

from odoo import fields, models


class IntakeMatch(models.Model):
    _name = "plasticos.intake.match"
    _description = "Intake Buyer Match Line"
    _order = "match_score desc, id asc"

    intake_id = fields.Many2one(
        "plasticos.intake", string="Intake", required=True,
        ondelete="cascade", index=True,
    )
    buyer_id = fields.Many2one(
        "res.partner", string="Buyer", required=True,
        ondelete="restrict", index=True,
    )
    match_score = fields.Float(
        string="Match %", digits=(5, 1), default=0.0,
        help="0–100 score produced by BuyerMatcher.",
    )
    typical_price = fields.Float(
        string="Typical Price ($/lb)", digits=(10, 4), default=0.0,
        help=(
            "Average $/lb sourced from avg_price_per_lb on the SOLD_TO "
            "Neo4j edge. 0.0 when no historical data available."
        ),
    )
    match_reason = fields.Text(string="Match Reason")
    selected = fields.Boolean(
        string="Send Offer?", default=False,
        help="Check to include this buyer when action_send_offers() runs.",
    )
    # TIER-2 ADDITION: back-ref to created offer
    offer_id = fields.Many2one(
        "plasticos.offer", string="Offer", ondelete="set null",
        copy=False, readonly=True,
        help=(
            "Set by action_send_offers(). Lines where offer_id is already "
            "set are skipped on re-run (idempotency guard)."
        ),
    )
    offer_state = fields.Selection(
        related="offer_id.state", string="Offer State",
        readonly=True, store=False,
    )

    _sql_constraints = [
        (
            "unique_intake_buyer",
            "UNIQUE(intake_id, buyer_id)",
            "A buyer can only appear once per intake match set.",
        ),
    ]
