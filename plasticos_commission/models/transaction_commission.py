"""Commission extension for plasticos.transaction.

Adds commission fields and overrides to the transaction model.
This extension pattern avoids the circular dependency:
  plasticos_transaction → plasticos_commission → plasticos_transaction (WRONG)
  plasticos_commission _inherits_ plasticos_transaction (CORRECT — one direction only)
"""

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class PlasticosTransactionCommission(models.Model):
    _inherit = "plasticos.transaction"

    # ── Commission Fields ─────────────────────────────────────────────────────
    commission_rule_id = fields.Many2one(
        "plasticos.commission.rule",
        string="Commission Rule",
        tracking=True,
    )
    commission_locked = fields.Boolean(
        string="Commission Locked",
        default=False,
        copy=False,
        tracking=True,
        help="When True, commission_amount is frozen at commission_locked_amount.",
    )
    commission_locked_amount = fields.Float(
        string="Locked Commission",
        copy=False,
        help="The commission amount captured at close time.",
    )
    commission_override_pct = fields.Float(
        string="Commission Override %",
        help="Admin override: fraction 0.0–1.0. Leave 0 to use rule. Only managers can edit.",
        groups="plasticos_transaction.group_plasticos_manager",
    )

    # ── Commission Compute ────────────────────────────────────────────────────

    @api.depends(
        "gross_margin",
        "commission_rule_id",
        "commission_override_pct",
        "state",
        "commission_locked",
        "commission_locked_amount",
    )
    def _compute_commission(self):
        """Override base stub — compute actual commission via service."""
        service = self.env["plasticos.commission.service"]
        for rec in self:
            if rec.commission_locked:
                rec.commission_amount = rec.commission_locked_amount or 0.0
                continue
            rec.commission_amount = service.compute_commission(rec)

    @api.depends("gross_margin", "commission_amount")
    def _compute_net_margin(self):
        """Override base — net margin = gross margin - commission."""
        for rec in self:
            rec.net_margin = rec.gross_margin - (rec.commission_amount or 0.0)

    # ── Commission Constraints ────────────────────────────────────────────────

    @api.constrains("commission_override_pct")
    def _check_override_pct_range(self):
        """Override base stub — validate commission override is a fraction 0.0–1.0."""
        for rec in self:
            if rec.commission_override_pct and not (0.0 <= rec.commission_override_pct <= 1.0):
                raise ValidationError(
                    "Commission override percentage must be between 0.0 and 1.0 (e.g., 0.15 for 15%)."
                )

    # ── Write Guards ──────────────────────────────────────────────────────────

    def _validate_write_immutability(self, rec, vals):
        """Override to add commission immutability guards."""
        super()._validate_write_immutability(rec, vals)
        if rec.state == "closed" and "commission_rule_id" in vals:
            raise UserError("Closed transactions are immutable.")
        if rec.commission_locked and "commission_rule_id" in vals:
            raise UserError("Commission cannot be modified after lock.")

    # ── Close Override ────────────────────────────────────────────────────────

    def _apply_close(self, rec):
        """Override to lock commission at close time, then write state."""
        service = self.env["plasticos.commission.service"]
        amount = service.compute_commission(rec)
        rec.commission_locked_amount = amount
        rec.commission_locked = True
        super()._apply_close(rec)
