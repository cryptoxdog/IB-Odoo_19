"""Advisory LLM economic assessment over consolidated web-lead evidence.

The assessment is deliberately non-authoritative.  Deterministic admission and
classification policy remain the only automated routing authority; an adverse,
missing, or failed assessment creates a broker-visible review requirement rather
than an automatic commercial rejection.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .evidence_keys import (
    ASSESSMENT_STATUS_ASSESSED,
    ASSESSMENT_STATUS_UNAVAILABLE,
    KEY_ASSESSMENT,
    KEY_CALL_METADATA,
    KEY_CLARIFICATION_REQUESTS,
    KEY_CONFLICTS,
    KEY_CONTEXT,
    KEY_DETERMINISTIC_CLASSIFICATION,
    KEY_ECONOMIC_ELIGIBILITY_POLICY,
    KEY_ERROR,
    KEY_PROVIDER,
    KEY_QUANTITY,
    KEY_REASON,
    KEY_RECONCILED_EVIDENCE,
    KEY_SCHEMA_VERSION,
    KEY_SELLER_MATERIAL_AND_SUPPLY,
    KEY_STATUS,
    KEY_VISION,
)
from .inference_provider import InferenceProvider, call_structured_text, provider_audit_metadata, safe_provider_error

ECONOMIC_ASSESSMENT_SCHEMA_VERSION = "web-lead-economic-assessment/v1"

_SYSTEM_PROMPT = """You assess recycled-plastics brokerage opportunities after deterministic intake policy has run.
You are advisory only: do not override policy, do not invent material facts, and do not recommend automatic outreach.
Return ONLY valid JSON with this exact shape:
{
  "opportunity_signal": "strong" | "review" | "weak" | "unknown",
  "confidence": number,
  "economic_rationale": string,
  "quality_risks": [string],
  "commercial_risks": [string],
  "clarifications": [string]
}
Rules:
- Use "unknown" where evidence is insufficient.
- Treat unverified quantity, identity, contamination, pickup geography, or cadence as risks, not facts.
- A high quantity does not cancel contamination or commercial-source uncertainty.
- Do not estimate price, margin, buyer demand, or a probability without supplied evidence.
- Do not approve, reject, contact, match, create an offer, or create a partner.
"""

_ALLOWED_SIGNALS = frozenset({"strong", "review", "weak", "unknown"})


def _bounded_string_list(value: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text[:500])
        if len(result) >= limit:
            break
    return result


def _assessment_context(
    *,
    canonical_payload: Mapping[str, Any] | None,
    evidence_bundle: Mapping[str, Any] | None,
    classification: Mapping[str, Any],
    eligibility: Mapping[str, Any],
) -> dict[str, Any]:
    """Construct a PII-minimized economic evidence package for the provider."""
    canonical = dict(canonical_payload or {})
    canonical.pop("raw_payload", None)
    for contact_key in ("contact_name", "contact_email", "contact_phone"):
        canonical.pop(contact_key, None)
    evidence = dict(evidence_bundle or {})
    evidence.pop("seller", None)
    return {
        KEY_SCHEMA_VERSION: ECONOMIC_ASSESSMENT_SCHEMA_VERSION,
        KEY_SELLER_MATERIAL_AND_SUPPLY: canonical,
        KEY_RECONCILED_EVIDENCE: {
            KEY_QUANTITY: evidence.get(KEY_QUANTITY),
            KEY_CONFLICTS: evidence.get(KEY_CONFLICTS, []),
            KEY_CLARIFICATION_REQUESTS: evidence.get(KEY_CLARIFICATION_REQUESTS, []),
            KEY_VISION: evidence.get(KEY_VISION, []),
        },
        KEY_DETERMINISTIC_CLASSIFICATION: dict(classification),
        KEY_ECONOMIC_ELIGIBILITY_POLICY: dict(eligibility),
    }


def validate_economic_assessment(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Sanitize provider output into a small, stable, durable evidence record."""
    signal = str(raw.get("opportunity_signal") or "unknown").strip().lower()
    if signal not in _ALLOWED_SIGNALS:
        signal = "unknown"
    try:
        confidence = float(raw.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    rationale = str(raw.get("economic_rationale") or "").strip()[:2000]
    return {
        "opportunity_signal": signal,
        "confidence": max(0.0, min(1.0, confidence)),
        "economic_rationale": rationale,
        "quality_risks": _bounded_string_list(raw.get("quality_risks")),
        "commercial_risks": _bounded_string_list(raw.get("commercial_risks")),
        "clarifications": _bounded_string_list(raw.get("clarifications")),
    }


def evaluate_economic_opportunity(
    *,
    provider: InferenceProvider | None,
    canonical_payload: Mapping[str, Any] | None,
    evidence_bundle: Mapping[str, Any] | None,
    classification: Mapping[str, Any],
    eligibility: Mapping[str, Any],
) -> dict[str, Any]:
    """Return an auditable advisory assessment without changing lifecycle state."""
    context = _assessment_context(
        canonical_payload=canonical_payload,
        evidence_bundle=evidence_bundle,
        classification=classification,
        eligibility=eligibility,
    )
    if provider is None:
        return {
            KEY_SCHEMA_VERSION: ECONOMIC_ASSESSMENT_SCHEMA_VERSION,
            KEY_STATUS: ASSESSMENT_STATUS_UNAVAILABLE,
            KEY_REASON: "no_economic_provider_configured",
            KEY_CONTEXT: context,
        }

    try:
        raw, call_metadata = call_structured_text(
            provider,
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=json.dumps(context, sort_keys=True, default=str),
            max_tokens=1024,
        )
    except Exception as exc:
        error = safe_provider_error(exc, provider, role="economic_evaluation")
        return {
            KEY_SCHEMA_VERSION: ECONOMIC_ASSESSMENT_SCHEMA_VERSION,
            KEY_STATUS: ASSESSMENT_STATUS_UNAVAILABLE,
            KEY_REASON: "economic_provider_failed",
            KEY_PROVIDER: error[KEY_PROVIDER],
            KEY_ERROR: error[KEY_ERROR],
            KEY_CONTEXT: context,
        }

    return {
        KEY_SCHEMA_VERSION: ECONOMIC_ASSESSMENT_SCHEMA_VERSION,
        KEY_STATUS: ASSESSMENT_STATUS_ASSESSED,
        KEY_PROVIDER: provider_audit_metadata(provider, role="economic_evaluation"),
        KEY_CALL_METADATA: call_metadata,
        KEY_ASSESSMENT: validate_economic_assessment(raw),
        KEY_CONTEXT: context,
    }
