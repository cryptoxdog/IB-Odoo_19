"""Typed Odoo client-side contracts for Gate-routed intelligence calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class OdooContext:
    model: str
    record_id: int
    company_id: int | None = None
    user_id: int | None = None
    db_name: str | None = None
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "model": self.model,
            "record_id": self.record_id,
            "company_id": self.company_id,
            "user_id": self.user_id,
            "db_name": self.db_name,
            "correlation_id": self.correlation_id,
        }
        return {k: v for k, v in data.items() if v not in (None, "")}


@dataclass(slots=True)
class ConvergeRequest:
    entity_id: str
    domain: str
    entity_snapshot: dict[str, Any] = field(default_factory=dict)
    odoo: dict[str, Any] = field(default_factory=dict)
    profile_id: str | None = None
    max_passes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "entity_id": self.entity_id,
            "domain": self.domain,
            "entity_snapshot": self.entity_snapshot,
            "odoo": self.odoo,
        }
        if self.profile_id:
            data["profile_id"] = self.profile_id
        if self.max_passes is not None:
            data["max_passes"] = self.max_passes
        return data


@dataclass(slots=True)
class ConvergeResponse:
    run_id: str | None = None
    status: str | None = None
    pass_count: int | None = None
    final_fields: dict[str, Any] = field(default_factory=dict)
    writeback: dict[str, Any] = field(default_factory=dict)
    total_tokens: int | None = None
    total_cost_usd: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MatchRequest:
    query: dict[str, Any]
    match_direction: str = "intake_to_buyer"
    top_n: int = 20
    odoo: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "query": self.query,
            "match_direction": self.match_direction,
            "top_n": self.top_n,
        }
        if self.odoo:
            data["odoo"] = self.odoo
        return data


@dataclass(slots=True)
class MatchCandidate:
    buyer_partner_id: int | None = None
    entity_ref: str | None = None
    buyer_name: str | None = None
    facility_profile_id: int | None = None
    score: float | None = None
    score_scale: str | None = None
    normalized_score: float | None = None
    eligible: bool = False
    rank: int | None = None
    reason: str | None = None
    typical_price: float | None = None
    gates_passed: list[str] = field(default_factory=list)
    gates_failed: list[str] = field(default_factory=list)
    feature_contributions: list[Any] = field(default_factory=list)
    missing_evidence: list[Any] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MatchResponse:
    status: str | None = None
    match_direction: str | None = None
    top_n: int | None = None
    results: list[MatchCandidate] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    query_id: str | None = None
    total_candidates: int | None = None
    execution_time_ms: int | None = None
    domain_spec_version: str | None = None
    model_version: str | None = None
    projection_version: str | None = None
    contract_version: str | None = None
    domain: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProcessWebLeadRequest:
    lead_id: str
    domain: str
    source: str
    raw_payload: dict[str, Any]
    normalized_seed: dict[str, Any]
    odoo: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "lead_id": self.lead_id,
            "domain": self.domain,
            "source": self.source,
            "raw_payload": self.raw_payload,
            "normalized_seed": self.normalized_seed,
        }
        if self.odoo:
            data["odoo"] = self.odoo
        return data


@dataclass(slots=True)
class ProcessWebLeadResponse:
    status: str | None = None
    classification: dict[str, Any] = field(default_factory=dict)
    normalized: dict[str, Any] = field(default_factory=dict)
    intake_candidate: dict[str, Any] = field(default_factory=dict)
    recommended_action: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProcessIntakeRequest:
    intake_id: int
    domain: str
    intake_snapshot: dict[str, Any]
    odoo: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "intake_id": self.intake_id,
            "domain": self.domain,
            "intake_snapshot": self.intake_snapshot,
        }
        if self.odoo:
            data["odoo"] = self.odoo
        return data


@dataclass(slots=True)
class ProcessIntakeResponse:
    status: str | None = None
    normalized: dict[str, Any] = field(default_factory=dict)
    match_query: dict[str, Any] = field(default_factory=dict)
    recommended_next_action: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
