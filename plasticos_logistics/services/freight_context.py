"""Deterministic freight-context construction for governed logistics decisions.

This service owns canonical serialization and SHA-256 identities only. It never
contacts a carrier or performs a commercial action.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

FREIGHT_CONTEXT_VERSION = "freight_context_v2"
FREIGHT_CONTEXT_SCHEMA_VERSION = "2.1"


@dataclass(frozen=True)
class FreightContext:
    """Canonical freight facts required by Same As Last qualification."""

    fingerprint: str
    location_fingerprint_origin: str
    location_fingerprint_destination: str
    serialized: str
    repeat_stream_kind: str
    repeat_stream_id: int | None


def _canonical_hash(value: dict[str, Any]) -> tuple[str, str]:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return serialized, hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _location_snapshot(partner) -> tuple[str, str]:
    """Hash a stable physical-location snapshot rather than partner ID alone."""
    snapshot = {
        "address": partner.contact_address_complete or "",
        "city": partner.city or "",
        "country_id": partner.country_id.id or None,
        "latitude": getattr(partner, "partner_latitude", None),
        "longitude": getattr(partner, "partner_longitude", None),
        "partner_id": partner.id,
        "state_id": partner.state_id.id or None,
        "street": partner.street or "",
        "street2": partner.street2 or "",
        "zip": partner.zip or "",
    }
    return _canonical_hash(snapshot)


def build_freight_context(load) -> FreightContext | None:
    """Build one versioned freight context or return None for missing hard facts.

    The initial repeat stream is the canonical transaction intake relation. No
    repeat stream is inferred from lane geometry or partner identity.
    """
    company = getattr(load, "company_id", None)
    if not company:
        sale_order = getattr(load, "sale_order_id", None)
        company = sale_order.company_id if sale_order and sale_order.company_id else None
    if not company or not load.pickup_partner_id or not load.delivery_partner_id:
        return None
    if not load.reference_weight or load.reference_weight <= 0:
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
