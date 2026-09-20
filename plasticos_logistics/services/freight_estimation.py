"""Deterministic, Haversine-weighted freight estimate calculation for Linda.

This module is deliberately local math rather than matching, enrichment, an LLM,
or a carrier-award engine.  It converts a bounded set of canonical, executed
lane outcomes into a nonbinding distribution that an operator may inspect.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from math import exp
from typing import TypedDict

from .freight_geometry import haversine_miles

ESTIMATOR_MODEL_VERSION = "linda-haversine-curve-v1"
ESTIMATOR_POLICY_VERSION = "linda-local-estimate-v1"
RECENCY_HALF_LIFE_DAYS = 180.0
MIN_DISTANCE_MILES = 1.0


@dataclass(frozen=True)
class FreightEvidence:
    """One canonical historical outcome normalized for deterministic estimation."""

    source_load_id: int
    carrier_id: int | None
    amount: float
    currency_id: int
    origin_latitude: float
    origin_longitude: float
    destination_latitude: float
    destination_longitude: float
    occurred_at: datetime
    evidence_kind: str


@dataclass(frozen=True)
class FreightEstimateProposal:
    """A local estimate result suitable for immutable Odoo persistence."""

    status: str
    failure_code: str | None
    haversine_miles: float | None
    currency_id: int | None
    estimate_floor: float | None
    estimate_target: float | None
    estimate_ceiling: float | None
    pricing_assumption: float | None
    confidence: float | None
    method: str | None
    request_fingerprint: str
    evidence_summary: dict
    reasoning_summary: dict


class WeightedEvidence(TypedDict):
    item: FreightEvidence
    weight: float
    origin_delta_miles: float
    destination_delta_miles: float
    lane_length_delta_miles: float
    historical_lane_miles: float
    age_days: float
    exact_lane: bool


def estimate_haversine_curve(
    *,
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
    currency_id: int,
    evidence: Iterable[FreightEvidence],
    now: datetime | None = None,
) -> FreightEstimateProposal:
    """Estimate a distribution using Haversine lane similarity and recency.

    The curve has no embedded dollar-per-mile, fuel, road-distance, or market
    coefficient.  Each observation's influence is derived from its geographic
    similarity to the requested lane and its observed age.  The returned range
    is the observed weighted population range, not a promise of market price.
    """
    now = _utc(now or datetime.now(UTC))
    current_lane_miles = haversine_miles(origin_latitude, origin_longitude, destination_latitude, destination_longitude)
    normalized = [item for item in evidence if item.currency_id == currency_id and item.amount > 0]
    if not normalized:
        return _insufficient_proposal(
            current_lane_miles,
            "insufficient_matching_currency_evidence",
            currency_id,
            evidence_count=0,
        )

    weighted_rows: list[WeightedEvidence] = []
    for item in normalized:
        historical_lane_miles = haversine_miles(
            item.origin_latitude,
            item.origin_longitude,
            item.destination_latitude,
            item.destination_longitude,
        )
        origin_delta = haversine_miles(origin_latitude, origin_longitude, item.origin_latitude, item.origin_longitude)
        destination_delta = haversine_miles(
            destination_latitude,
            destination_longitude,
            item.destination_latitude,
            item.destination_longitude,
        )
        lane_length_delta = abs(historical_lane_miles - current_lane_miles)
        lane_distance = origin_delta + destination_delta + lane_length_delta
        age_days = max(0.0, (now - _utc(item.occurred_at)).total_seconds() / 86400.0)
        geographic_weight = 1.0 / max(lane_distance, MIN_DISTANCE_MILES)
        recency_weight = exp(-age_days / RECENCY_HALF_LIFE_DAYS)
        weight = geographic_weight * recency_weight
        weighted_rows.append(
            {
                "item": item,
                "weight": weight,
                "origin_delta_miles": origin_delta,
                "destination_delta_miles": destination_delta,
                "lane_length_delta_miles": lane_length_delta,
                "historical_lane_miles": historical_lane_miles,
                "age_days": age_days,
                "exact_lane": lane_distance <= MIN_DISTANCE_MILES,
            }
        )

    total_weight = sum(row["weight"] for row in weighted_rows)
    target = sum(row["item"].amount * row["weight"] for row in weighted_rows) / total_weight
    floor = min(row["item"].amount for row in weighted_rows)
    ceiling = max(row["item"].amount for row in weighted_rows)
    exact_count = sum(1 for row in weighted_rows if row["exact_lane"])
    confidence = _confidence(weighted_rows, exact_count)
    method = "exact_lane" if exact_count == len(weighted_rows) else "hybrid" if exact_count else "similar_lane"
    payload = {
        "currency_id": currency_id,
        "current_lane_miles": round(current_lane_miles, 6),
        "evidence": [_fingerprint_row(row) for row in weighted_rows],
        "model_version": ESTIMATOR_MODEL_VERSION,
        "policy_version": ESTIMATOR_POLICY_VERSION,
    }
    return FreightEstimateProposal(
        status="succeeded",
        failure_code=None,
        haversine_miles=current_lane_miles,
        currency_id=currency_id,
        estimate_floor=floor,
        estimate_target=target,
        estimate_ceiling=ceiling,
        pricing_assumption=target,
        confidence=confidence,
        method=method,
        request_fingerprint=_sha256(payload),
        evidence_summary={
            "estimator": ESTIMATOR_MODEL_VERSION,
            "exact_lane_executed_count": exact_count,
            "similar_lane_executed_count": len(weighted_rows) - exact_count,
            "evidence_count": len(weighted_rows),
            "newest_evidence_age_days": round(min(row["age_days"] for row in weighted_rows), 3),
            "oldest_evidence_age_days": round(max(row["age_days"] for row in weighted_rows), 3),
            "coordinate_quality": "available",
            "currency_id": currency_id,
        },
        reasoning_summary={
            "formula": "inverse_haversine_lane_distance_times_exponential_recency",
            "current_lane_haversine_miles": round(current_lane_miles, 6),
            "range_basis": "minimum_and_maximum_observed_matching_currency_outcomes",
            "pricing_assumption_basis": "weighted_target_no_embedded_commercial_margin",
            "candidate_rows": [
                {
                    "source_load_id": row["item"].source_load_id,
                    "evidence_kind": row["item"].evidence_kind,
                    "origin_delta_miles": round(row["origin_delta_miles"], 6),
                    "destination_delta_miles": round(row["destination_delta_miles"], 6),
                    "lane_length_delta_miles": round(row["lane_length_delta_miles"], 6),
                    "age_days": round(row["age_days"], 3),
                    "weight": round(row["weight"], 12),
                }
                for row in weighted_rows
            ],
        },
    )


def _confidence(rows: list[WeightedEvidence], exact_count: int) -> float:
    """Return a transparent evidence-coverage score; never a model-confidence claim."""
    evidence_coverage = min(1.0, len(rows) / 10.0)
    exact_lane_coverage = exact_count / len(rows)
    recency = sum(exp(-row["age_days"] / RECENCY_HALF_LIFE_DAYS) for row in rows) / len(rows)
    return round((evidence_coverage + exact_lane_coverage + recency) / 3.0, 6)


def _insufficient_proposal(
    miles: float, failure_code: str, currency_id: int, *, evidence_count: int
) -> FreightEstimateProposal:
    payload = {
        "currency_id": currency_id,
        "current_lane_miles": round(miles, 6),
        "failure_code": failure_code,
        "model_version": ESTIMATOR_MODEL_VERSION,
    }
    return FreightEstimateProposal(
        status="insufficient_evidence",
        failure_code=failure_code,
        haversine_miles=miles,
        currency_id=None,
        estimate_floor=None,
        estimate_target=None,
        estimate_ceiling=None,
        pricing_assumption=None,
        confidence=None,
        method=None,
        request_fingerprint=_sha256(payload),
        evidence_summary={
            "estimator": ESTIMATOR_MODEL_VERSION,
            "exact_lane_executed_count": 0,
            "similar_lane_executed_count": 0,
            "evidence_count": evidence_count,
            "coordinate_quality": "available",
            "currency_id": currency_id,
        },
        reasoning_summary={
            "formula": "inverse_haversine_lane_distance_times_exponential_recency",
            "reason": failure_code,
        },
    )


def _fingerprint_row(row: WeightedEvidence) -> dict:
    item = row["item"]
    return {
        "source_load_id": item.source_load_id,
        "amount": item.amount,
        "currency_id": item.currency_id,
        "occurred_at": _utc(item.occurred_at).isoformat(),
        "evidence_kind": item.evidence_kind,
        "origin_delta_miles": round(row["origin_delta_miles"], 6),
        "destination_delta_miles": round(row["destination_delta_miles"], 6),
        "lane_length_delta_miles": round(row["lane_length_delta_miles"], 6),
    }


def _sha256(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
