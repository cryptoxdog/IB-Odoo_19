"""Re-apply admin group grants on every plasticos_base upgrade.

Odoo only runs post_init_hook on *install*, not on *upgrade*. Without this
migration, ib@ / ab@ can lose or never receive base.group_system after DB
restores or manual group edits. This script calls the same logic as post_init_hook.
"""

import logging

from odoo import SUPERUSER_ID
from odoo.api import Environment

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = Environment(cr, SUPERUSER_ID, {})
    _logger.info("plasticos_base 19.0.1.1.3 post-migrate: re-applying admin/cron group grants")
    # Ensure ScrapManagement admins are internal users (not portal) — required for Apps / Settings
    cr.execute(
        """
        UPDATE res_users
        SET share = false
        WHERE login IN ('ib@scrapmanagement.com', 'ab@scrapmanagement.com')
        """
    )
    from odoo.addons.plasticos_base import hooks

    hooks.post_init_hook(env)
