"""Post-migration: retire the legacy ERP CSV partner-import UI records.

The Settings block (Corporate / Facility CSV paths and the "Run Legacy ERP
Partner Import" button) and the wizard window action / form view were removed
from the module data files. A database that already persisted them keeps the
records until something drops them: Odoo's ``ir.model.data._process_end``
unlinks stale non-noupdate xmlids of an updated module during this same
upgrade, and this migration retires the same records explicitly and
idempotently so the outcome does not depend on load ordering, and is logged.

Deliberately untouched: the ``ir.config_parameter`` values
``plasticos_partner_import.default_corporate_csv`` /
``plasticos_partner_import.default_facility_csv`` (the importer service still
honours them from the shell) and every importer code path.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_RETIRED_XML_IDS = (
    "res_config_settings_view_form_partner_import",  # ir.ui.view — Settings block
    "action_partner_import_wizard",  # ir.actions.act_window — wizard launcher
    "view_partner_import_wizard_form",  # ir.ui.view — wizard form
)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xml_id in _RETIRED_XML_IDS:
        record = env.ref(f"plasticos_partner_import.{xml_id}", raise_if_not_found=False)
        if record:
            record.unlink()
            _logger.info("plasticos_partner_import 19.0.2.10.23: retired legacy CSV import UI record %s", xml_id)
