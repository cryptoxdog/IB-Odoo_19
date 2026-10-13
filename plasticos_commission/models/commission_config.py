"""Commission configuration helpers.

Provides max_budget_tokens with its legacy alias for backward compatibility.
All values are stored in ir.config_parameter — no dedicated table needed.
"""

from __future__ import annotations

import logging

from odoo import api, models
from odoo.exceptions import AccessError

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
        icp = self.env["ir.config_parameter"].sudo()  # sudo: read two fixed commission keys; ICP is settings-only
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
        """Write max_budget_tokens to ICP (both keys for backward compat).

        Public, so reachable over RPC by any authenticated user. Only a
        Settings user may change these global parameters: the caller is
        checked first and the write runs with the caller's own rights, so
        ir.config_parameter's group_system ACL applies to both keys.
        """
        if not self.env.is_system():
            raise AccessError("Only Settings administrators can change the commission token budget.")
        if value <= 0:
            raise ValueError(f"max_budget_tokens must be positive, got {value}")
        icp = self.env["ir.config_parameter"]
        icp.set_param(self._ICP_MAX_BUDGET_TOKENS, str(value))
        icp.set_param(self._ICP_MAX_TOKENS_LEGACY, str(value))
