"""Canonical quality-tier code registry.

``tests/test_quality_tier_codes.py`` keeps this tuple equal to the codes in
``data/material_quality_tier_data.xml``. Phrase-sheet letters A, B, and C map
onto the first three codes. The CRM import uses that map. The normalizer still
returns the letter itself.
"""

# Same order as the seed file. UPPER_SNAKE convention.
QUALITY_TIER_CODES: tuple[str, ...] = (
    "GRADE_A",
    "GRADE_B",
    "GRADE_C",
    "REUSABLE",
    "STANDARD",
)

# Phrase-sheet grade column. Other letters are not a quality tier.
LETTER_TO_QUALITY_TIER: dict[str, str] = {
    "A": "GRADE_A",
    "B": "GRADE_B",
    "C": "GRADE_C",
}

# Former selection keys that survive on the master. Prime, Near Prime,
# Economy, and Unknown do not.
SELECTION_TO_QUALITY_TIER: dict[str, str] = {
    "grade_a": "GRADE_A",
    "grade_b": "GRADE_B",
    "standard": "STANDARD",
}


def template_quality_tier_code(old_tier: str | None) -> str | None:
    """Selection key stored on a grade template, or None when it has no master."""
    return SELECTION_TO_QUALITY_TIER.get((old_tier or "").strip())


def profile_quality_tier(old_tier: str | None, sub_grade: str | None) -> tuple[str | None, str | None]:
    """Return ``(tier code or None, leftover sub_grade text or None)``.

    A stored letter A, B, or C wins over the old selection. Any other
    ``sub_grade`` text is leftover for ``freeform_notes``. It is not a tier.
    """
    letter = (sub_grade or "").strip()
    if letter in LETTER_TO_QUALITY_TIER:
        return LETTER_TO_QUALITY_TIER[letter], None
    return SELECTION_TO_QUALITY_TIER.get((old_tier or "").strip()), letter or None


def notes_with_leftover(notes: str | None, leftover: str | None) -> str | None:
    """Append leftover text when the notes do not already contain it.

    ``None`` means the notes stay as they are.
    """
    text = (leftover or "").strip()
    if not text:
        return None
    current = notes or ""
    if text.casefold() in current.casefold():
        return None
    if current.strip():
        return f"{current.rstrip()}\n{text}"
    return text
