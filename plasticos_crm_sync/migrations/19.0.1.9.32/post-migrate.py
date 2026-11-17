"""Backfill the VanillaSoft Company Type CRM tags on existing leads (C1 F1).

``plasticos_crm_bridge`` now carries one ``crm.tag`` per Company Type, and the
sync writes it on every lead it touches. This puts it on the leads imported
before: the recorded ``VanillaSoft Company Type: X`` paragraph of each lead's
description is the source. Idempotent; logs set / already set / no source
value / unmapped.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    counts = env["crm.lead"]._plasticos_backfill_company_type_tags()
    _logger.info("post-migrate 19.0.1.9.32: Company Type CRM tags %s", counts)
