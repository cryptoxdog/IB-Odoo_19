# ═══════════════════════════════════════════════════════════════════════════════
# triage_helpers.py
# Module : plasticos_web_leads
# Purpose: Shared deterministic parsing / inference helpers used by
#          ai_normalizer, classification_engine, and image_analyzer.
#
# FIXES APPLIED:
# WL-01 — tonnes pattern now correctly maps to metric-ton branch (×2204.6)
# WL-02 — comma-stripped numeric parsing replaces .isdigit() guard
# WL-03 — unit-count parsing uses safe_float() instead of raw int()
# WL-04 — UNIT_WEIGHTS_LBS updated to industry-realistic values
# WL-05 — weight_source tag is always populated, bare-number path tagged
# WL-06 — safe_int / safe_float are canonical here; ai_normalizer imports them
# ═══════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import re

# ─────────────────────────────────────────────────────────────────────────────
# Unit-to-weight conversion table (lbs per unit)
# Updated to industry-realistic values for commercial recycled plastics:
#   pallet   : 1800 lbs (HDPE film bale rack / industrial pallet)
#   bale     : 1500 lbs (standard 30×30×48 compressed plastic bale)
#   gaylord  : 1000 lbs (48×40×36 gaylord bin, plastic regrind)
#   drum     :  450 lbs (55-gal drum, dense plastic pellets)
#   tote     : 2000 lbs (IBC tote, liquid or pellet load)
#   supersack: 2000 lbs (bulk bag / FIBC at capacity)
#   truckload:42000 lbs (standard 53' van, 44,000 lb max, 42k realistic)
#   container:44000 lbs (20' ISO, plastic scrap)
# ─────────────────────────────────────────────────────────────────────────────
UNIT_WEIGHTS_LBS: dict[str, float] = {
    "pallet": 1800.0,
    "bale": 1500.0,
    "gaylord": 1000.0,
    "drum": 450.0,
    "tote": 2000.0,
    "supersack": 2000.0,
    "super sack": 2000.0,
    "truckload": 42000.0,
    "truck": 42000.0,
    "container": 44000.0,
    "load": 42000.0,
}

# Written-out number words → integers (for "one truckload" etc.)
_WORD_NUMBERS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "a": 1,
    "an": 1,
}

# ─────────────────────────────────────────────────────────────────────────────
# safe_int / safe_float — canonical definitions (imported by other modules)
# ─────────────────────────────────────────────────────────────────────────────


def safe_int(value, *, default: int = 0) -> int:
    """Coerce value to int, returning default on None / non-numeric."""
    if value is None:
        return default
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (ValueError, TypeError):
        return default


def safe_float(value, *, default: float = 0.0) -> float:
    """Coerce value to float, returning default on None / non-numeric."""
    if value is None:
        return default
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return default


# ─────────────────────────────────────────────────────────────────────────────
# Weight parsing
# ─────────────────────────────────────────────────────────────────────────────

#
# FIX WL-01: metric-ton patterns (metric ton / metric tons / tonne / tonnes)
# MUST appear BEFORE short-ton patterns in the compiled regex OR be handled
# in a separate priority branch. We handle this by checking metric patterns
# first in the function body.
#
_RE_COMMA_NUM = re.compile(r"[\d,]+(?:\.\d+)?")

# Priority 1 — explicit mass with recognised unit
_MASS_PATTERNS: list[tuple[str, float, str]] = [
    # metric tons — MUST precede short tons (WL-01 fix)
    (r"([\d,]+(?:\.\d+)?)\s*(?:metric\s+ton(?:ne)?s?|tonne?s?)\b", 2204.623, "explicit_metric_tons"),
    # short tons
    (r"([\d,]+(?:\.\d+)?)\s*(?:short\s+)?ton(?:s)?\b(?!\s*ne)", 2000.0, "explicit_tons"),
    # lbs / lb / pounds
    (r"([\d,]+(?:\.\d+)?)\s*(?:lbs?|pounds?)\b", 1.0, "explicit_lbs"),
    # kg / kilograms
    (r"([\d,]+(?:\.\d+)?)\s*(?:kgs?|kilograms?)\b", 2.205, "explicit_kg"),
]

