"""Project the Other polymer onto the stored code and retire the Sheet material grade."""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

SHEET_GRADE = "plasticos_material_profile.material_grade_sheet"


def _backfill_other_polymer(cr):
    cr.execute(
        """
        UPDATE plasticos_material_profile mp
        SET polymer = p.code
        FROM plasticos_polymer p
        WHERE mp.polymer_id = p.id
          AND p.code = 'OTHER'
          AND mp.polymer IS NULL
        """
    )
    _logger.info("Backfilled polymer code OTHER on %s material profiles.", cr.rowcount)


def _grade_references(cr, grade_id):
    cr.execute(
        """
        SELECT src.relname, att.attname
        FROM pg_constraint con
        JOIN pg_class src ON src.oid = con.conrelid
        JOIN pg_class dst ON dst.oid = con.confrelid
        JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
        WHERE con.contype = 'f' AND dst.relname = 'plasticos_material_grade'
        """
    )
    total = 0
    for table, column in cr.fetchall():
        cr.execute(
            SQL("SELECT count(*) FROM %s WHERE %s = %s", SQL.identifier(table), SQL.identifier(column), grade_id)
        )
        total += cr.fetchone()[0]
    return total


def _retire_sheet_grade(env):
    grade = env.ref(SHEET_GRADE, raise_if_not_found=False)
    if not grade:
        return
    references = _grade_references(env.cr, grade.id)
    if references:
        grade.active = False
        _logger.warning(
            "Archived the Sheet material grade; %s records still reference it. Sheet stays a form.", references
        )
        return
    grade.unlink()
    _logger.info("Removed the Sheet material grade; Sheet stays a form.")


def migrate(cr, version):
    _backfill_other_polymer(cr)
    _retire_sheet_grade(api.Environment(cr, SUPERUSER_ID, {}))
