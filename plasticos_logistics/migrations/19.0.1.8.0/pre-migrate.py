"""Permit append-only superseding calibration observations on module upgrade."""

from psycopg2 import sql


def migrate(cr, version):
    """Drop only the legacy one-observation-per-load unique constraint.

    The replacement model constraint is created by Odoo after this pre-migration
    and preserves duplicate protection at `(load_id, observed_at)` while allowing
    attributed superseding observations.
    """
    cr.execute(
        """
        SELECT conname
          FROM pg_constraint
         WHERE conrelid = 'plasticos_freight_calibration_observation'::regclass
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
