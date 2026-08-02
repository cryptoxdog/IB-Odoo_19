"""Semantic kernel -> Gate payload builders (TASK-027).

Projects approved Odoo ORM records into supply-opportunity and buyer-demand
payloads. Never embeds TransportPacket routing/identity fields in the payload.
Cross-field quantity/window rules are enforced here (JSON Schema cannot).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

PROJECTION_VERSION = "1.0.0"
FIELD_DICTIONARY_VERSION = "1.0.0"
CONTRACT_VERSION = "1.0.0-draft"
DOMAIN = "plasticos"


# Odoo selection -> payload state (peer schemas; no combined discriminator).
def _map_supply_state(state_raw: str) -> str:
    if state_raw == "available":
        return "open"
    if state_raw == "reserved":
        return "committed"
    if state_raw == "cancelled":
        return "withdrawn"
    return state_raw


def _map_demand_state(state_raw: str) -> str:
    if state_raw == "partially_filled":
        return "sourcing"
    if state_raw == "filled":
        return "satisfied"
    if state_raw == "cancelled":
        return "withdrawn"
    return state_raw


_TRANSPORT_FORBIDDEN = frozenset(
    {
        "packet_id",
        "tenant_id",
        "source_node",
        "destination_node",
        "action",
        "correlation_id",
        "causation_id",
        "hops",
        "hop_trace",
        "idempotency_key",
        "transport_hash",
        "signature",
    }
)


class SemanticPayloadError(ValueError):
    """Invalid semantic payload projection."""


def _ref(model: str, record_id: int | str | None) -> str | None:
    if record_id is None or record_id == "":
        return None
    return f"{model}:{int(record_id)}"


def _iso_date(value: Any) -> str | None:
    if value in (None, False, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return f"{value.isoformat()}T00:00:00Z"
    text = str(value)
    if "T" not in text:
        return f"{text[:10]}T00:00:00Z"
    return text


def _num(value: Any) -> float | None:
    if value is None or value is False:
        return None
    return float(value)


def _assert_quantity_order(minimum: float | None, target: float | None, maximum: float | None) -> None:
    if minimum is not None and target is not None and minimum > target:
        raise SemanticPayloadError("quantity.minimum must be <= quantity.target")
    if target is not None and maximum is not None and target > maximum:
        raise SemanticPayloadError("quantity.target must be <= quantity.maximum")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise SemanticPayloadError("quantity.minimum must be <= quantity.maximum")


def _assert_window_order(start: str | None, end: str | None, *, label: str) -> None:
    if start and end and start > end:
        raise SemanticPayloadError(f"{label}.start_at must be <= {label}.end_at")


def _reject_transport_fields(payload: dict[str, Any]) -> None:
    bad = _TRANSPORT_FORBIDDEN.intersection(payload)
    if bad:
        raise SemanticPayloadError(f"payload must not include transport fields: {sorted(bad)}")


def build_quantity_range(
    *,
    minimum: float | None,
    target: float | None,
    maximum: float | None,
    unit: str = "lb",
) -> dict[str, Any]:
    _assert_quantity_order(minimum, target, maximum)
    qty: dict[str, Any] = {"unit": unit}
    if minimum is not None:
        qty["minimum"] = minimum
    if target is not None:
        qty["target"] = target
    if maximum is not None:
        qty["maximum"] = maximum
    if "minimum" not in qty and "target" not in qty and "maximum" not in qty:
        raise SemanticPayloadError("quantity is required")
    return qty


def build_supply_opportunity_payload(record: Any, *, revision: int | None = None) -> dict[str, Any]:
    """Project plasticos.supply.opportunity (or stub) to supply-opportunity payload."""
    record_id = int(record.id)
    state_raw = getattr(record, "state", None) or "draft"
    state = _map_supply_state(state_raw)

    spec = getattr(record, "specification_id", None)
    spec_id = getattr(spec, "id", None) if spec not in (None, False) else None
    if not spec_id:
        raise SemanticPayloadError("material_specification_ref required")

    supplier = getattr(record, "supplier_partner_id", None)
    supplier_id = getattr(supplier, "id", None) if supplier not in (None, False) else None
    origin = getattr(record, "origin_facility_id", None)
    origin_id = getattr(origin, "id", None) if origin not in (None, False) else None

    minimum = _num(getattr(record, "min_lot_size_lbs", None))
    target = _num(getattr(record, "quantity_lbs", None))
    maximum = _num(getattr(record, "max_lot_size_lbs", None))
    quantity = build_quantity_range(minimum=minimum, target=target, maximum=maximum)

    start = _iso_date(getattr(record, "available_from", None))
    end = _iso_date(getattr(record, "available_until", None))
    _assert_window_order(start, end, label="availability")
    availability: dict[str, Any] = {}
    if start:
        availability["start_at"] = start
    if end:
        availability["end_at"] = end
    if not availability:
        raise SemanticPayloadError("availability window required")

    rev = int(revision) if revision is not None else 1

    payload: dict[str, Any] = {}
    payload["contract_version"] = CONTRACT_VERSION
    payload["domain"] = DOMAIN
    payload["opportunity_ref"] = _ref("plasticos.supply.opportunity", record_id)
    payload["revision"] = rev
    payload["state"] = state
    if supplier_id:
        payload["supplier_ref"] = _ref("res.partner", supplier_id)
    if origin_id:
        payload["origin_facility_ref"] = _ref("res.partner", origin_id)
    payload["material_specification_ref"] = _ref("plasticos.material.specification", spec_id)
    payload["quantity"] = quantity
    payload["availability"] = availability

    price = _num(getattr(record, "asking_price_per_lb", None))
    currency = getattr(record, "currency_id", None)
    currency_name = getattr(currency, "name", None) if currency not in (None, False) else None
    if price is not None and currency_name:
        asking: dict[str, Any] = {}
        asking["amount"] = price
        asking["currency"] = str(currency_name)
        asking["unit"] = "lb"
        payload["asking_price"] = asking

    intake = getattr(record, "intake_id", None)
    intake_id = getattr(intake, "id", None) if intake not in (None, False) else None
    source_ref = getattr(record, "source_record_ref", None) or (
        _ref("plasticos.intake", intake_id) if intake_id else _ref("plasticos.supply.opportunity", record_id)
    )
    source: dict[str, Any] = {}
    source["system"] = getattr(record, "source_system", None) or "odoo"
    source["record_ref"] = source_ref
    source["revision"] = rev
    payload["source_record"] = source
    payload["projection_version"] = getattr(record, "contract_version", None) or PROJECTION_VERSION
    payload["field_dictionary_version"] = FIELD_DICTIONARY_VERSION
    payload["evidence_refs"] = []
    payload["unresolved_fields"] = []

    _reject_transport_fields(payload)
    if "demand_ref" in payload:
        raise SemanticPayloadError("supply payload must not include demand_ref")
    return payload


def build_buyer_demand_payload(record: Any, *, revision: int | None = None) -> dict[str, Any]:
    """Project plasticos.buyer.demand (or stub) to buyer-demand payload."""
    record_id = int(record.id)
    state_raw = getattr(record, "state", None) or "draft"
    state = _map_demand_state(state_raw)

    spec = getattr(record, "specification_id", None)
    spec_id = getattr(spec, "id", None) if spec not in (None, False) else None
    if not spec_id:
        raise SemanticPayloadError("material_requirement_ref required")

    buyer = getattr(record, "buyer_partner_id", None)
    buyer_id = getattr(buyer, "id", None) if buyer not in (None, False) else None
    dest = getattr(record, "buyer_facility_id", None)
    dest_id = getattr(dest, "id", None) if dest not in (None, False) else None

    minimum = _num(getattr(record, "min_lot_size_lbs", None))
    target = _num(getattr(record, "quantity_lbs", None))
    maximum = _num(getattr(record, "max_lot_size_lbs", None))
    quantity = build_quantity_range(minimum=minimum, target=target, maximum=maximum)

    start = _iso_date(getattr(record, "needed_from", None))
    end = _iso_date(getattr(record, "needed_until", None))
    _assert_window_order(start, end, label="need_window")
    need_window: dict[str, Any] = {}
    if start:
        need_window["start_at"] = start
    if end:
        need_window["end_at"] = end
    if not need_window:
        raise SemanticPayloadError("need_window required")

    rev = 1 if revision is None else int(revision)

    payload: dict[str, Any] = {}
    payload["contract_version"] = CONTRACT_VERSION
    payload["domain"] = DOMAIN
    payload["demand_ref"] = _ref("plasticos.buyer.demand", record_id)
    payload["revision"] = rev
    payload["state"] = state
    if buyer_id:
        payload["buyer_ref"] = _ref("res.partner", buyer_id)
    if dest_id:
        payload["destination_facility_ref"] = _ref("res.partner", dest_id)
    payload["material_requirement_ref"] = _ref("plasticos.material.specification", spec_id)
    payload["quantity"] = quantity
    payload["need_window"] = need_window

    price = _num(getattr(record, "target_price_per_lb", None))
    currency = getattr(record, "currency_id", None)
    currency_name = getattr(currency, "name", None) if currency not in (None, False) else None
    if price is not None and currency_name:
        target_price: dict[str, Any] = {}
        target_price["amount"] = price
        target_price["currency"] = str(currency_name)
        target_price["unit"] = "lb"
        payload["target_price"] = target_price

    source_ref = getattr(record, "source_record_ref", None) or _ref("plasticos.buyer.demand", record_id)
    source: dict[str, Any] = {}
    source["system"] = getattr(record, "source_system", None) or "odoo"
    source["record_ref"] = source_ref
    source["revision"] = rev
    payload["source_record"] = source
    payload["projection_version"] = getattr(record, "contract_version", None) or PROJECTION_VERSION
    payload["field_dictionary_version"] = FIELD_DICTIONARY_VERSION
    payload["required_certifications"] = []
    payload["evidence_refs"] = []
    payload["unresolved_fields"] = []

    _reject_transport_fields(payload)
    if "opportunity_ref" in payload:
        raise SemanticPayloadError("buyer-demand payload must not include opportunity_ref")
    return payload


def build_match_query_from_supply(payload: dict[str, Any], *, top_n: int = 20) -> dict[str, Any]:
    """Wrap a supply-opportunity payload as Gate match query facts (no transport fields)."""
    _reject_transport_fields(payload)
    query: dict[str, Any] = {}
    query["entity_ref"] = payload["opportunity_ref"]
    query["facts"] = payload
    query["evidence_summary"] = list(payload.get("evidence_refs") or [])
    out: dict[str, Any] = {}
    out["direction"] = "supply_opportunity_to_buyer_facility"
    out["query"] = query
    out["top_n"] = top_n
    return out


def build_match_query_from_demand(payload: dict[str, Any], *, top_n: int = 20) -> dict[str, Any]:
    _reject_transport_fields(payload)
    query: dict[str, Any] = {}
    query["entity_ref"] = payload["demand_ref"]
    query["facts"] = payload
    query["evidence_summary"] = list(payload.get("evidence_refs") or [])
    out: dict[str, Any] = {}
    out["direction"] = "buyer_demand_to_supply_opportunity"
    out["query"] = query
    out["top_n"] = top_n
    return out
