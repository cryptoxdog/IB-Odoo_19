"""Set the Trade Role tags of existing companies from their ranks (ADR-131).

19.0.5.5.0 adds the Trade Role tag group (Buyer / Supplier). The module's data
file has already moved the existing ``plasticos_crm_bridge`` Buyer and Supplier
tags into it. This sets each company's Trade Role tags from its native
``customer_rank`` / ``supplier_rank`` (both ranks -> both tags) and mirrors them
onto its sites, in batches of 1000 ids. ``company_role`` is not touched. A
second run changes nothing.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

BATCH = 1000


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {"active_test": False, "tracking_disable": True})
    partners = env["res.partner"]
    ids = partners.search(
        [("company_type", "=", "company"), "|", ("customer_rank", ">", 0), ("supplier_rank", ">", 0)], order="id"
    ).ids
    for start in range(0, len(ids), BATCH):
        partners.browse(ids[start : start + BATCH])._plasticos_sync_trade_role_tags()
        env.flush_all()
        env.invalidate_all()
    _logger.info("post-migrate 19.0.5.5.0: Trade Role tags set from ranks on %d companies", len(ids))