# Priority 2 — unit counts (ordered longest match first to avoid "tote"→"to")
_UNIT_PATTERNS: list[tuple[str, str]] = [
    (r"([\d,]+(?:\.\d+)?|" + "|".join(_WORD_NUMBERS) + r")\s*(?:super\s*sacks?)\b", "supersack"),
    (r"([\d,]+(?:\.\d+)?|" + "|".join(_WORD_NUMBERS) + r")\s*truckloads?\b", "truckload"),
    (r"([\d,]+(?:\.\d+)?|" + "|".join(_WORD_NUMBERS) + r")\s*(?:40'|20'|iso\s*)?containers?\b", "container"),
    (r"([\d,]+(?:\.\d+)?|" + "|".join(_WORD_NUMBERS) + r")\s*gaylords?\b", "gaylord"),
    (r"([\d,]+(?:\.\d+)?|" + "|".join(_WORD_NUMBERS) + r")\s*pallets?\b", "pallet"),
    (r"([\d,]+(?:\.\d+)?|" + "|".join(_WORD_NUMBERS) + r")\s*bales?\b", "bale"),
    (r"([\d,]+(?:\.\d+)?|" + "|".join(_WORD_NUMBERS) + r")\s*drums?\b", "drum"),
    (r"([\d,]+(?:\.\d+)?|" + "|".join(_WORD_NUMBERS) + r")\s*totes?\b", "tote"),
    (r"([\d,]+(?:\.\d+)?|" + "|".join(_WORD_NUMBERS) + r")\s*loads?\b", "load"),
]
_COMPILED_MASS = [(re.compile(p, re.I), mult, tag) for p, mult, tag in _MASS_PATTERNS]
_COMPILED_UNITS = [(re.compile(p, re.I), unit) for p, unit in _UNIT_PATTERNS]


def _strip_commas(s: str) -> float:
    """Remove thousands-separator commas and coerce to float. (FIX WL-02)"""
    cleaned = s.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_weight_lbs(raw: str | None) -> tuple[float, str]:
    """
    Parse a free-text quantity string into (lbs: float, source_tag: str).

    source_tag values (for audit trail):
      "none"                  — no parseable weight found
      "explicit_lbs"          — number + lbs/lb/pounds keyword
      "explicit_tons"         — number + ton/tons keyword
      "explicit_metric_tons"  — number + metric ton/tonne keyword
      "explicit_kg"           — number + kg/kilogram keyword
      "unit_count:<unit>"     — inferred from container count × weight
      "bare_number:lbs_assumed" — bare large number, assumed lbs
    """
    if not raw:
        return 0.0, "none"

    text = str(raw).strip()

    # Priority 1 — explicit mass units
    for pattern, multiplier, tag in _COMPILED_MASS:
        m = pattern.search(text)
        if m:
            qty = _strip_commas(m.group(1))  # FIX WL-02: strip commas
            if qty > 0:
                return round(qty * multiplier, 2), tag

    # Priority 2 — unit counts (FIX WL-03: uses safe_float not int())
    for pattern, unit_key in _COMPILED_UNITS:
        m = pattern.search(text)
        if m:
            raw_qty = m.group(1).strip().lower()
            qty = _WORD_NUMBERS.get(raw_qty, None)
            if qty is None:
                qty = safe_float(raw_qty)
            if qty and qty > 0:
                lbs_per_unit = UNIT_WEIGHTS_LBS.get(unit_key, 0.0)
                return round(qty * lbs_per_unit, 2), f"unit_count:{unit_key}"

    # Priority 3 — bare large number (≥ 1000), assume lbs (FIX WL-05)
    bare = _RE_COMMA_NUM.search(text)
    if bare:
        val = _strip_commas(bare.group())
        if val >= 1000.0:
            return val, "bare_number:lbs_assumed"

    return 0.0, "none"


# ─────────────────────────────────────────────────────────────────────────────
# Boolean coercion (shared by ai_normalizer.validate_ai_output)
# ─────────────────────────────────────────────────────────────────────────────
_TRUE_STRINGS = {"true", "yes", "1", "y", "t"}
_FALSE_STRINGS = {"false", "no", "0", "n", "f"}


def coerce_bool(value) -> bool | None:
    """
    Coerce AI string / int booleans to Python bool or None.

    Returns:
      True  — if value is True, 1, or a recognised truthy string
      False — if value is False, 0, or a recognised falsy string
      None  — if value is None or an unrecognised string ("maybe", "unknown")
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    s = str(value).strip().lower()
    if s in _TRUE_STRINGS:
        return True
    if s in _FALSE_STRINGS:
        return False
    return None  # unrecognised → treat as unknown, not False
