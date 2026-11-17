"""Recompute the Trade Role badge from the native ranks (ADR-131 Decision B).

19.0.5.5.0 makes ``res.partner.company_role`` a stored compute of the commercial
partner's ``customer_rank`` / ``supplier_rank`` (Buyer, Supplier, Both). Stored
rows are not recomputed on upgrade, so this does, in batches of 1000 ids.
Carrier, Broker, Internal, Prospect and Other stay where neither rank is set.
The Company Type and Status tag groups are handled by the module's data file,
which runs on every install and upgrade. A second run writes the same values.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

BATCH = 1000


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {"active_test": False, "tracking_disable": True})
    partners = env["res.partner"]
    field = partners._fields["company_role"]
    ids = partners.search([], order="id").ids
    for start in range(0, len(ids), BATCH):
        env.add_to_compute(field, partners.browse(ids[start : start + BATCH]))
        env.flush_all()
        env.invalidate_all()
    cr.execute("SELECT company_role, count(*) FROM res_partner GROUP BY company_role ORDER BY company_role")
    counts = ", ".join(f"{role}={total}" for role, total in cr.fetchall())
    _logger.info("post-migrate 19.0.5.5.0: recomputed company_role on %d partners (%s)", len(ids), counts)
