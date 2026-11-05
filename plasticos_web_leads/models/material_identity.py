"""Split one web-lead material code into a form or a material grade.

Pure: no Odoo import. The caller passes the grade registry, so the pure test
tier can use the same ``GRADE_CODES`` as the runtime.
"""

from __future__ import annotations

from collections.abc import Collection


def split_material_code(code: str | None, grade_codes: Collection[str]) -> tuple[str | None, str | None]:
    """Return (form_code, material_grade_code) for one material code."""
    normalized = (code or "").strip().upper()
    if not normalized:
        return None, None
    if normalized in grade_codes:
        return None, normalized
    return normalized, None


# Seller words that name what the items were. Pallet, tote, and crate stay
# first so a lead that names more than one keeps the reusable-item grade.
_ITEM_GRADE_HINTS: tuple[tuple[str, str], ...] = (
    ("pallet", "PALLETS"),
    ("tote", "TOTES"),
    ("crate", "CRATES"),
    ("drum", "DRUMS"),
    ("bucket", "BUCKETS"),
    ("pail", "BUCKETS"),
)


def merge_form_and_grade(
    ai_form: str | None,
    declared_text: str | None,
    vision_form: str | None,
    grade_codes: Collection[str],
) -> tuple[str | None, str | None]:
    """Return (form_code, material_grade_code) when a submission has both facts.

    A grade never occupies the form slot. Seller item words fill only an empty
    grade. A vision form fills an empty form slot and does not replace a form
    the text AI already named.
    """
    form_code, grade_code = split_material_code(ai_form, grade_codes)
    if not grade_code:
        declared = (declared_text or "").lower()
        for term, hinted in _ITEM_GRADE_HINTS:
            if term in declared and hinted in grade_codes:
                grade_code = hinted
                break
    if vision_form and not form_code:
        seen_form, seen_grade = split_material_code(vision_form, grade_codes)
        if seen_form:
            form_code = seen_form
        elif seen_grade and not grade_code:
            grade_code = seen_grade
    return form_code, grade_code
