"""Re-home load-dashboard ir.rule XML ids before security_base data load.

Logistics updates first (security_base depends on it) and no longer ships those
rules. On Staging upgrades, reassign ownership *before* this module's XML runs
so noupdate/update paths bind to the surviving ir.rule rows when still present.
"""

import logging

_logger = logging.getLogger(__name__)

_RULE_XMLIDS = (
    "rule_load_dashboard_rep_own",
    "rule_load_dashboard_logistics_all",
    "rule_load_dashboard_ops_manager_all",
)


def migrate(cr, version):
    _logger.info(
        "plasticos_security_base 19.0.1.2.10: pre-reassign load-dashboard rule xmlids",
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
