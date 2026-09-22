"""Immutable broker-approved snapshot helpers for web-lead handoff facts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from .evidence_keys import (
    KEY_ACQUISITION_STATUS,
    KEY_ATTACHMENTS,
    KEY_CANONICAL_PAYLOAD,
    KEY_CLARIFICATION_REQUESTS,
    KEY_CLASSIFICATION,
    KEY_CONFLICTS,
    KEY_CONTENT_SHA256,
    KEY_ECONOMIC_ASSESSMENT,
    KEY_EVIDENCE,
    KEY_FACILITY_ID,
    KEY_FORM_CODE,
    KEY_FORM_ID,
    KEY_ID,
    KEY_INTAKE,
    KEY_IR_ATTACHMENT_ID,
    KEY_LEAD,
    KEY_LEAD_ID,
    KEY_LOADS_PER_MONTH,
    KEY_NAME,
    KEY_PARTNER_ID,
    KEY_PENDING_COMPANY_NAME,
    KEY_POLYMER_CODE,
    KEY_POLYMER_ID,
    KEY_PROVIDER,
    KEY_PROVIDER_EXTERNAL_ID,
    KEY_QUANTITY,
    KEY_QUANTITY_PER_LOAD_LBS,
    KEY_REVIEW_NOTES,
    KEY_SCHEMA_VERSION,
    KEY_SOURCE_ID,
    KEY_SOURCE_TYPE_CODE,
    KEY_SOURCE_TYPE_ID,
)

SNAPSHOT_SCHEMA_VERSION = "web-lead-broker-snapshot/v1"


def build_snapshot_payload(
    *,
    lead: Any,
    intake: Any,
    review_notes: str | None,
) -> dict[str, Any]:
    """Build the factual, credential-free snapshot approved by a broker."""
    evidence = dict(lead.evidence_bundle or {})
    canonical = dict(lead.canonical_payload or {})
    canonical.pop("raw_payload", None)
    return {
        KEY_SCHEMA_VERSION: SNAPSHOT_SCHEMA_VERSION,
        KEY_LEAD: {
            KEY_LEAD_ID: lead.lead_id,
            KEY_PROVIDER: lead.provider_key or None,
            KEY_PROVIDER_EXTERNAL_ID: lead.provider_external_id or None,
            KEY_CANONICAL_PAYLOAD: canonical,
        },
        KEY_INTAKE: {
            KEY_ID: intake.id,
            KEY_NAME: intake.name,
            KEY_POLYMER_ID: intake.polymer_id.id if intake.polymer_id else None,
            KEY_POLYMER_CODE: intake.polymer_id.code if intake.polymer_id else None,
            KEY_FORM_ID: intake.form_id.id if intake.form_id else None,
            KEY_FORM_CODE: intake.form_id.code if intake.form_id else None,
            KEY_SOURCE_TYPE_ID: intake.source_type_id.id if intake.source_type_id else None,
            KEY_SOURCE_TYPE_CODE: intake.source_type_id.code if intake.source_type_id else None,
            KEY_QUANTITY_PER_LOAD_LBS: intake.quantity_per_load_lbs,
            KEY_LOADS_PER_MONTH: intake.loads_per_month,
            KEY_PENDING_COMPANY_NAME: intake.pending_company_name or None,
            KEY_PARTNER_ID: intake.partner_id.id if intake.partner_id else None,
            KEY_FACILITY_ID: intake.facility_id.id if intake.facility_id else None,
        },
        KEY_CLASSIFICATION: dict(lead.decision_reasons or {}),
        KEY_EVIDENCE: {
            KEY_QUANTITY: evidence.get(KEY_QUANTITY),
            KEY_CONFLICTS: evidence.get(KEY_CONFLICTS, []),
            KEY_CLARIFICATION_REQUESTS: evidence.get(KEY_CLARIFICATION_REQUESTS, []),
            KEY_ATTACHMENTS: [
                {
                    KEY_SOURCE_ID: row.get(KEY_SOURCE_ID),
                    KEY_CONTENT_SHA256: row.get(KEY_CONTENT_SHA256),
                    KEY_ACQUISITION_STATUS: row.get(KEY_ACQUISITION_STATUS),
                    KEY_IR_ATTACHMENT_ID: row.get(KEY_IR_ATTACHMENT_ID),
                }
                for row in evidence.get(KEY_ATTACHMENTS, [])
                if isinstance(row, Mapping)
            ],
            KEY_ECONOMIC_ASSESSMENT: evidence.get(KEY_ECONOMIC_ASSESSMENT),
        },
        KEY_REVIEW_NOTES: (review_notes or "").strip() or None,
    }


def snapshot_content_hash(payload: Mapping[str, Any]) -> str:
    """Create a stable content hash for immutable snapshot verification."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
