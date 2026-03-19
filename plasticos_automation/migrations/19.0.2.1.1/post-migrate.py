"""Re-apply Settings → automation group merge after XML patch removal (Odoo 19 Apps access)."""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.plasticos_automation.hooks import _merge_automation_groups_into_settings

    _merge_automation_groups_into_settings(env)
    _logger.info(
        "post-migrate 19.0.2.1.1: ensured automation groups implied by base.group_system",
    )
