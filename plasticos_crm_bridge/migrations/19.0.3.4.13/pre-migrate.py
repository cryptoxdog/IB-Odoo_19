"""Adopt Buyer and Supplier tags before this version's XML seed runs.

Runs on upgrade only. Fresh installation uses the same helper from module data.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_ROLE_TAGS = (
    ("Buyer", "plasticos_crm_bridge.crm_tag_buyer"),
    ("Supplier", "plasticos_crm_bridge.crm_tag_supplier"),
)


def migrate(cr, version):
    if not version:
        return
    from odoo.addons.plasticos_crm_bridge.models.crm_tag_adoption import adopt_role_tag  # noqa: PLC0415

    env = api.Environment(cr, SUPERUSER_ID, {})
    for name, xmlid in _ROLE_TAGS:
        adopted = adopt_role_tag(env, name, xmlid)
        _logger.info("CRM role tag %s adoption before seed: %s", name, adopted)
