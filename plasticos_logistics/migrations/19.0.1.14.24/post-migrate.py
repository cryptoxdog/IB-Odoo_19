"""S11 (OP11-E03, F6): move the Linda load-sweep cursor out of ir.config_parameter.

Before S11 each sweep lane kept its cursor in the system parameter
``plasticos_logistics.linda_load_sweep_cursor.<lane>``. The sweep now keeps it in
``plasticos.linda.sweep.cursor``, one row per lane and company. This step copies
each stored value once into the row of the company the sweep ran in (the
``plasticos_base.user_system_cron`` company, else the main company), then
removes the old parameter so nothing reads or writes it again. A value that is
not a load id is dropped and the lane restarts from the first load, exactly as
the old code treated it. A rerun finds no parameter and changes nothing.
"""

import logging

_logger = logging.getLogger(__name__)

PREFIX = "plasticos_logistics.linda_load_sweep_cursor."
LANES = ("ack", "chase")


def _sweep_company(cr):
    cr.execute(
        """
        SELECT u.company_id
          FROM ir_model_data d
          JOIN res_users u ON u.id = d.res_id
         WHERE d.module = 'plasticos_base' AND d.name = 'user_system_cron' AND d.model = 'res.users'
        """
    )
    row = cr.fetchone()
    if row and row[0]:
        return row[0]
    cr.execute("SELECT res_id FROM ir_model_data WHERE module = 'base' AND name = 'main_company'")
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT key, value FROM ir_config_parameter WHERE key = ANY(%s)", ([PREFIX + lane for lane in LANES],))
    stored = dict(cr.fetchall())
    if not stored:
        return
    company_id = _sweep_company(cr)
    moved = 0
    for key, value in sorted(stored.items()):
        lane = key[len(PREFIX) :]
        position = int(value) if (value or "").isdigit() else 0
        if company_id:
            cr.execute(
                """
                INSERT INTO plasticos_linda_sweep_cursor
                    (lane, company_id, last_load_id, create_uid, write_uid, create_date, write_date)
                VALUES (%s, %s, %s, 1, 1, now() at time zone 'UTC', now() at time zone 'UTC')
                ON CONFLICT (lane, company_id) DO NOTHING
                """,
                (lane, company_id, position),
            )
            moved += cr.rowcount
    cr.execute("DELETE FROM ir_config_parameter WHERE key = ANY(%s)", (list(stored),))
    _logger.info(
        "S11 Linda sweep cursor: %s lane(s) moved to company %s; %s parameter(s) removed",
        moved,
        company_id,
        cr.rowcount,
    )
