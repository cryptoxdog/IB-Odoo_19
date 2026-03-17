"""Canonical process-type code registry — single source of truth.

Every layer that references process types MUST import from here:
  - material_profile.py ``origin_process_type`` Selection
  - facility_profile.py ``process_type`` Selection
  - matcher.py Gate 9 MFI compatibility check
  - graph_service.py Cypher process-type scoring
  - tests/test_process_enum_alignment.py drift-prevention tests

Adding or removing a process code here will cause drift-prevention tests to
fail until every downstream consumer is updated.

Pattern follows form_codes.py from PR #23.
"""

# ── Canonical process codes (alphabetical for deterministic comparison) ──
PROCESS_CODES: tuple[str, ...] = (
    "blow_mold",
    "compounding",
    "extrusion",
    "film_blown",
    "film_cast",
    "injection",
    "other",
    "rotomold",
    "thermoform",
)

# ── MFI Ranges per process type ──────────────────────────────────────────
# Key = process code, Value = (min_mfi, max_mfi) where None = no limit.
# Industry-standard heuristics for MFI compatibility.
MFI_RANGES: dict[str, tuple[float | None, float | None]] = {
    "injection": (10.0, None),  # MFI >= 10
    "extrusion": (None, 20.0),  # MFI <= 20
    "blow_mold": (0.5, 10.0),  # 0.5 <= MFI <= 10
    "film_blown": (None, 5.0),  # MFI <= 5
    "film_cast": (None, 5.0),  # MFI <= 5
    "thermoform": (1.0, 12.0),  # 1 <= MFI <= 12
    "rotomold": (2.0, 10.0),  # 2 <= MFI <= 10
    "compounding": (None, None),  # any MFI
    "other": (None, None),  # any MFI
}

# ── Selection tuples (for Odoo fields.Selection) ─────────────────────────
# Human-readable labels for UI display.
PROCESS_LABELS: dict[str, str] = {
    "blow_mold": "Blow Molding",
    "compounding": "Compounding",
    "extrusion": "Extrusion",
    "film_blown": "Film Blown",
    "film_cast": "Film Cast",
    "injection": "Injection Molding",
    "other": "Other",
    "rotomold": "Rotational Molding",
    "thermoform": "Thermoforming",
}

PROCESS_SELECTION: list[tuple[str, str]] = [(code, PROCESS_LABELS[code]) for code in PROCESS_CODES]


def check_mfi_compatibility(process_type: str | None, mfi: float | None) -> bool:
    """Return True when the MFI value is compatible with process_type.

    Null-safe: missing data = pass (compatible).
    """
    if not process_type or mfi is None:
        return True

    bounds = MFI_RANGES.get(process_type)
    if bounds is None:
        return True  # unknown process type = pass

    lo, hi = bounds
    if lo is not None and mfi < lo:
        return False
    if hi is not None and mfi > hi:
        return False
    return True
