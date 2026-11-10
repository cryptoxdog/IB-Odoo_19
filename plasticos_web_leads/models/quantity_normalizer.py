"""Deterministic quantity evidence for canonical web-lead packets."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .triage_helpers import WEIGHT_SOURCE_AREA, SellerMass, parse_seller_mass

_WEEKLY_TO_MONTHLY = 52.0 / 12.0
_EVERY_OTHER_WEEK_TO_MONTHLY = 26.0 / 12.0

_INVENTORY_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(loads?|pallets?|gaylords?|bales?|rolls?)\b",
    re.IGNORECASE,
)
_CADENCE_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*loads?\s*(?:/|per|a|each)?\s*"
    r"(week|wk|weekly|month|mo|monthly|quarterly|quarter|annually|annual|year|yr)\b",
    re.IGNORECASE,
)
_EVERY_OTHER_WEEK_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)?\s*loads?\s*every\s+other\s+week\b", re.IGNORECASE)
_BIWEEKLY_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)?\s*loads?\s*biweekly\b", re.IGNORECASE)
_TWICE_MONTHLY_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)?\s*loads?\s*(?:twice\s+(?:a|per)\s+month|twice\s+monthly)\b", re.IGNORECASE
)

_PERIOD_NORMALIZATION = dict(
    week="weekly",
    wk="weekly",
    weekly="weekly",
    month="monthly",
    mo="monthly",
    monthly="monthly",
    quarter="quarterly",
    quarterly="quarterly",
    year="annual",
    yr="annual",
    annual="annual",
    annually="annual",
)
_MONTHLY_MULTIPLIERS = dict(
    weekly=_WEEKLY_TO_MONTHLY,
    every_other_week=_EVERY_OTHER_WEEK_TO_MONTHLY,
    twice_monthly=2.0,
    monthly=1.0,
    quarterly=1.0 / 3.0,
    annual=1.0 / 12.0,
)


@dataclass(frozen=True)
class QuantityEvidence:
    """Separated seller evidence for load mass, inventory, and cadence."""

    load_weight_lbs: float | None
    weight_source: str
    weight_source_text: str | None
    current_inventory_count_low: float | None
    current_inventory_count_high: float | None
    current_inventory_unit: str | None
    cadence_count_low: float | None
    cadence_count_high: float | None
    cadence_period: str | None
    loads_per_month: float | None
    supply_mode: str
    assumptions: tuple[str, ...]
    clarification_requests: tuple[str, ...]
    load_weight_lbs_high: float | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation for evidence persistence."""
        return asdict(self)


def _normalize_period(period: str) -> str:
    return _PERIOD_NORMALIZATION[period.lower()]


def _monthly_count(count: float, period: str) -> float:
    try:
        return count * _MONTHLY_MULTIPLIERS[period]
    except KeyError as exc:
        raise ValueError(f"Unsupported cadence period: {period}") from exc


def _supply_mode(*texts: str) -> str:
    lowered = " ".join(text.lower() for text in texts if text).strip()
    if re.search(r"\b(one[ -]?time|single\s+lot|closeout|liquidation)\b", lowered):
        return "one_time"
    if re.search(r"\bseasonal(?:ly)?\b", lowered):
        return "seasonal"
    if re.search(
        r"\b(ongoing|recurring|regular|continuous|weekly|monthly|quarterly|annual|annually|biweekly)\b", lowered
    ):
        return "ongoing"
    return "unclear"


def _cadence(text: str) -> tuple[float | None, str | None, float | None]:
    match = _CADENCE_PATTERN.search(text)
    if match:
        count = float(match.group(1))
        period = _normalize_period(match.group(2))
        return count, period, _monthly_count(count, period)

    for pattern, period in (
        (_EVERY_OTHER_WEEK_PATTERN, "every_other_week"),
        (_BIWEEKLY_PATTERN, "every_other_week"),
        (_TWICE_MONTHLY_PATTERN, "twice_monthly"),
    ):
        match = pattern.search(text)
        if match:
            count = float(match.group(1) or 1.0)
            return count, period, _monthly_count(count, period)

    lowered = text.lower()
    if re.search(r"\bweekly\b", lowered):
        return None, "weekly", None
    if re.search(r"\bmonthly\b", lowered):
        return None, "monthly", None
    if re.search(r"\bquarterly\b", lowered):
        return None, "quarterly", None
    if re.search(r"\b(annual|annually)\b", lowered):
        return None, "annual", None
    return None, None, None


def _inventory(text: str, cadence_period: str | None) -> tuple[float | None, str | None]:
    if cadence_period:
        return None, None
    match = _INVENTORY_PATTERN.search(text)
    if not match:
        return None, None
    return float(match.group(1)), match.group(2).lower().rstrip("s")


def _weight_from_weight_field(raw: str) -> SellerMass:
    """A dedicated weight box that is only a number is already pounds."""
    token = raw.replace(",", "").strip()
    try:
        numeric = float(token)
    except ValueError:
        return parse_seller_mass(raw)
    if numeric < 0:
        return SellerMass(None, None, "none")
    return SellerMass(numeric, None, "weight_per_load_field_lbs")


def normalize_quantity_evidence(
    *,
    quantity_text: str | None,
    weight_per_load_text: str | None,
    frequency_text: str | None,
) -> QuantityEvidence:
    """Normalize seller quantity text through the one mass parser."""
    quantity = (quantity_text or "").strip()
    per_load = (weight_per_load_text or "").strip()
    frequency = (frequency_text or "").strip()

    field_mass = _weight_from_weight_field(per_load) if per_load else SellerMass(None, None, "none")
    quantity_mass = parse_seller_mass(quantity) if quantity else SellerMass(None, None, "none")
    cadence_count, cadence_period, loads_per_month = _cadence(f"{quantity} {frequency}")
    if field_mass.source == WEIGHT_SOURCE_AREA or field_mass.lbs:
        chosen = field_mass
        weight_source_text = per_load or None
    elif quantity_mass.source == WEIGHT_SOURCE_AREA:
        chosen = quantity_mass
        weight_source_text = quantity or None
    elif quantity_mass.source.startswith("unit_count:") and cadence_period:
        chosen = SellerMass(None, None, "none")
        weight_source_text = None
    else:
        chosen = quantity_mass
        weight_source_text = quantity if chosen.lbs is not None or chosen.source == WEIGHT_SOURCE_AREA else None

    load_weight = chosen.lbs
    weight_source = chosen.source
    inventory_count, inventory_unit = _inventory(quantity, cadence_period)
    supply_mode = _supply_mode(quantity, frequency)

    clarifications: list[str] = []
    if load_weight is None:
        clarifications.append("Confirm per-load weight in pounds, kilograms, or tons.")
    if supply_mode == "ongoing" and loads_per_month is None:
        clarifications.append("Confirm recurring load cadence per week or month.")

    return QuantityEvidence(
        load_weight_lbs=load_weight,
        weight_source=weight_source,
        weight_source_text=weight_source_text,
        current_inventory_count_low=inventory_count,
        current_inventory_count_high=inventory_count,
        current_inventory_unit=inventory_unit,
        cadence_count_low=cadence_count,
        cadence_count_high=cadence_count,
        cadence_period=cadence_period,
        loads_per_month=loads_per_month,
        supply_mode=supply_mode,
        assumptions=chosen.assumptions,
        clarification_requests=tuple(clarifications),
        load_weight_lbs_high=chosen.lbs_high,
    )
