"""Commission configuration helpers.

Provides max_budget_tokens with its legacy alias for backward compatibility.
All values are stored in ir.config_parameter — no dedicated table needed.
"""

from __future__ import annotations

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PlasticosCommissionConfig(models.AbstractModel):
    """System config accessor for commission module settings.

    AbstractModel: no database table. Uses ir.config_parameter for storage.
    """

    _name = "plasticos.commission.config"
    _description = "PlasticOS Commission Configuration"

    _ICP_MAX_BUDGET_TOKENS = "plasticos.commission.max_budget_tokens"
    _ICP_MAX_TOKENS_LEGACY = "plasticos.commission.max_tokens"

    @api.model
    def get_max_budget_tokens(self) -> int:
        """Return max_budget_tokens from ICP, falling back to legacy key then default."""
        icp = self.env["ir.config_parameter"].sudo()
        val = icp.get_param(self._ICP_MAX_BUDGET_TOKENS)
        if val:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
        val_legacy = icp.get_param(self._ICP_MAX_TOKENS_LEGACY)
        if val_legacy:
            try:
                return int(val_legacy)
            except (ValueError, TypeError):
                pass
        return 4096

    @api.model
    def set_max_budget_tokens(self, value: int) -> None:
        """Write max_budget_tokens to ICP (both keys for backward compat)."""
        if value <= 0:
            raise ValueError(f"max_budget_tokens must be positive, got {value}")
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(self._ICP_MAX_BUDGET_TOKENS, str(value))
        icp.set_param(self._ICP_MAX_TOKENS_LEGACY, str(value))
