"""Idempotent re-home of load-dashboard ir.rule XML ids.

Staging dump can have the rules under plasticos_logistics while a prior failed
upgrade left (or XML load created) the same names under plasticos_security_base.
Blind UPDATE then UniqueViolates ir_model_data_module_name_uniq_index.
"""

import logging

_logger = logging.getLogger(__name__)

_RULE_XMLIDS = (
    "rule_load_dashboard_rep_own",
    "rule_load_dashboard_logistics_all",
    "rule_load_dashboard_ops_manager_all",
)


def _rehome_load_dashboard_xmlids(cr, label: str) -> None:
    _logger.info("%s: reassign load-dashboard rule xmlids", label)
    # Conflict with different res_id: drop the logistics ir.rule so it cannot
    # stay active as an orphan after its xmlid is removed. Same res_id: keep
    # the shared rule; only the duplicate logistics xmlid is deleted below.
    cr.execute(
        """
        DELETE FROM ir_rule
         WHERE id IN (
               SELECT logistics.res_id
                 FROM ir_model_data AS logistics
                 JOIN ir_model_data AS sb
                   ON sb.module = 'plasticos_security_base'
                  AND sb.name = logistics.name
                WHERE logistics.module = 'plasticos_logistics'
                  AND logistics.name = ANY(%s)
                  AND logistics.model = 'ir.rule'
                  AND logistics.res_id IS DISTINCT FROM sb.res_id
             )
        """,
        [list(_RULE_XMLIDS)],
    )
    rules_deleted = cr.rowcount
    cr.execute(
        """
        DELETE FROM ir_model_data AS logistics
         WHERE logistics.module = 'plasticos_logistics'
           AND logistics.name = ANY(%s)
           AND EXISTS (
                 SELECT 1
                   FROM ir_model_data AS sb
                  WHERE sb.module = 'plasticos_security_base'
                    AND sb.name = logistics.name
               )
        """,
        [list(_RULE_XMLIDS)],
    )
    deleted = cr.rowcount
    cr.execute(
        """
        UPDATE ir_model_data
           SET module = 'plasticos_security_base'
         WHERE module = 'plasticos_logistics'
           AND name = ANY(%s)
        """,
        [list(_RULE_XMLIDS)],
    )
    _logger.info(
        "%s: orphan_rules_removed=%s conflict_xmlids_removed=%s logistics_reassigned=%s",
        label,
        rules_deleted,
        deleted,
        cr.rowcount,
    )


def migrate(cr, version):
    _rehome_load_dashboard_xmlids(cr, "plasticos_security_base 19.0.1.2.11 pre")
