"""Copy retired quality-tier selections and profile letters before those columns drop.

The module update removes ``quality_tier`` and ``sub_grade``. This runs first
and keeps the values for the 19.0.5.13.0 post-migrate.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS plasticos_quality_tier_migration (
            res_model VARCHAR NOT NULL,
            res_id INTEGER NOT NULL,
            old_tier VARCHAR,
            old_sub_grade VARCHAR,
            PRIMARY KEY (res_model, res_id)
        )
        """
    )
    _snapshot_profile(cr)
    _snapshot_template(cr)


def _columns(cr, table):
    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = %s
           AND column_name IN ('quality_tier', 'sub_grade')
        """,
        (table,),
    )
    return {row[0] for row in cr.fetchall()}


def _snapshot_profile(cr):
    present = _columns(cr, "plasticos_material_profile")
    if not present:
        return
    if present == {"quality_tier", "sub_grade"}:
        cr.execute(
            """
            INSERT INTO plasticos_quality_tier_migration (res_model, res_id, old_tier, old_sub_grade)
            SELECT 'plasticos.material.profile', id, quality_tier, sub_grade
              FROM plasticos_material_profile
            ON CONFLICT (res_model, res_id) DO NOTHING
            """
        )
    elif present == {"quality_tier"}:
        cr.execute(
            """
            INSERT INTO plasticos_quality_tier_migration (res_model, res_id, old_tier, old_sub_grade)
            SELECT 'plasticos.material.profile', id, quality_tier, NULL
              FROM plasticos_material_profile
            ON CONFLICT (res_model, res_id) DO NOTHING
            """
        )
    else:
        cr.execute(
            """
            INSERT INTO plasticos_quality_tier_migration (res_model, res_id, old_tier, old_sub_grade)
            SELECT 'plasticos.material.profile', id, NULL, sub_grade
              FROM plasticos_material_profile
            ON CONFLICT (res_model, res_id) DO NOTHING
            """
        )
    _logger.info("Snapshotted quality tier columns on %s material profiles.", cr.rowcount)


def _snapshot_template(cr):
    if "quality_tier" not in _columns(cr, "plasticos_grade_template"):
        return
    cr.execute(
        """
        INSERT INTO plasticos_quality_tier_migration (res_model, res_id, old_tier, old_sub_grade)
        SELECT 'plasticos.grade.template', id, quality_tier, NULL
          FROM plasticos_grade_template
        ON CONFLICT (res_model, res_id) DO NOTHING
        """
    )
    _logger.info("Snapshotted quality tier columns on %s grade templates.", cr.rowcount)
