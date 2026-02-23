import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PlasticosMatchResult(models.Model):
    """Stores match outcomes produced by the L9 adapter.

    No scoring logic lives in Odoo. This model is a pure result
    container: the L9 SDK adapter writes results here, and Odoo
    users consume them through views and reports.
    """

    _name = "plasticos.match.result"
    _description = "Material–Buyer Match Result"
    _inherit = ["mail.thread"]
    _order = "score desc, create_date desc"
    _rec_name = "display_name"

    # ═════════════════════════════════════════════════════════
    # Supply Side (Intake)
    # ═════════════════════════════════════════════════════════

    intake_id = fields.Many2one(
        "plasticos.intake",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
        help="The intake record that was submitted for matching.",
    )

    # Denormalized for list-view performance — no joins needed
    intake_polymer = fields.Char(
        related="intake_id.polymer_id.name",
        store=True,
        index=True,
    )
    intake_form = fields.Char(
        related="intake_id.form_id.name",
        store=True,
    )
    intake_partner_id = fields.Many2one(
        related="intake_id.partner_id",
        store=True,
        string="Supplier",
    )

    # ═════════════════════════════════════════════════════════
    # Demand Side (Buyer / Facility Capability)
    # ═════════════════════════════════════════════════════════

    buyer_partner_id = fields.Many2one(
        "res.partner",
        string="Buyer",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
        help="The buyer company matched to this intake.",
    )
    buyer_facility_id = fields.Many2one(
        "res.partner",
        string="Buyer Facility",
        index=True,
        ondelete="set null",
        domain="[('parent_id', '=', buyer_partner_id)]",
        help="Specific facility of the buyer, if matched at location level.",
    )
    facility_profile_id = fields.Many2one(
        "plasticos.facility.profile",
        string="Capability Profile",
        index=True,
        ondelete="set null",
        help="The facility capability profile that was evaluated.",
    )

    # ═════════════════════════════════════════════════════════
    # Score & Reasoning (written by L9)
    # ═════════════════════════════════════════════════════════

    score = fields.Float(
        digits=(5, 2),
        index=True,
        tracking=True,
        help="Overall match score (0–100). Computed by L9 adapter.",
    )
    confidence = fields.Float(
        digits=(5, 2),
        help="Confidence level of the match (0–100).",
    )
    score_breakdown = fields.Json(
        help="Structured breakdown of score components from L9.",
    )
    match_reasoning = fields.Text(
        help="Human-readable explanation of why this match was produced.",
    )

    # ═════════════════════════════════════════════════════════
    # L9 Metadata
    # ═════════════════════════════════════════════════════════

    l9_run_id = fields.Char(
        index=True,
        help="Unique identifier of the L9 matching run.",
    )
    l9_model_version = fields.Char(
        help="Version of the L9 matching model that produced this result.",
    )
    l9_timestamp = fields.Datetime(
        help="Timestamp when L9 produced this result.",
    )

    # ═════════════════════════════════════════════════════════
    # Lifecycle
    # ═════════════════════════════════════════════════════════

    state = fields.Selection(
        [
            ("pending", "Pending Review"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
            ("expired", "Expired"),
        ],
        default="pending",
        tracking=True,
        index=True,
    )
    reviewed_by = fields.Many2one(
        "res.users",
        string="Reviewed By",
        readonly=True,
    )
    reviewed_date = fields.Datetime(
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

    _check_unique_match_per_run = models.Constraint(
        "unique(intake_id, buyer_partner_id, l9_run_id)",
        "Duplicate match result for the same intake + buyer + run.",
    )

    _check_score_range = models.Constraint(
        "check(score >= 0 AND score <= 100)",
        "Score must be between 0 and 100.",
    )

    _check_confidence_range = models.Constraint(
        "check(confidence >= 0 AND confidence <= 100)",
        "Confidence must be between 0 and 100.",
    )

    # ═════════════════════════════════════════════════════════
    # Computed
    # ═════════════════════════════════════════════════════════

    @api.depends("intake_id", "buyer_partner_id", "score")
    def _compute_display_name(self):
        for rec in self:
            intake = rec.intake_id.name or "?"
            buyer = rec.buyer_partner_id.name or "?"
            rec.display_name = f"{intake} → {buyer} ({rec.score:.0f}%)"

    # ═════════════════════════════════════════════════════════
    # Actions
    # ═════════════════════════════════════════════════════════

    def action_accept(self):
        """Accept this match result — marks it for offer generation."""
        for rec in self:
            if rec.state != "pending":
                raise UserError(
                    f"Only pending match results can be accepted. " f"'{rec.display_name}' is in state '{rec.state}'."
                )
            rec.write(
                {
                    "state": "accepted",
                    "reviewed_by": self.env.uid,
                    "reviewed_date": fields.Datetime.now(),
                }
            )
        _logger.info(
            "Match results accepted: %s",
            self.mapped("display_name"),
        )

    def action_reject(self):
        """Reject this match result."""
        for rec in self:
            if rec.state != "pending":
                raise UserError(
                    f"Only pending match results can be rejected. " f"'{rec.display_name}' is in state '{rec.state}'."
                )
            rec.write(
                {
                    "state": "rejected",
                    "reviewed_by": self.env.uid,
                    "reviewed_date": fields.Datetime.now(),
                }
            )
        _logger.info(
            "Match results rejected: %s",
            self.mapped("display_name"),
        )
