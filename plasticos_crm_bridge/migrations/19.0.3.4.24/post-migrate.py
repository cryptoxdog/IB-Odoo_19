"""Move opportunities off the VanillaSoft stages onto the native CRM stages.

The named stage xmlids are the only rows rewritten. Dead Lead has no native
stage, so those opportunities move to native New. Nothing else is backfilled.
"""

import logging

_logger = logging.getLogger(__name__)

# VanillaSoft xmlid name -> native crm.stage xmlid.
STAGE_REMAP = {
    "stage_new": "crm.stage_lead1",
    "stage_qualified_hot": "crm.stage_lead2",
    "stage_qualified_warm": "crm.stage_lead2",
    "stage_resistant": "crm.stage_lead3",
    "stage_active_supplier": "crm.stage_lead4",
    "stage_dead_lead": "crm.stage_lead1",
}


def _stage_id(cr, xmlid):
    module, name = xmlid.split(".", 1)
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
        WHERE module = %s AND name = %s AND model = 'crm.stage'
        """,
        (module, name),
    )
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    if not version:
        return
    for source_name, target_xmlid in STAGE_REMAP.items():
        source_id = _stage_id(cr, f"plasticos_crm_bridge.{source_name}")
        target_id = _stage_id(cr, target_xmlid)
        if not source_id or not target_id or source_id == target_id:
            _logger.info(
                "plasticos_crm_bridge 19.0.3.4.24: skip %s -> %s (source=%s target=%s)",
                source_name,
                target_xmlid,
                source_id,
                target_id,
            )
            continue
        cr.execute("UPDATE crm_lead SET stage_id = %s WHERE stage_id = %s", (target_id, source_id))
        _logger.info(
            "plasticos_crm_bridge 19.0.3.4.24: moved %s opportunities from %s to %s",
            cr.rowcount,
            source_name,
            target_xmlid,
        )
