"""Split one web-lead material code into a form or a material grade.

Pure: no Odoo import. Form and grade come from the catalog the caller built
from the live master rows.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from .material_catalog import CatalogEntry, accept_value, match_one


def split_material_code(code: str | None, grade_codes: Collection[str]) -> tuple[str | None, str | None]:
    """Return (form_code, material_grade_code) for one material code."""
    normalized = (code or "").strip().upper()
    if not normalized:
        return None, None
    if normalized in grade_codes:
        return None, normalized
    return normalized, None


def merge_form_and_grade(
    ai_form: str | None,
    declared_text: str | None,
    vision_form: str | None,
    form_entries: Sequence[CatalogEntry],
    grade_entries: Sequence[CatalogEntry],
) -> tuple[str | None, str | None]:
    """Return (form_code, material_grade_code) when a submission has both facts.

    A grade never occupies the form slot. Seller text fills an empty slot from
    that kind's catalog only. A vision form fills an empty form slot and does
    not replace a form the text AI already named.
    """
    form_code = accept_value(ai_form, form_entries)
    grade_code = None if form_code else accept_value(ai_form, grade_entries)
    if not grade_code:
        grade_code = match_one(declared_text, grade_entries)
    if not form_code:
        form_code = match_one(declared_text, form_entries)
    if vision_form and not form_code:
        seen_form = accept_value(vision_form, form_entries)
        seen_grade = accept_value(vision_form, grade_entries)
        if seen_form:
            form_code = seen_form
        elif seen_grade and not grade_code:
            grade_code = seen_grade
    return form_code, grade_code
