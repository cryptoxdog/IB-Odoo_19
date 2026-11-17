"""Drop the retired equipment-type column on facility material rules (ADR-134 §10).

The module is optional and uninstalled on production. When the table exists,
the old column is removed after the field was renamed to capability_type_id.
A second run finds the column gone and changes nothing.
"""

import logging

_logger = logging.getLogger(__name__)

_TABLE = "plasticos_facility_material_rule"


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = %s
           AND column_name = 'equipment_type_id'
        """,
        (_TABLE,),
    )
    if cr.fetchone() is None:
        _logger.info("semantic kernel 19.0.1.0.6: equipment_type_id already absent; columns_dropped=0")
        return
    cr.execute("ALTER TABLE plasticos_facility_material_rule DROP COLUMN equipment_type_id")
    _logger.info("semantic kernel 19.0.1.0.6 counts: columns_dropped=1")
