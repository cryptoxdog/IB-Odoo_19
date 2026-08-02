#!/usr/bin/env python3
"""Split opportunity protocol validators (TASK-039).

Replaces the combined opportunity-protocol discriminator with two peer payloads:
supply-opportunity and buyer-demand. Portable JSON Schema cannot compare siblings;
these runtime checks enforce quantity and time-window ordering.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

SUPPLY_REQUIRED = frozenset(
    {
        "contract_version",
        "domain",
        "opportunity_ref",
        "revision",
        "state",
        "material_specification_ref",
        "quantity",
        "availability",
        "source_record",
        "projection_version",
    }
)
DEMAND_REQUIRED = frozenset(
    {
        "contract_version",
        "domain",
        "demand_ref",
        "revision",
        "state",
        "material_requirement_ref",
        "quantity",
        "need_window",
        "source_record",
        "projection_version",
    }
)

# Keys that would imply a combined/impossible discriminator protocol.
FORBIDDEN_COMBINED_KEYS = frozenset(
    {
        "opportunity_type",
        "side",
        "protocol_kind",
        "discriminator",
        "oneOf",
    }
)


class OpportunityProtocolError(ValueError):
    """Raised when a split-protocol payload or field relation is invalid."""


def _as_number(value: Any, *, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise OpportunityProtocolError(f"{field} must be numeric, not boolean")
    if isinstance(value, (int, float)):
        return float(value)
    raise OpportunityProtocolError(f"{field} must be numeric")


def validate_quantity_range(quantity: dict[str, Any] | None, *, required: bool = True) -> None:
    if quantity is None:
        if required:
            raise OpportunityProtocolError("quantity is required")
        return
    if not isinstance(quantity, dict):
        raise OpportunityProtocolError("quantity must be an object")
    minimum = _as_number(quantity.get("minimum"), field="quantity.minimum")
    target = _as_number(quantity.get("target"), field="quantity.target")
    maximum = _as_number(quantity.get("maximum"), field="quantity.maximum")
    # Preserve explicit zeros; only compare when values are present.
    if minimum is not None and target is not None and minimum > target:
        raise OpportunityProtocolError("quantity.minimum must be <= quantity.target")
    if target is not None and maximum is not None and target > maximum:
        raise OpportunityProtocolError("quantity.target must be <= quantity.maximum")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise OpportunityProtocolError("quantity.minimum must be <= quantity.maximum")


def _parse_instant(value: Any, *, field: str) -> datetime | date | None:
    if value is None or value is False:
        return None
    if isinstance(value, (datetime, date)):
        return value
    if not isinstance(value, str) or not value:
        raise OpportunityProtocolError(f"{field} must be an ISO timestamp or date")
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError as exc:
            raise OpportunityProtocolError(f"{field} is not a valid timestamp") from exc


def validate_time_window(window: dict[str, Any] | None, *, required: bool = True, label: str = "window") -> None:
    if window is None:
        if required:
            raise OpportunityProtocolError(f"{label} is required")
        return
    if not isinstance(window, dict):
        raise OpportunityProtocolError(f"{label} must be an object")
    start = _parse_instant(window.get("start_at"), field=f"{label}.start_at")
    end = _parse_instant(window.get("end_at"), field=f"{label}.end_at")
    if start is not None and end is not None and start > end:
        raise OpportunityProtocolError(f"{label}.start_at must be <= {label}.end_at")


def assert_not_combined_protocol(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise OpportunityProtocolError("payload must be an object")
    bad = FORBIDDEN_COMBINED_KEYS.intersection(payload)
    if bad:
        raise OpportunityProtocolError(f"combined protocol keys forbidden: {sorted(bad)}")
    has_opp = "opportunity_ref" in payload
    has_dem = "demand_ref" in payload
    if has_opp and has_dem:
        raise OpportunityProtocolError("payload cannot mix opportunity_ref and demand_ref")


def validate_supply_payload(payload: dict[str, Any]) -> None:
    assert_not_combined_protocol(payload)
    missing = sorted(SUPPLY_REQUIRED - payload.keys())
    if missing:
        raise OpportunityProtocolError(f"supply-opportunity missing required fields: {missing}")
    if "demand_ref" in payload or "need_window" in payload:
        raise OpportunityProtocolError("supply-opportunity must not carry buyer-demand fields")
    validate_quantity_range(payload.get("quantity"), required=True)
    validate_time_window(payload.get("availability"), required=True, label="availability")


def validate_buyer_demand_payload(payload: dict[str, Any]) -> None:
    assert_not_combined_protocol(payload)
    missing = sorted(DEMAND_REQUIRED - payload.keys())
    if missing:
        raise OpportunityProtocolError(f"buyer-demand missing required fields: {missing}")
    if "opportunity_ref" in payload or "availability" in payload:
        raise OpportunityProtocolError("buyer-demand must not carry supply-opportunity fields")
    validate_quantity_range(payload.get("quantity"), required=True)
    validate_time_window(payload.get("need_window"), required=True, label="need_window")


def validate_odoo_quantity_triplet(minimum: float | None, target: float | None, maximum: float | None) -> None:
    """ORM field check: min_lot / quantity / max_lot (zeros preserved)."""
    validate_quantity_range(
        {
            "minimum": minimum if minimum not in (None, False) else None,
            "target": target if target not in (None, False) else None,
            "maximum": maximum if maximum not in (None, False) else None,
        },
        required=False,
    )


def validate_odoo_date_window(start: date | None, end: date | None, *, label: str) -> None:
    if start and end and start > end:
        raise OpportunityProtocolError(f"{label} start must be <= end")
