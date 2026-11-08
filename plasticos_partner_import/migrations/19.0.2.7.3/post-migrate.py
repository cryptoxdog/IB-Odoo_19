"""Drop retired partner import menus if they still exist from older builds."""

import logging

_logger = logging.getLogger(__name__)

_MENU_XMLIDS = (
    "plasticos_partner_import.menu_partner_import_wizard",
    "plasticos_partner_import.menu_partner_import_wizard_plasticos",
)


def migrate(cr, version):
    _logger.info("plasticos_partner_import 19.0.2.7.3: remove retired partner import menus")
    for xmlid in _MENU_XMLIDS:
        module, name = xmlid.split(".", 1)
        cr.execute(
            """
            SELECT res_id FROM ir_model_data
             WHERE module = %s AND name = %s AND model = 'ir.ui.menu'
            """,
            (module, name),
        )
        row = cr.fetchone()
        if not row:
            continue
        menu_id = row[0]
        cr.execute("DELETE FROM ir_ui_menu WHERE id = %s", (menu_id,))
        cr.execute(
            "DELETE FROM ir_model_data WHERE module = %s AND name = %s",
            (module, name),
        )
