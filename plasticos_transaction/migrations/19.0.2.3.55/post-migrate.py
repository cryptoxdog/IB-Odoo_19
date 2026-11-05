"""Verify the native order binding the Opportunity hand-off relies on.

Runs on upgrade only. ``sale.order.opportunity_id`` comes from ``sale_crm``,
which Odoo auto-installs beside ``sale`` and ``crm``. The hand-off stops at
runtime when the column is absent; this step only records that state so an
operator sees it before the first acceptance. No data is changed.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT state FROM ir_module_module WHERE name = 'sale_crm'")
    row = cr.fetchone()
    state = row[0] if row else "absent"
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = 'sale_order' AND column_name = 'opportunity_id'"
    )
    has_column = bool(cr.fetchone())
    if has_column:
        _logger.info("plasticos_transaction 19.0.2.3.55: sale.order.opportunity_id present (sale_crm %s)", state)
    else:
        _logger.warning(
            "plasticos_transaction 19.0.2.3.55: sale.order.opportunity_id missing (sale_crm %s); "
            "offer acceptance will refuse to create a quotation until sale_crm is installed",
            state,
        )
