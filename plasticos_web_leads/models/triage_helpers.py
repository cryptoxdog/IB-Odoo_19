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
from dataclasses import dataclass

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

# A seller range. The low number is the classified weight. The high number is kept.
_RANGE_RE = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*(?:-|–|—|\bto\b)\s*([\d,]+(?:\.\d+)?)",
    re.IGNORECASE,
)
_AREA_RE = re.compile(
    r"\b(?:sq\.?\s*ft|sqft|square\s+feet|square\s+foot|ft\s*(?:\^?\s*2|²)|"
    r"sq\.?\s*m|sqm|square\s+met(?:er|re)s?|m\s*(?:\^?\s*2|²))\b",
    re.IGNORECASE,
)
_COUNT_TAIL_RE = re.compile(
    r"^\s*(?:super\s*sacks?|truckloads?|containers?|gaylords?|pallets?|bales?|drums?|totes?|loads?)\b",
    re.IGNORECASE,
)
_TAIL_UNITS: tuple[tuple[re.Pattern[str], float, str], ...] = (
    (re.compile(r"^\s*(?:metric\s+tons?|metric\s+tonnes?|tonnes?)\b", re.I), 2204.623, "explicit_metric_tons"),
    (re.compile(r"^\s*(?:short\s+)?tons?\b", re.I), 2000.0, "explicit_tons"),
    (re.compile(r"^\s*(?:lbs?|pounds?)\b", re.I), 1.0, "explicit_lbs"),
    (re.compile(r"^\s*(?:kgs?|kilograms?)\b", re.I), 2.205, "explicit_kg"),
)

# Above this, the number is stored and flagged. It is not deleted.
SINGLE_LOAD_REVIEW_CAP_LBS = 200_000.0
# Area text is a weight-source tag, not a selection value.
WEIGHT_SOURCE_AREA = "area_not_mass"


def _strip_commas(s: str) -> float:
    """Remove thousands-separator commas and coerce to float. (FIX WL-02)"""
    cleaned = s.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


@dataclass(frozen=True)
class SellerMass:
    """One seller mass reading. ``lbs`` is the classified weight. ``lbs_high`` is a range top."""

    lbs: float | None
    lbs_high: float | None
    source: str
    assumptions: tuple[str, ...] = ()


def _unit_after(text: str, end: int) -> tuple[float, str] | None:
    tail = text[end:]
    for pattern, multiplier, tag in _TAIL_UNITS:
        if pattern.match(tail):
            return multiplier, tag
    return None


def _range_assumption(source: str, high: float | None) -> tuple[str, ...]:
    notes: list[str] = []
    if high is not None:
        notes.append("Classified on the low end of the seller range.")
    if source.startswith("unit_count:"):
        notes.append(f"Converted a stated {source.split(':', 1)[1]} count with the unit weight table.")
    return tuple(notes)


def parse_seller_mass(raw: str | None) -> SellerMass:
    """Parse seller text into one mass reading.

    Explicit mass, a numeric range, and a stated unit count all resolve here.
    Square feet and square meters stay area. They never become pounds.
    """
    if raw is None or not str(raw).strip():
        return SellerMass(None, None, "none")

    text = str(raw).strip()
    has_area = _AREA_RE.search(text) is not None

    range_match = _RANGE_RE.search(text)
    if range_match and _COUNT_TAIL_RE.match(text[range_match.end() :]) is None:
        low = _strip_commas(range_match.group(1))
        high = _strip_commas(range_match.group(2))
        unit = _unit_after(text, range_match.end())
        if unit and low > 0:
            multiplier, tag = unit
            high_lbs = round(high * multiplier, 2) if high > low else None
            return SellerMass(round(low * multiplier, 2), high_lbs, tag, _range_assumption(tag, high_lbs))
        if not unit and not has_area and low > 0 and high >= low:
            high_lbs = high if high > low else None
            return SellerMass(low, high_lbs, "range_lbs", _range_assumption("range_lbs", high_lbs))
        if has_area and not unit:
            return SellerMass(None, None, WEIGHT_SOURCE_AREA)

    for pattern, multiplier, tag in _COMPILED_MASS:
        match = pattern.search(text)
        if match:
            quantity = _strip_commas(match.group(1))
            if quantity > 0:
                return SellerMass(round(quantity * multiplier, 2), None, tag)

    if has_area:
        return SellerMass(None, None, WEIGHT_SOURCE_AREA)

    for pattern, unit_key in _COMPILED_UNITS:
        match = pattern.search(text)
        if not match:
            continue
        raw_qty = match.group(1).strip().lower()
        quantity = _WORD_NUMBERS.get(raw_qty)
        if quantity is None:
            quantity = safe_float(raw_qty)
        if quantity and quantity > 0:
            source = f"unit_count:{unit_key}"
            lbs = round(quantity * UNIT_WEIGHTS_LBS.get(unit_key, 0.0), 2)
            return SellerMass(lbs, None, source, _range_assumption(source, None))

    bare = _RE_COMMA_NUM.search(text)
    if bare and not has_area:
        value = _strip_commas(bare.group())
        if value >= 1000.0:
            # A unitless number is not a pound figure. The source records that it was seen.
            return SellerMass(None, None, "bare_number:lbs_assumed")

    return SellerMass(None, None, "none")


def parse_weight_lbs(raw: str | None) -> tuple[float, str]:
    """Parse seller text into ``(lbs, source)``. A missing mass is ``(0.0, source)``."""
    mass = parse_seller_mass(raw)
    if mass.lbs is None:
        return 0.0, "none" if mass.source == "none" else mass.source
    return mass.lbs, mass.source


def parse_explicit_weight_lbs(raw: str | None) -> tuple[float | None, str]:
    """Return the same mass reading as ``parse_seller_mass``, without the range top."""
    mass = parse_seller_mass(raw)
    return mass.lbs, mass.source


def replay_stored_mass(*, quantity_text: str | None, estimated_lbs: float | None = None) -> SellerMass:
    """Re-read stored seller text. Area text discards a previously stored pound figure."""
    parsed = parse_seller_mass(quantity_text)
    if parsed.source == WEIGHT_SOURCE_AREA or parsed.source.startswith("bare_number:"):
        return parsed
    if parsed.lbs:
        return parsed
    stored = float(estimated_lbs or 0)
    if stored > 0:
        return SellerMass(stored, None, "stored_lbs")
    return parsed


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
