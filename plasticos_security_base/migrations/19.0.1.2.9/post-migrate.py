"""Re-home load-dashboard ir.rule XML ids from plasticos_logistics → this module."""

import logging

_logger = logging.getLogger(__name__)

_RULE_XMLIDS = (
    "rule_load_dashboard_rep_own",
    "rule_load_dashboard_logistics_all",
    "rule_load_dashboard_ops_manager_all",
)


def migrate(cr, version):
    """Preserve upgraded DBs: same xml id names, new owning module."""
    _logger.info(
        "plasticos_security_base 19.0.1.2.9: reassign load-dashboard rule xmlids",
    )
    cr.execute(
        """
        UPDATE ir_model_data
           SET module = 'plasticos_security_base'
         WHERE module = 'plasticos_logistics'
           AND name = ANY(%s)
        """,
        [list(_RULE_XMLIDS)],
    )
