"""Re-apply identical cofounder admin groups (ib@ + ab@) after 19.0.1.2.4."""

import logging

from odoo import SUPERUSER_ID
from odoo.api import Environment

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = Environment(cr, SUPERUSER_ID, {})
    _logger.info(
        "plasticos_security_base 19.0.1.2.4 post-migrate: sync cofounder seed group grants",
    )
    cr.execute(
        """
        UPDATE res_users
        SET share = false
        WHERE login IN ('ib@scrapmanagement.com', 'ab@scrapmanagement.com')
        """
    )
    from odoo.addons.plasticos_security_base import hooks

    hooks.grant_seed_user_groups(env)
