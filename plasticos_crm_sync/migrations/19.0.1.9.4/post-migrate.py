"""Remove excluded VanillaSoft columns already stored by an older sync.

Runs only when an installed database is upgraded to 19.0.1.9.4. A fresh
install passes an empty version and changes nothing. The cleanup is the same
predicate the runtime filter uses, and a second upgrade finds nothing to write.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import SUPERUSER_ID, api
    from odoo.addons.plasticos_crm_sync.services.orchestrator import purge_legacy_excluded_persistence

    env = api.Environment(cr, SUPERUSER_ID, {})
    counts = purge_legacy_excluded_persistence(env)
    _logger.info(
        "plasticos_crm_sync 19.0.1.9.4 excluded-source cleanup: leads=%s partners=%s table_rows=%s orphans=%s skipped_non_dict=%s",
        counts["leads"],
        counts["partners"],
        counts["table_rows"],
        counts["orphans"],
        counts["skipped_non_dict"],
    )
