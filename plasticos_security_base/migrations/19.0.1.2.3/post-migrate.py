"""Re-apply seed user group grants after fixing admin XML IDs (user_admin_*)."""

import logging

from odoo import SUPERUSER_ID
from odoo.api import Environment

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = Environment(cr, SUPERUSER_ID, {})
    _logger.info(
        "plasticos_security_base 19.0.1.2.3 post-migrate: re-granting seed user groups",
    )
    from odoo.addons.plasticos_security_base import hooks

    hooks.grant_seed_user_groups(env)
