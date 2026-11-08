"""Post-migration: remove the manual VanillaSoft CRM-lead CSV import.

The wizard, its service and its view were the old manual VanillaSoft path
(odoo-intent-1 ingestion milestone: plasticos_crm_sync's API orchestrator is
the single authoritative path). The menus were already dropped by
19.0.2.7.1; this migration deletes the orphaned wizard action XML ID so no
stale reference to the removed wizard model survives the upgrade.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_REMOVED_XML_IDS = ("action_crm_lead_import_wizard",)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xml_id in _REMOVED_XML_IDS:
        record = env.ref(f"plasticos_partner_import.{xml_id}", raise_if_not_found=False)
        if record:
            record.unlink()
            _logger.info("Removed orphaned manual-import action %s", xml_id)
