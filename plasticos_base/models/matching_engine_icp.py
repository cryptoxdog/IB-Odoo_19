"""Buyer matching — GATE_URL availability helpers only.

Not a mixin. Stub / empty-result behavior lives in ``plasticos.buyer.matcher`` only.
The matching UI/cron killswitch is Gate availability (``GATE_URL``), not a
microservice ICP.
"""

from __future__ import annotations

import logging
import os

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ENV_GATE_URL = "GATE_URL"


def matching_engine_is_enabled(env) -> bool:
    """Return True when the Gate hub URL is configured in the environment."""
    del env
    return bool((os.environ.get(ENV_GATE_URL) or "").strip())


def matching_engine_require_enabled_for_ui(env) -> None:
    """Raise UserError when ``GATE_URL`` is unset (buttons / wizards)."""
    if matching_engine_is_enabled(env):
        return
    _logger.info("GATE_URL unset for UI: user=%s", env.uid)
    raise UserError(_("Gate is not configured (GATE_URL is unset)."))


def matching_engine_should_skip_cron(env, cron_name: str) -> bool:
    """True when Gate is unconfigured — caller should skip cron work."""
    if matching_engine_is_enabled(env):
        return False
    _logger.warning("GATE_URL unset; skipping cron=%s", cron_name)
    return True
