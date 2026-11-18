"""Map stored sweep process-type filters onto capability-type codes (ADR-134).

The old equipment-type id list cannot be mapped after that table is dropped,
so it is deleted and the new capability filter starts empty. Counts are logged.
"""

import json
import logging

_logger = logging.getLogger(__name__)

_PROCESS_KEY = "plasticos.gate.sweep_process_types"
_OLD_EQUIPMENT_KEY = "plasticos.gate.sweep_equipment_type_ids"
_PROCESS_TO_CAPABILITY = {
    "blow_mold": "blow_molding",
    "compounding": "compounding",
    "compression_mold": "compression_molding",
    "extrusion": "extrusion",
    "film_blown": "film_blowing",
    "film_cast": "film_casting",
    "injection": "injection_molding",
    "rotomold": "rotomolding",
    "thermoform": "thermoforming",
}


def migrate(cr, version):
    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (_PROCESS_KEY,))
    row = cr.fetchone()
    mapped = 0
    dropped = 0
    if row and row[0]:
        raw = row[0].strip()
        try:
            items = (
                json.loads(raw) if raw.startswith("[") else [part.strip() for part in raw.split(",") if part.strip()]
            )
        except json.JSONDecodeError:
            items = []
        codes = []
        for item in items:
            if item in _PROCESS_TO_CAPABILITY:
                codes.append(_PROCESS_TO_CAPABILITY[item])
                mapped += 1
            elif item in _PROCESS_TO_CAPABILITY.values():
                codes.append(item)
            else:
                dropped += 1
        stored = json.dumps(sorted(set(codes))) if codes else ""
        cr.execute("UPDATE ir_config_parameter SET value = %s WHERE key = %s", (stored, _PROCESS_KEY))
    cr.execute("DELETE FROM ir_config_parameter WHERE key = %s", (_OLD_EQUIPMENT_KEY,))
    equipment_deleted = cr.rowcount
    _logger.info(
        "enrichment sweep filter migration 19.0.2.7.3 counts: process_mapped=%s process_dropped=%s equipment_params_deleted=%s",
        mapped,
        dropped,
        equipment_deleted,
    )
