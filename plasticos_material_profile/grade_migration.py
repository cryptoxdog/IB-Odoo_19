"""Move the six former forms onto material grades during the grade upgrade.

Each module's post-migrate calls these helpers on its own tables. They copy
values and count them; they issue no ALTER TABLE. Odoo's end-of-upgrade cleanup
drops the ``origin_form_id`` column and unlinks the six form records, and that
unlink fails on any remaining ``ondelete="restrict"`` link, so every helper
raises before then when a link is left behind.
"""

import logging

from odoo.tools import SQL
from odoo.tools.sql import column_exists

from .grade_codes import FORMER_FORM_CODES, GRADE_CODES

_logger = logging.getLogger(__name__)

ORIGIN_COLUMN = "origin_form_id"


class GradeMigrationError(RuntimeError):
    """A grade migration left a value it could not account for."""


def origin_note(form):
    return f"Origin form: {form.name}"


def _append_line(text, line):
    if line in (text or "").splitlines():
        return text
    return f"{text}\n{line}" if text else line


def _model(env, model_name):
    return env[model_name].with_context(active_test=False, tracking_disable=True, mail_notrack=True)


def former_forms(env):
    return _model(env, "plasticos.material.form").search([("code", "in", list(FORMER_FORM_CODES))])


def grades_by_code(env):
    grades = {grade.code: grade for grade in _model(env, "plasticos.material.grade").search([])}
    missing = sorted(set(GRADE_CODES) - set(grades))
    if missing:
        raise GradeMigrationError(f"Material grades are not seeded: {', '.join(missing)}")
    return grades


def origin_forms(env, table):
    """Map record id to its ``origin_form_id`` form, or return None once the column is gone."""
    cr = env.cr
    if not column_exists(cr, table, ORIGIN_COLUMN):
        return None
    cr.execute(
        SQL(
            "SELECT id, %s FROM %s WHERE %s IS NOT NULL",
            SQL.identifier(ORIGIN_COLUMN),
            SQL.identifier(table),
            SQL.identifier(ORIGIN_COLUMN),
        )
    )
    rows = cr.fetchall()
    forms = _model(env, "plasticos.material.form").browse({form_id for _record_id, form_id in rows})
    by_id = {form.id: form for form in forms}
    return {record_id: by_id[form_id] for record_id, form_id in rows}


def move_former_forms(env, model_name, notes_field=None, replacement_form_code=None):
    """Set the grade from a former form or the origin form, then clear or replace the form.

    A former form wins over the origin form; a disagreeing origin form, or one
    with no grade code, is appended to ``notes_field``. Records that already
    have a grade keep it. Returns ``(moved, copied, noted)`` and raises when an
    origin row is neither copied nor noted, or a former form is still linked.
    """
    Model = _model(env, model_name)
    grades = grades_by_code(env)
    former = former_forms(env)
    replacement = Model.browse()
    if replacement_form_code:
        replacement = _model(env, "plasticos.material.form").search([("code", "=", replacement_form_code)], limit=1)
        if not replacement:
            raise GradeMigrationError(f"Replacement form {replacement_form_code} is not seeded.")
    origins = origin_forms(env, Model._table)
    if origins is None:
        _logger.info("%s: %s is already gone; origin copy skipped", model_name, ORIGIN_COLUMN)
        origins = {}
    if origins and not notes_field:
        raise GradeMigrationError(f"{model_name} has origin forms but no notes field.")

    domain = [("form_id", "in", former.ids)]
    if origins:
        domain = ["|", *domain, ("id", "in", list(origins))]
    moved = 0
    for record in Model.search(domain):
        vals = {}
        form_code = record.form_id.code if record.form_id in former else None
        origin = origins.get(record.id)
        origin_code = origin.code if origin else None
        grade_code = form_code or (origin_code if origin_code in grades else None)
        if grade_code and not record.material_grade_id:
            vals["material_grade_id"] = grades[grade_code].id
        if form_code:
            vals["form_id"] = replacement.id or False
            moved += 1
        if origin and (origin_code not in grades or (form_code and origin_code != form_code)):
            notes = _append_line(record[notes_field], origin_note(origin))
            if notes != record[notes_field]:
                vals[notes_field] = notes
        if vals:
            record.write(vals)

    copied = noted = 0
    for record_id, origin in origins.items():
        record = Model.browse(record_id)
        if record.material_grade_id.code == origin.code:
            copied += 1
        elif origin_note(origin) in (record[notes_field] or "").splitlines():
            noted += 1
    if copied + noted != len(origins):
        raise GradeMigrationError(
            f"{model_name}: {len(origins)} origin forms, {copied} copied and {noted} noted; the counts differ."
        )
    remaining = Model.search_count([("form_id", "in", former.ids)])
    if remaining:
        raise GradeMigrationError(f"{model_name}: {remaining} records still link a former form.")
    _logger.info(
        "%s: %s former forms moved to grades, %s origin forms copied, %s noted", model_name, moved, copied, noted
    )
    return moved, copied, noted


def clear_former_form_links(env, model_name, field_name):
    """Clear ``field_name`` where it points at a former form; return the cleared ids."""
    Model = _model(env, model_name)
    records = Model.search([(field_name, "in", former_forms(env).ids)])
    cleared = records.ids
    if records:
        records.write({field_name: False})
    for record_id in cleared:
        _logger.info("%s %s: cleared %s that pointed at a former form", model_name, record_id, field_name)
    return cleared
