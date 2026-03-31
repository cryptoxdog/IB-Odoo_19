"""Buyer matching engine — ICP flag helpers only.

Not a mixin. Stub / empty-result behavior lives in ``plasticos.buyer.matcher`` only.
"""

from __future__ import annotations

import logging

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_TRUTHY = frozenset({"true", "1", "yes", "on"})

ICP_MATCHING_ENABLED = "plasticos.matching_engine.enabled"
# Historical key name (data/plasticos_base data); message is shown when matching is disabled.
ICP_MATCHING_USER_MESSAGE = "plasticos.feature_gate.user_message"


def _param_truthy(env, key: str, *, default: str = "False") -> bool:
    if not key.startswith("plasticos."):
        raise ValueError(f"ICP key must be prefixed with \'plasticos.\', got: {key!r}")
    icp = env["ir.config_parameter"].sudo()
    if not key.startswith("plasticos."):
        raise ValueError(f"ICP key must be prefixed with 'plasticos.', got: {key!r}")
    raw = (icp.get_param(key, default) or default).strip().lower()
    return raw in _TRUTHY


def matching_engine_is_enabled(env) -> bool:
    """Return True if buyer matching engine is enabled (ICP)."""
    return _param_truthy(env, ICP_MATCHING_ENABLED, default="False")


def matching_engine_require_enabled_for_ui(env) -> None:
    """Raise UserError when the matching engine is off (buttons / wizards)."""
    if matching_engine_is_enabled(env):
        return
    icp = env["ir.config_parameter"].sudo()
    message = icp.get_param(
        ICP_MATCHING_USER_MESSAGE,
        _("This isn't ready - come back in 5 minutes!"),
    )
    _logger.info("Matching engine disabled for UI: user=%s", env.uid)
    raise UserError(message)


def matching_engine_should_skip_cron(env, cron_name: str) -> bool:
    """True when matching is disabled — caller should skip cron work."""
    if matching_engine_is_enabled(env):
        return False
    _logger.warning("Matching engine disabled; skipping cron=%s", cron_name)
    return True
