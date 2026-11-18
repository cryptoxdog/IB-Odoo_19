"""Backfill one requested delivery appointment per sale order that already asked.

ADR-135 §5. Idempotent: a load that already has a requested, proposed or accepted
delivery appointment is left alone. Counts are logged. Schedule defaults are
inserted into ir.config_parameter only when the key is absent.
"""

import importlib.util
import logging
import sys
from pathlib import Path

_logger = logging.getLogger(__name__)
_VERSION = "19.0.1.16.0"


def _schedule():
    path = Path(__file__).resolve().parents[2] / "schedule_window.py"
    spec = importlib.util.spec_from_file_location("plasticos_logistics_schedule_window", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _seed_parameters(cr, defaults):
    inserted = 0
    for key, value in defaults:
        cr.execute("SELECT 1 FROM ir_config_parameter WHERE key = %s", (key,))
        if cr.fetchone():
            continue
        cr.execute(
            """
            INSERT INTO ir_config_parameter (key, value, create_uid, create_date, write_uid, write_date)
            VALUES (%s, %s, 1, (NOW() AT TIME ZONE 'UTC'), 1, (NOW() AT TIME ZONE 'UTC'))
            """,
            (key, value),
        )
        inserted += 1
    return {"parameters_seen": len(defaults), "parameters_inserted": inserted}


def _backfill(cr, planner):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'sale_order' AND column_name = 'appointment_requested'
        """
    )
    if not cr.fetchone():
        return {"rows_seen": 0, "rows_created": 0, "already_present": 0, "skipped_no_load": 0, "column_absent": 1}
    cr.execute(
        """
        SELECT so.id, l.id
          FROM sale_order so
          LEFT JOIN plasticos_load l ON l.sale_order_id = so.id
         WHERE so.appointment_requested IS TRUE
         ORDER BY so.id, l.id
        """
    )
    grouped = {}
    for sale_id, load_id in cr.fetchall():
        bucket = grouped.setdefault(sale_id, [])
        if load_id:
            bucket.append(load_id)
    cr.execute(
        """
        SELECT load_id
          FROM plasticos_load_appointment
         WHERE side = 'delivery' AND state IN ('requested', 'proposed', 'accepted')
        """
    )
    existing = {row[0] for row in cr.fetchall()}
    orders = [
        {"sale_order_id": sale_id, "load_ids": load_ids, "existing_delivery_load_ids": sorted(existing)}
        for sale_id, load_ids in grouped.items()
    ]
    plans, counts = planner(orders)
    created = 0
    for plan in plans:
        note = f"Backfilled from sale order {plan['sale_order_id']} appointment_requested"
        cr.execute(
            """
            INSERT INTO plasticos_load_appointment (
                load_id, company_id, side, state, arranged_by, note,
                create_uid, write_uid, create_date, write_date
            )
            SELECT l.id, l.company_id, 'delivery', 'requested', 'us', %s,
                   1, 1, (NOW() AT TIME ZONE 'UTC'), (NOW() AT TIME ZONE 'UTC')
              FROM plasticos_load l
             WHERE l.id = %s
               AND NOT EXISTS (
                    SELECT 1
                      FROM plasticos_load_appointment a
                     WHERE a.load_id = l.id
                       AND a.side = 'delivery'
                       AND a.state IN ('requested', 'proposed', 'accepted')
               )
            """,
            (note, plan["load_id"]),
        )
        created += cr.rowcount
    counts["rows_created"] = created
    return counts


def migrate(cr, version):
    if not version:
        return
    module = _schedule()
    parameters = _seed_parameters(cr, module.PARAMETER_DEFAULTS)
    cr.execute("SELECT to_regclass('public.plasticos_load_appointment')")
    if not cr.fetchone()[0]:
        _logger.info("plasticos_logistics %s appointment backfill skipped; table absent; %s", _VERSION, parameters)
        return
    counts = _backfill(cr, module.plan_appointment_backfill)
    _logger.info("plasticos_logistics %s appointment backfill %s parameters %s", _VERSION, counts, parameters)
