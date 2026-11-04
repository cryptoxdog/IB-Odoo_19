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
