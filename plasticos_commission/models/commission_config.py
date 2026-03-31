"""Commission configuration helpers.

Provides max_budget_tokens with its legacy alias for backward compatibility.
"""
from __future__ import annotations

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PlasticosCommissionConfig(models.TransientModel):
    """System config accessor for commission module settings.

    Uses ir.config_parameter for persistence.
    Provides backward-compatible aliases for key renames.
    """

    _name = "plasticos.commission.config"
    _description = "PlasticOS Commission Configuration"

    # ── Token Budget ──────────────────────────────────────────────────────────
    # Primary key (new). Kept in sync with legacy alias via _compute/inverse.
    max_budget_tokens = fields.Integer(
        string="Max Budget Tokens",
        default=4096,
        help="Maximum number of LLM tokens allowed per commission scoring request.",
    )
    # Legacy alias: plasticos.commission.max_tokens (pre-rename)
    max_tokens = fields.Integer(
        string="Max Tokens (legacy alias)",
        compute="_compute_max_tokens",
        inverse="_inverse_max_tokens",
        help="Backward-compatible alias for max_budget_tokens. "
             "Reads/writes the same ICP key.",
    )

    _ICP_MAX_BUDGET_TOKENS = "plasticos.commission.max_budget_tokens"
    # Historical key written before rename — keep readable for migration
    _ICP_MAX_TOKENS_LEGACY = "plasticos.commission.max_tokens"

    @api.depends("max_budget_tokens")
    def _compute_max_tokens(self):
        for rec in self:
            rec.max_tokens = rec.max_budget_tokens

    def _inverse_max_tokens(self):
        for rec in self:
            rec.max_budget_tokens = rec.max_tokens

    @api.model
    def get_max_budget_tokens(self) -> int:
        """Return max_budget_tokens from ICP, falling back to legacy key then default."""
        icp = self.env["ir.config_parameter"].sudo()
        # Try new key first
        val = icp.get_param(self._ICP_MAX_BUDGET_TOKENS)
        if val:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
        # Fall back to legacy key
        val_legacy = icp.get_param(self._ICP_MAX_TOKENS_LEGACY)
        if val_legacy:
            try:
                return int(val_legacy)
            except (ValueError, TypeError):
                pass
        return 4096  # hard default

    @api.model
    def set_max_budget_tokens(self, value: int) -> None:
        """Write max_budget_tokens to ICP (both keys for backward compat)."""
        if value <= 0:
            raise ValueError(f"max_budget_tokens must be positive, got {value}")
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(self._ICP_MAX_BUDGET_TOKENS, str(value))
        # Keep legacy key in sync so old code reading it still works
        icp.set_param(self._ICP_MAX_TOKENS_LEGACY, str(value))
