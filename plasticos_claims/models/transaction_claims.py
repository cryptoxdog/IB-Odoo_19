"""Transaction extension for claims integration.

Issue 4 fix: Adds claim_ids One2many and proper @api.depends for
chargebacks/penalties to auto-update when claims are resolved.
"""

from odoo import api, fields, models


class PlasticosTransactionClaims(models.Model):
    _inherit = "plasticos.transaction"

    # ── Claim Link (Issue 4 fix) ───────────────────────────────
    claim_ids = fields.One2many(
        "plasticos.claim",
        "transaction_id",
        string="Claims",
        help="QC cases, chargebacks, and penalty claims linked to this transaction.",
    )
    claim_count = fields.Integer(
        compute="_compute_claim_count",
        store=True,
    )
    has_quality_claim = fields.Boolean(
        compute="_compute_has_quality_claim",
        store=True,
        help="True if any unresolved quality claims exist.",
    )

    @api.depends("claim_ids")
    def _compute_claim_count(self):
        for rec in self:
            rec.claim_count = len(rec.claim_ids)

    @api.depends("claim_ids", "claim_ids.state", "claim_ids.case_type")
    def _compute_has_quality_claim(self):
        """True if any unresolved quality-related claims exist."""
        quality_types = ("buyer_claim", "inspection")
        for rec in self:
            unresolved = rec.claim_ids.filtered(
                lambda c, qt=quality_types: c.case_type in qt and c.state not in ("resolved", "archived")
            )
            rec.has_quality_claim = bool(unresolved)

    @api.depends(
        "claim_ids",
        "claim_ids.state",
        "claim_ids.case_type",
        "claim_ids.recovery_amount",
    )
    def _compute_chargebacks_penalties(self):
        """Sum recoveries from resolved claims.

        Issue 4 fix: Now uses @api.depends so it auto-updates when claims change.
        Chargebacks and penalties are credits that reduce effective cost.
        """
        for rec in self:
            resolved_claims = rec.claim_ids.filtered(lambda c: c.state == "resolved")
            rec.freight_chargebacks = sum(
                c.recovery_amount for c in resolved_claims if c.case_type == "freight_chargeback"
            )
            rec.lightweight_penalties = sum(
                c.recovery_amount for c in resolved_claims if c.case_type == "lightweight_penalty"
            )
