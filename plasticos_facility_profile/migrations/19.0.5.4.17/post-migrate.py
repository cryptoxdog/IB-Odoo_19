"""Recompute the stored Contact type and facility gate for the Site shape.

19.0.5.4.17 adds ``site`` to the stored ``res.partner.company_type`` and moves
``company_type`` and ``is_facility`` onto the site predicate (a partner with a
parent that is a delivery/invoice address or a company: ADR-131). Their new
dependencies do not recompute the stored rows on upgrade, so this does, in
batches of 1000 ids. It changes no other partner value: ``company_type`` is
recomputed without its inverse. A second run writes the same values.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

BATCH = 1000
FIELDS = ("company_type", "is_facility")


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {"active_test": False, "tracking_disable": True})
    partners = env["res.partner"]
    ids = partners.search([], order="id").ids
    for start in range(0, len(ids), BATCH):
        chunk = partners.browse(ids[start : start + BATCH])
        for name in FIELDS:
            env.add_to_compute(partners._fields[name], chunk)
        env.flush_all()
        env.invalidate_all()
    cr.execute("SELECT company_type, count(*) FROM res_partner GROUP BY company_type ORDER BY company_type")
    counts = ", ".join(f"{kind}={total}" for kind, total in cr.fetchall())
    _logger.info(
        "post-migrate 19.0.5.4.17: recomputed company_type and is_facility on %d partners (%s)", len(ids), counts
    )
