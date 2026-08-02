#!/usr/bin/env python3
"""Odoo projection + outcome schema producer validators (TASK-042).

Compiles canonical-projection, sync-projection, and outcome-feedback payload
contracts for which Odoo remains the business system of record. CEG consumes
rebuildable projections; outcomes are idempotent by key.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

ENTITY_REF = re.compile(r"^[a-z0-9_.-]+:[^\s]+$")

FORBIDDEN_TRANSPORT = frozenset(
    {
        "packet_uuid",
        "packet_type",
        "tenant_uuid",
        "tenant_id",
        "correlation_id",
        "causation_id",
        "hop_trace",
        "transport_hash",
        "signature",
        "source_node",
        "destination_node",
    }
)

CANONICAL_ENTITY_TYPES = frozenset(
    {
        "material_specification",
        "material_observation",
        "supply_opportunity",
        "buyer_demand",
        "facility_material_rule",
        "capacity_observation",
    }
)

OUTCOME_TYPES = frozenset(
    {
        "reviewed",
        "contacted",
        "quoted",
        "accepted",
        "rejected",
        "completed",
        "claim_raised",
        "paid",
        "repeat_business",
    }
)

SYNC_OPS = frozenset({"upsert", "tombstone"})
SOURCE_SYSTEMS = frozenset({"odoo", "eie", "ceg", "operator", "external_source"})


class ProjectionOutcomeError(ValueError):
    """Raised when a projection/outcome payload violates producer rules."""


def _require_entity_ref(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not ENTITY_REF.match(value):
        raise ProjectionOutcomeError(f"invalid {field_name}")
    return value


def _reject_transport(payload: dict[str, Any]) -> None:
    hit = FORBIDDEN_TRANSPORT.intersection(payload)
    if hit:
        raise ProjectionOutcomeError(f"transport fields forbidden: {sorted(hit)}")


def _parse_source(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise ProjectionOutcomeError("source_record must be an object")
    system = source.get("system")
    if system not in SOURCE_SYSTEMS:
        raise ProjectionOutcomeError("source_record.system invalid")
    record_ref = _require_entity_ref(source.get("record_ref"), field_name="source_record.record_ref")
    revision = source.get("revision", 0)
    if not isinstance(revision, (int, str)) or isinstance(revision, bool):
        raise ProjectionOutcomeError("source_record.revision invalid")
    return {"system": system, "record_ref": record_ref, "revision": revision}


def validate_canonical_projection(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ProjectionOutcomeError("payload must be an object")
    _reject_transport(payload)
    if payload.get("contract_version") != "1.0.0-draft":
        raise ProjectionOutcomeError("contract_version must be 1.0.0-draft")
    if payload.get("domain") != "plasticos":
        raise ProjectionOutcomeError("domain must be plasticos")
    entity_ref = _require_entity_ref(payload.get("entity_ref"), field_name="entity_ref")
    entity_type = payload.get("entity_type")
    if entity_type not in CANONICAL_ENTITY_TYPES:
        raise ProjectionOutcomeError("entity_type invalid")
    revision = payload.get("revision")
    if not isinstance(revision, (int, str)) or isinstance(revision, bool):
        raise ProjectionOutcomeError("revision invalid")
    source_record = _parse_source(payload.get("source_record"))
    for key in ("projection_version", "field_dictionary_version"):
        if not isinstance(payload.get(key), str) or not payload.get(key):
            raise ProjectionOutcomeError(f"{key} required")
    if not isinstance(payload.get("properties"), dict):
        raise ProjectionOutcomeError("properties must be an object")
    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at:
        raise ProjectionOutcomeError("generated_at required")
    # Soft-parse ISO datetime
    try:
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProjectionOutcomeError("generated_at must be date-time") from exc
    for list_key in ("relationship_refs", "evidence_refs"):
        refs = payload.get(list_key) or []
        if not isinstance(refs, list):
            raise ProjectionOutcomeError(f"{list_key} must be array")
        seen: set[str] = set()
        for ref in refs:
            parsed = _require_entity_ref(ref, field_name=list_key)
            if parsed in seen:
                raise ProjectionOutcomeError(f"{list_key} must be unique")
            seen.add(parsed)
    tombstone = payload.get("tombstone", False)
    if not isinstance(tombstone, bool):
        raise ProjectionOutcomeError("tombstone must be boolean")
    return {
        "entity_ref": entity_ref,
        "entity_type": entity_type,
        "revision": revision,
        "source_record": source_record,
        "tombstone": tombstone,
        "projection_version": payload["projection_version"],
    }


def validate_sync_projection(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ProjectionOutcomeError("payload must be an object")
    _reject_transport(payload)
    if payload.get("contract_version") != "1.0.0-draft":
        raise ProjectionOutcomeError("contract_version must be 1.0.0-draft")
    if payload.get("domain") != "plasticos":
        raise ProjectionOutcomeError("domain must be plasticos")
    if not isinstance(payload.get("projection_version"), str) or not payload.get("projection_version"):
        raise ProjectionOutcomeError("projection_version required")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ProjectionOutcomeError("records required")
    normalized: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise ProjectionOutcomeError("record must be object")
        entity_ref = _require_entity_ref(record.get("entity_ref"), field_name="entity_ref")
        if not isinstance(record.get("entity_type"), str) or not record.get("entity_type"):
            raise ProjectionOutcomeError("entity_type required")
        revision = record.get("revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise ProjectionOutcomeError("revision must be non-negative int")
        operation = record.get("operation")
        if operation not in SYNC_OPS:
            raise ProjectionOutcomeError("operation invalid")
        if not isinstance(record.get("properties"), dict):
            raise ProjectionOutcomeError("properties must be object")
        source_record = _parse_source(record.get("source_record"))
        if not isinstance(record.get("field_dictionary_version"), str) or not record.get("field_dictionary_version"):
            raise ProjectionOutcomeError("field_dictionary_version required")
        for list_key in ("relationship_refs", "evidence_refs"):
            refs = record.get(list_key) or []
            if not isinstance(refs, list):
                raise ProjectionOutcomeError(f"{list_key} must be array")
            for ref in refs:
                _require_entity_ref(ref, field_name=list_key)
        normalized.append(
            {
                "entity_ref": entity_ref,
                "entity_type": record["entity_type"],
                "revision": revision,
                "operation": operation,
                "properties": record["properties"],
                "source_record": source_record,
                "field_dictionary_version": record["field_dictionary_version"],
            }
        )
    return {"projection_version": payload["projection_version"], "records": normalized}


def validate_outcome_feedback(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ProjectionOutcomeError("payload must be an object")
    _reject_transport(payload)
    if payload.get("contract_version") != "1.0.0-draft":
        raise ProjectionOutcomeError("contract_version must be 1.0.0-draft")
    if payload.get("domain") != "plasticos":
        raise ProjectionOutcomeError("domain must be plasticos")
    outcomes = payload.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        raise ProjectionOutcomeError("outcomes required")
    normalized: list[dict[str, Any]] = []
    for item in outcomes:
        if not isinstance(item, dict):
            raise ProjectionOutcomeError("outcome item must be object")
        match_result_ref = _require_entity_ref(item.get("match_result_ref"), field_name="match_result_ref")
        candidate_ref = _require_entity_ref(item.get("candidate_ref"), field_name="candidate_ref")
        outcome_type = item.get("outcome_type")
        if outcome_type not in OUTCOME_TYPES:
            raise ProjectionOutcomeError("outcome_type invalid")
        occurred_at = item.get("occurred_at")
        if not isinstance(occurred_at, str) or not occurred_at:
            raise ProjectionOutcomeError("occurred_at required")
        datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
        source_record = _parse_source(item.get("source_record"))
        key = item.get("idempotency_key")
        if not isinstance(key, str) or not key:
            raise ProjectionOutcomeError("idempotency_key required")
        details = item.get("details") or {}
        if not isinstance(details, dict):
            raise ProjectionOutcomeError("details must be object")
        normalized.append(
            {
                "match_result_ref": match_result_ref,
                "candidate_ref": candidate_ref,
                "outcome_type": outcome_type,
                "occurred_at": occurred_at,
                "source_record": source_record,
                "idempotency_key": key,
                "details": details,
            }
        )
    return {"outcomes": normalized}


@dataclass
class ProjectionEntry:
    entity_ref: str
    revision: int
    tombstoned: bool
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncApplyResult:
    accepted: list[str] = field(default_factory=list)
    reused: list[str] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)


class ProjectionStore:
    """In-memory rebuildable projection store (Odoo remains SoR)."""

    def __init__(self) -> None:
        self._entries: dict[str, ProjectionEntry] = {}

    def get(self, entity_ref: str) -> ProjectionEntry | None:
        return self._entries.get(entity_ref)

    def apply(self, payload: dict[str, Any]) -> SyncApplyResult:
        validated = validate_sync_projection(payload)
        result = SyncApplyResult()
        for record in validated["records"]:
            existing = self._entries.get(record["entity_ref"])
            if existing is not None and record["revision"] < existing.revision:
                result.rejected.append({"entity_ref": record["entity_ref"], "reason": "stale_revision"})
                continue
            if (
                existing is not None
                and record["revision"] == existing.revision
                and record["operation"] == ("tombstone" if existing.tombstoned else "upsert")
            ):
                result.reused.append(record["entity_ref"])
                continue
            self._entries[record["entity_ref"]] = ProjectionEntry(
                entity_ref=record["entity_ref"],
                revision=record["revision"],
                tombstoned=record["operation"] == "tombstone",
                properties={} if record["operation"] == "tombstone" else dict(record["properties"]),
            )
            result.accepted.append(record["entity_ref"])
        return result

    def rebuild_from(self, records: list[dict[str, Any]]) -> None:
        self._entries.clear()
        ordered = sorted(records, key=lambda r: (r["entity_ref"], r["revision"]))
        for record in ordered:
            self.apply(
                {
                    "contract_version": "1.0.0-draft",
                    "domain": "plasticos",
                    "projection_version": "1.0.0",
                    "records": [record],
                }
            )


@dataclass
class OutcomeApplyResult:
    accepted: list[str] = field(default_factory=list)
    reused: list[str] = field(default_factory=list)


class OutcomeFeedbackStore:
    def __init__(self) -> None:
        self._by_key: dict[str, dict[str, Any]] = {}

    def apply(self, payload: dict[str, Any]) -> OutcomeApplyResult:
        validated = validate_outcome_feedback(payload)
        result = OutcomeApplyResult()
        for item in validated["outcomes"]:
            key = item["idempotency_key"]
            if key in self._by_key:
                result.reused.append(key)
                continue
            self._by_key[key] = item
            result.accepted.append(key)
        return result

    def get(self, key: str) -> dict[str, Any] | None:
        return self._by_key.get(key)
