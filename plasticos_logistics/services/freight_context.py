"""Deterministic freight-context construction for governed logistics decisions.

This service owns canonical serialization and SHA-256 identities only. It never
contacts a carrier or performs a commercial action.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

FREIGHT_CONTEXT_VERSION = "freight_context_v3"
FREIGHT_CONTEXT_SCHEMA_VERSION = "3.0"
# Buyerless or manual movement: exact company and physical lane, no intake repeat
# stream. It authorizes a manual rate only; Same As Last never qualifies on it.
FREIGHT_CONTEXT_MANUAL_VERSION = "freight_context_manual_v1"
FREIGHT_CONTEXT_MANUAL_SCHEMA_VERSION = "1.0"
UNKNOWN_EQUIPMENT_CLASS = "unknown"
FREIGHT_CONTEXT_VERSIONS = (FREIGHT_CONTEXT_VERSION, FREIGHT_CONTEXT_MANUAL_VERSION)


@dataclass(frozen=True)
class FreightContext:
    """Canonical freight facts required by Same As Last qualification."""

    fingerprint: str
    location_fingerprint_origin: str
    location_fingerprint_destination: str
    serialized: str
    repeat_stream_kind: str
    repeat_stream_id: int | None
    version: str = FREIGHT_CONTEXT_VERSION


def _canonical_hash(value: dict[str, Any]) -> tuple[str, str]:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return serialized, hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _location_snapshot(partner) -> tuple[str, str]:
    """Hash a stable physical-location snapshot rather than partner ID alone."""
    snapshot = {
        "city": getattr(partner, "city", None) or "",
        "country_id": getattr(getattr(partner, "country_id", None), "id", None) or None,
        "latitude": getattr(partner, "partner_latitude", None),
        "longitude": getattr(partner, "partner_longitude", None),
        "partner_id": partner.id,
        "state_id": getattr(getattr(partner, "state_id", None), "id", None) or None,
        "street": getattr(partner, "street", None) or "",
        "street2": getattr(partner, "street2", None) or "",
        "zip": getattr(partner, "zip", None) or "",
    }
    return _canonical_hash(snapshot)


def _load_company(load):
    company = getattr(load, "company_id", None)
    if not company:
        sale_order = getattr(load, "sale_order_id", None)
        company = sale_order.company_id if sale_order and sale_order.company_id else None
    return company or None


def _has_lane_facts(load, company) -> bool:
    if not company or not load.pickup_partner_id or not load.delivery_partner_id:
        return False
    return bool(load.reference_weight and load.reference_weight > 0)


def build_freight_context(load) -> FreightContext | None:
    """Build one versioned freight context or return None for missing hard facts.

    The initial repeat stream is the canonical transaction intake relation. No
    repeat stream is inferred from lane geometry or partner identity.
    """
    company = _load_company(load)
    if not _has_lane_facts(load, company):
        return None

    transaction = load.transaction_id
    intake = transaction.intake_id if transaction and transaction.intake_id else None
    if not intake:
        return None

    origin_serialized, origin_fingerprint = _location_snapshot(load.pickup_partner_id)
    destination_serialized, destination_fingerprint = _location_snapshot(load.delivery_partner_id)
    context = {
        "company_id": company.id,
        "destination_location_fingerprint": destination_fingerprint,
        "destination_partner_id": load.delivery_partner_id.id,
        "equipment_class": None,
        "fingerprint_version": FREIGHT_CONTEXT_VERSION,
        "material_family": None,
        "origin_location_fingerprint": origin_fingerprint,
        "origin_partner_id": load.pickup_partner_id.id,
        "reference_weight_lbs": float(load.reference_weight),
        "repeat_stream": {"id": intake.id, "kind": "intake"},
        "schema_version": FREIGHT_CONTEXT_SCHEMA_VERSION,
    }
    serialized, fingerprint = _canonical_hash(context)
    # Location serializations are intentionally created above to document the
    # physical snapshot material; only digests enter the public context.
    del origin_serialized, destination_serialized
    return FreightContext(
        fingerprint=fingerprint,
        location_fingerprint_origin=origin_fingerprint,
        location_fingerprint_destination=destination_fingerprint,
        serialized=serialized,
        repeat_stream_kind="intake",
        repeat_stream_id=intake.id,
    )


def build_manual_freight_context(load) -> FreightContext | None:
    """Build the manual/buyerless context: exact company and lane, no repeat stream.

    It never reads an intake, so a load with no transaction can still carry a
    manually confirmed rate. Equipment is recorded as an explicit unknown rather
    than ``None``; an unknown class is never equal to a known one. There is no
    ``repeat_stream`` key at all, so a missing stream cannot match another one.
    """
    company = _load_company(load)
    if not _has_lane_facts(load, company):
        return None
    _origin_serialized, origin_fingerprint = _location_snapshot(load.pickup_partner_id)
    _destination_serialized, destination_fingerprint = _location_snapshot(load.delivery_partner_id)
    context = {
        "company_id": company.id,
        "destination_location_fingerprint": destination_fingerprint,
        "destination_partner_id": load.delivery_partner_id.id,
        "equipment_class": UNKNOWN_EQUIPMENT_CLASS,
        "fingerprint_version": FREIGHT_CONTEXT_MANUAL_VERSION,
        "origin_location_fingerprint": origin_fingerprint,
        "origin_partner_id": load.pickup_partner_id.id,
        "reference_weight_lbs": float(load.reference_weight),
        "schema_version": FREIGHT_CONTEXT_MANUAL_SCHEMA_VERSION,
    }
    serialized, fingerprint = _canonical_hash(context)
    return FreightContext(
        fingerprint=fingerprint,
        location_fingerprint_origin=origin_fingerprint,
        location_fingerprint_destination=destination_fingerprint,
        serialized=serialized,
        repeat_stream_kind="none",
        repeat_stream_id=None,
        version=FREIGHT_CONTEXT_MANUAL_VERSION,
    )


def build_freight_context_for_version(load, version) -> FreightContext | None:
    """Rebuild the context a load recorded. An unknown version yields no context."""
    if version == FREIGHT_CONTEXT_VERSION:
        return build_freight_context(load)
    if version == FREIGHT_CONTEXT_MANUAL_VERSION:
        return build_manual_freight_context(load)
    return None


def select_manual_rate_context(load) -> FreightContext | None:
    """Context for a manual rate: the legacy v3 context when it exists, else the manual one.

    An intake-backed load keeps its v3 fingerprint byte-for-byte; only a load with
    no repeat stream falls through to the manual branch.
    """
    return build_freight_context(load) or build_manual_freight_context(load)
