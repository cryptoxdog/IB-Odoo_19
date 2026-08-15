"""Reference mapper: CEG match response -> Odoo buyer-match records (TASK-004).

DELIVERABLE for cryptoxdog/IB-Odoo_19 (in scope; apply only when execution
starts). Drop into the plasticos_gate mapper and adapt imports to the module
Odoo env. Not applied in the 2026-08-14 remediations pass.

Grounds:
- Wave 3 contract break: the live CEG /v1/execute match response returns its rows
  under the key "candidates" (NOT "results"). The prior Odoo mapper read
  payload.get("results") and silently dropped every candidate.
- DEC-001 -> OPTION-B (accepted, evidence EVID-004): candidate identity is the
  namespaced CEG contract field `entity_ref` matching ^[a-z0-9_.-]+:[^\\s]+$
  (Odoo case: "res.partner:<int>"), NOT a bare res.partner id and NOT a
  Neo4j-native node id. An explicit resolver parses the ref -> buyer_partner_id.
- CEG MatchResponse / MatchCandidate contract (engine/models/payloads.py):
    MatchResponse: query_id, direction, candidates[], total_candidates,
      execution_time_ms, domain_spec_version, model_version, projection_version,
      contract_version, domain
    MatchCandidate: entity_ref, eligible(bool), score(float|None),
      score_scale("0_to_1"|"0_to_100"|"unnormalized_declared"), rank(int|None),
      failed_gates[], feature_contributions[], missing_evidence[], explanation
  NOTE: payloads carry NO packet_id/correlation_id/meta (transport-forbidden);
  those live on the chassis envelope, not the payload.

Behaviour (matches VAL-004 negative cases):
- candidates are never dropped (reads "candidates");
- buyer id is resolved from entity_ref per DEC-001 (no invented mapping);
- scores normalize to [0, 1] using the declared score_scale;
- output is sorted by normalized score, descending;
- a missing/invalid entity_ref fails that candidate SAFELY (skipped + recorded),
  never mis-attributed to the wrong res.partner.
"""

from __future__ import annotations

import re
from typing import Any

# Odoo model whose integer id is the buyer partner. Only this model is accepted;
# any other namespace fails safe (no cross-model mis-attribution).
BUYER_PARTNER_MODEL = "res.partner"
_ENTITY_REF_RE = re.compile(r"^(?P<model>[a-z0-9_.-]+):(?P<id>\S+)$")


class UnresolvableBuyerRef(ValueError):
    """Raised internally when an entity_ref cannot map to a res.partner id."""


def resolve_buyer_partner_id(entity_ref: str | None) -> int:
    """Resolve a CEG contract entity_ref to an Odoo res.partner integer id.

    DEC-001/OPTION-B: entity_ref is "<model>:<id>" (e.g. "res.partner:102").
    Accept ONLY the res.partner model; reject anything else fail-safe.
    """
    if not entity_ref or not isinstance(entity_ref, str):
        msg = "candidate has no entity_ref"
        raise UnresolvableBuyerRef(msg)
    m = _ENTITY_REF_RE.match(entity_ref.strip())
    if not m:
        msg = f"entity_ref does not match '<model>:<id>': {entity_ref!r}"
        raise UnresolvableBuyerRef(msg)
    model, raw_id = m.group("model"), m.group("id")
    if model != BUYER_PARTNER_MODEL:
        msg = f"entity_ref model {model!r} is not {BUYER_PARTNER_MODEL!r}: {entity_ref!r}"
        raise UnresolvableBuyerRef(msg)
    try:
        return int(raw_id)
    except (TypeError, ValueError) as exc:
        msg = f"entity_ref id is not an integer: {entity_ref!r}"
        raise UnresolvableBuyerRef(msg) from exc


def normalize_score(score: float | None, score_scale: str | None) -> float | None:
    """Normalize a candidate score to [0, 1] using the declared score_scale.

    None score -> None (ineligible/gated candidates may omit a score).
    unnormalized_declared -> left as-is (already a declared, comparable value);
    callers should treat it as opaque-but-orderable, not a probability.
    """
    if score is None:
        return None
    if score_scale == "0_to_1":
        return max(0.0, min(1.0, float(score)))
    if score_scale == "0_to_100":
        return max(0.0, min(1.0, float(score) / 100.0))
    # unnormalized_declared or unknown: do not fabricate a scale; return raw.
    return float(score)


def map_match_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Map a CEG match response payload into Odoo buyer-match records.

    Returns a dict with:
      - "matches":  list of buyer-match records (sorted score desc), each:
            buyer_partner_id, entity_ref, score, score_scale, normalized_score,
            eligible, rank, explanation, failed_gates, feature_contributions,
            missing_evidence
      - "unresolved": list of {entity_ref, reason} for fail-safe skips
      - "query_id", "direction", "total_candidates", "execution_time_ms",
        "domain_spec_version", "model_version", "projection_version",
        "contract_version", "domain"  (contract lineage preserved verbatim)
    """
    # Wave 3 fix: read "candidates", not "results".
    candidates = payload.get("candidates")
    if candidates is None:
        # Fail loudly on the OLD/wrong contract rather than silently emptying.
        msg = f"CEG match payload has no 'candidates' key (got keys: {sorted(payload)})"
        raise KeyError(msg)

    matches: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for cand in candidates:
        entity_ref = cand.get("entity_ref")
        try:
            buyer_partner_id = resolve_buyer_partner_id(entity_ref)
        except UnresolvableBuyerRef as exc:
            unresolved.append({"entity_ref": entity_ref, "reason": str(exc)})
            continue
        score = cand.get("score")
        score_scale = cand.get("score_scale")
        matches.append(
            {
                "buyer_partner_id": buyer_partner_id,
                "entity_ref": entity_ref,
                "score": score,
                "score_scale": score_scale,
                "normalized_score": normalize_score(score, score_scale),
                "eligible": bool(cand.get("eligible", False)),
                "rank": cand.get("rank"),
                "explanation": cand.get("explanation"),
                "failed_gates": cand.get("failed_gates", []),
                "feature_contributions": cand.get("feature_contributions", []),
                "missing_evidence": cand.get("missing_evidence", []),
            }
        )

    # Sort descending by normalized score; None scores sink to the bottom.
    matches.sort(
        key=lambda r: (r["normalized_score"] is not None, r["normalized_score"] or 0.0),
        reverse=True,
    )

    # Preserve contract lineage verbatim (do NOT invent packet_id/correlation_id here;
    # those belong to the chassis envelope, not the payload).
    return {
        "matches": matches,
        "unresolved": unresolved,
        "query_id": payload.get("query_id"),
        "direction": payload.get("direction"),
        "total_candidates": payload.get("total_candidates", len(candidates)),
        "execution_time_ms": payload.get("execution_time_ms"),
        "domain_spec_version": payload.get("domain_spec_version"),
        "model_version": payload.get("model_version"),
        "projection_version": payload.get("projection_version"),
        "contract_version": payload.get("contract_version"),
        "domain": payload.get("domain"),
    }
