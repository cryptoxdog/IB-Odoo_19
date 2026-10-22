"""Grant Mack the sales-rep groups the owner fallback requires.

Blank VanillaSoft owners, and the ss@ / va@ / sales5@ / nc@ aliases, resolve to
sales2@scrapmanagement.com. That user was seeded without the sales-rep groups
the other representatives receive.
"""

import logging

from odoo import SUPERUSER_ID
from odoo.api import Environment

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = Environment(cr, SUPERUSER_ID, {})
    _logger.info("plasticos_security_base 19.0.1.2.21: grant seed salesperson groups, including Mack")
    from odoo.addons.plasticos_security_base import hooks

    hooks.grant_seed_user_groups(env)
