"""Pure helpers for material profile derived features (no Odoo registry required)."""

from __future__ import annotations

_RESIDUE_TEXT_MARKERS = (
    "residue",
    "residual",
    "leftover",
    "oil residue",
    "grease",
    "adhesive",
    "contaminant",
)

_RESIDUE_ATTRIBUTE_CODES = frozenset({"residue", "with_residue", "oil_residue"})


def _normalize_tokens(values) -> list[str]:
    if not values:
        return []
    tokens = []
    for item in values:
        if item is None:
            continue
        text = str(item).strip().lower()
        if text:
            tokens.append(text)
    return tokens


def _text_indicates_residue(text: str | None) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _RESIDUE_TEXT_MARKERS)


def compute_has_residue_feature(
    *,
    contamination_percent: float | None = None,
    contamination_notes: str | None = None,
    material_attribute_names_or_codes: list[str] | None = None,
    source_type_name_or_code: str | None = None,
    origin_process_type: str | None = None,
    freeform_notes: str | None = None,
) -> bool:
    """Derive residue presence from quality and context signals (not a stored DB field)."""
    if contamination_percent is not None and contamination_percent > 0:
        return True
    if _text_indicates_residue(contamination_notes):
        return True
    if _text_indicates_residue(freeform_notes):
        return True

    for token in _normalize_tokens(material_attribute_names_or_codes):
        if token in _RESIDUE_ATTRIBUTE_CODES or "residue" in token:
            return True

    for token in _normalize_tokens([source_type_name_or_code, origin_process_type]):
        if "residue" in token:
            return True

    return False
