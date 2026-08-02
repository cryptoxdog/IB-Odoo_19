"""Deterministic Odoo outcome-replay input schema for CEG consumers (TASK-033/058)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_ID = "l9.odoo.outcome_replay_input.v1"
SCHEMA_VERSION = "1.0.0"

REQUIRED_EVENT_FIELDS = (
    "tenant",
    "action",
    "packet_id",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def content_hash(document_without_hash: dict[str, Any]) -> str:
    """SHA-256 over canonical JSON of the document excluding content_hash itself."""
    payload = {k: v for k, v in document_without_hash.items() if k != "content_hash"}
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    missing = [f for f in REQUIRED_EVENT_FIELDS if not str(raw.get(f) or "").strip()]
    if missing:
        raise ValueError(f"replay event missing required fields: {missing}")
    event = {
        "tenant": str(raw["tenant"]).strip(),
        "action": str(raw["action"]).strip(),
        "packet_id": str(raw["packet_id"]).strip(),
    }
    if raw.get("correlation_id") is not None:
        event["correlation_id"] = str(raw["correlation_id"])
    if raw.get("source_model") is not None:
        event["source_model"] = str(raw["source_model"])
    if raw.get("source_id") is not None:
        event["source_id"] = str(raw["source_id"])
    if raw.get("observed_at") is not None:
        event["observed_at"] = str(raw["observed_at"])
    if isinstance(raw.get("payload"), dict):
        # Nested payload kept but canonicalized via sorted serialization later.
        event["payload"] = raw["payload"]
    return event


def build_replay_document(
    *,
    events: list[dict[str, Any]],
    producer: str = "odoo.outcome_replay_export",
    producer_task: str = "TASK-057",
    notes: str | None = None,
) -> dict[str, Any]:
    """Build a Gate-mutation-free replay input document with content hash."""
    if not isinstance(events, list):
        raise TypeError("events must be a list")
    normalized = [normalize_event(e) for e in events]
    # Stable order: packet_id then action then tenant
    normalized.sort(key=lambda e: (e["packet_id"], e["action"], e["tenant"]))
    doc: dict[str, Any] = {
        "schema": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "producer": producer,
        "producer_task": producer_task,
        "gate_mutation": False,
        "event_count": len(normalized),
        "events": normalized,
    }
    if notes:
        doc["notes"] = notes
    doc["content_hash"] = content_hash(doc)
    return doc
