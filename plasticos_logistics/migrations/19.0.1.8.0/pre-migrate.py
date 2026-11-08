"""Permit append-only superseding calibration observations on module upgrade."""

from psycopg2 import sql


def migrate(cr, version):
    """Drop only the legacy one-observation-per-load unique constraint.

    The replacement model constraint is created by Odoo after this pre-migration
    and preserves duplicate protection at `(load_id, observed_at)` while allowing
    attributed superseding observations.
    """
    # A database upgrading from a revision that predates this model has no
    # calibration table yet. A hard-coded ``::regclass`` cast would raise
    # UndefinedTable and abort the whole plasticos_logistics upgrade before
    # Odoo could create the table, so resolve the name safely first.
    cr.execute("SELECT to_regclass('plasticos_freight_calibration_observation')")
    if cr.fetchone()[0] is None:
        return
    cr.execute(
        """
        SELECT conname
          FROM pg_constraint
         WHERE conrelid = to_regclass('plasticos_freight_calibration_observation')
           AND contype = 'u'
           AND pg_get_constraintdef(oid) = 'UNIQUE (load_id)'
        """
    )
    for (constraint_name,) in cr.fetchall():
        cr.execute(
            sql.SQL("ALTER TABLE {} DROP CONSTRAINT {}").format(
                sql.Identifier("plasticos_freight_calibration_observation"), sql.Identifier(constraint_name)
            )
        )
