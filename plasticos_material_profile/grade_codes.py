"""Canonical material-grade code registry — single source of truth.

A material grade is what the items were before processing (drums, totes,
pallets). It is not a physical form; forms live in ``form_codes.py``.

``tests/test_material_grade_codes.py`` keeps this tuple equal to the codes in
``data/material_grade_data.xml``.
"""

# Same order as the seed file. UPPER_SNAKE convention.
GRADE_CODES: tuple[str, ...] = (
    "BUCKETS",
    "DRUMS",
    "JERRY_CANS",
    "SUPERACS",
    "TRAYS",
    "LIDS",
    "TUBS_LIDS",
    "CUPS",
    "JARS",
    "FLOWER_POTS",
    "TOTES",
    "TOTERS",
    "IBC_TOTES",
    "LINERS",
    "DRIP_TUBE",
    "PIPE",
    "TUBING",
    "PALLETS",
    "BOTTLES",
    "STRAPPING",
    "CORNERBOARDS",
    "CORE_PLUGS",
    "CRATES",
    "KNOCKDOWN_BINS",
    "BUMPERS",
    "SIDING",
    "RETURNS",
    "DUNNAGE",
    "STRETCH_FILM",
    "SHRINK_WRAP",
    "SILAGE_FILM",
    "NURSERY_FILM",
    "OCC",
    "DISPOSAL_FEE",
    "TRASH",
)

# Codes that were material forms before 19.0.5.11.0.
FORMER_FORM_CODES: tuple[str, ...] = ("BOTTLES", "BUCKETS", "CRATES", "DRUMS", "PALLETS", "TOTES")
