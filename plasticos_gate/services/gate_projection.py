"""Authoritative Odoo -> Graph projection builders (post-commit, typed, allowlisted).

Graph is a derived read model. It receives a typed projection of *committed*
Odoo state, never an EIE proposal that Odoo has not yet accepted. Building the
projection here — rather than letting EIE write Graph directly — keeps a single
answer to "which system is right": Odoo.

Two defences are deliberate and not redundant:

* the property allowlist below (producer side), and
* Graph's own ontology validation at ingress (consumer side).

Graph's sync generator executes ``SET n += row``, so any key that reaches it
becomes a node property. This module refuses to emit an undeclared key at all.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

#: Graph endpoint entity type for a recycling facility node.
FACILITY_ENTITY_TYPE = "facilities"

#: Model whose primary key backs the stable Graph facility identifier.
#: Policy recorded in docs/adr/ADR-129-odoo-authoritative-graph-projection.md.
FACILITY_STABLE_ID_MODEL = "plasticos.facility.profile"

#: Every property this projection is permitted to publish. Adding a key here is
#: an ontology change and needs the Graph domain to declare it first.
FACILITY_PROJECTION_PROPERTIES = frozenset(
    {
        "facility_id",
        "entity_ref",
        "name",
        "lat",
        "lon",
        "capacity_tons_month",
        "food_grade_certified",
    }
)

#: Required on every facility row — Graph rejects a node without identity.
FACILITY_REQUIRED_PROPERTIES = ("facility_id", "entity_ref", "name")

#: Never publish contact data or developer identity into the graph, even if a
#: future allowlist edit adds them by mistake.
PROHIBITED_PROJECTION_PROPERTIES = frozenset(
    {
        "email",
        "phone",
        "mobile",
        "comment",
        "street",
        "street2",
        "vat",
        "user_id",
        "create_uid",
        "write_uid",
    }
)

#: US short ton. Capacity is stored in pounds in Odoo and published in tons.
POUNDS_PER_SHORT_TON = 2000.0

PROJECTION_CONTRACT_VERSION = "plasticos.projection.v1"


class ProjectionContractError(ValueError):
    """Raised when a projection row violates the published property contract."""


def build_facility_id(facility_profile_id: int) -> str:
    """Return the stable Graph facility identifier for a facility profile.

    Odoo has no pre-existing facility-scoped external identifier, so this is an
    explicitly adopted policy (ADR-129): the identifier is derived from the
    ``plasticos.facility.profile`` primary key, which is stable for the life of
    the database and survives partner renames and re-parenting.
    """
    return f"{FACILITY_STABLE_ID_MODEL}:{facility_profile_id}"


def _coerce_float(value: Any) -> float | None:
    if value in (None, False, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_facility_projection_row(partner, facility_profile) -> dict[str, Any] | None:
    """Build one facility projection row from committed Odoo state.

    Returns ``None`` when the partner is not a facility. Not every
    ``res.partner`` is a Graph Facility, and declaring one would poison the
    graph with non-facility nodes.
    """
    if not facility_profile or not getattr(facility_profile, "id", None):
        return None

    row: dict[str, Any] = {
        "facility_id": build_facility_id(facility_profile.id),
        "entity_ref": f"res.partner:{partner.id}",
        "name": partner.name or "",
    }

    lat = _coerce_float(getattr(partner, "partner_latitude", None))
    lon = _coerce_float(getattr(partner, "partner_longitude", None))
    # Odoo stores an ungeocoded partner as 0.0/0.0, which is a real coordinate
    # in the Gulf of Guinea. Publish nothing rather than a false location.
    if lat is not None and lon is not None and (lat, lon) != (0.0, 0.0):
        row["lat"] = lat
        row["lon"] = lon

    capacity_lbs = _coerce_float(getattr(facility_profile, "capacity_lbs_month", None))
    if capacity_lbs:
        row["capacity_tons_month"] = capacity_lbs / POUNDS_PER_SHORT_TON

    food_grade = getattr(facility_profile, "food_grade_certified", None)
    if food_grade is not None:
        row["food_grade_certified"] = bool(food_grade)

    validate_projection_row(row)
    return row


def validate_projection_row(row: dict[str, Any]) -> None:
    """Reject a row that violates the facility projection contract."""
    if not isinstance(row, dict):
        raise ProjectionContractError("projection row must be a mapping")
    keys = set(row)
    undeclared = keys - FACILITY_PROJECTION_PROPERTIES
    if undeclared:
        raise ProjectionContractError(
            f"undeclared projection properties for {FACILITY_ENTITY_TYPE}: {sorted(undeclared)}"
        )
    prohibited = keys & PROHIBITED_PROJECTION_PROPERTIES
    if prohibited:
        raise ProjectionContractError(f"prohibited projection properties: {sorted(prohibited)}")
    for required in FACILITY_REQUIRED_PROPERTIES:
        if not row.get(required):
            raise ProjectionContractError(f"projection row is missing required property {required!r}")


def build_facility_sync_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the Graph sync payload for a batch of validated facility rows."""
    for row in rows:
        validate_projection_row(row)
    return {
        "entity_type": FACILITY_ENTITY_TYPE,
        "contract_version": PROJECTION_CONTRACT_VERSION,
        "batch": list(rows),
    }


def projection_semantic_key(payload: dict[str, Any]) -> str:
    """Return the dedupe key for one projection payload.

    The key binds entity type, identity, and a hash of the projected content, so
    an unchanged projection never enqueues twice while a changed one always gets
    its own row. Graph MERGE makes a repeat send harmless; this makes it rare.
    """
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    entity_type = payload.get("entity_type") or "unknown"
    batch = payload.get("batch") or []
    identity = batch[0].get("facility_id") if len(batch) == 1 and isinstance(batch[0], dict) else "batch"
    return f"graph:{entity_type}:{identity}:{digest}"
