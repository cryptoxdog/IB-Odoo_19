"""Evidence→Odoo mapping consumer helpers (outside plasticos_* for phantom-enum gate)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MappingProjection:
    feature_id: str
    odoo_model: str
    odoo_field: str
    unit: str | None
    write_mode: str
    value_kinds: tuple[str, ...]


@dataclass(frozen=True)
class MappingPolicy:
    merge_strategy: str
    review_mode: str
    default_write_mode: str
    human_review_precedence: bool


@dataclass(frozen=True)
class EvidenceOdooMapping:
    contract_version: str
    domain: str
    owner: str
    policy: MappingPolicy
    projections: tuple[MappingProjection, ...]
    rules: tuple[str, ...]

    def projection_for(self, feature_id: str) -> MappingProjection | None:
        for projection in self.projections:
            if projection.feature_id == feature_id:
                return projection
        return None


@dataclass(frozen=True)
class OdooFieldState:
    empty: bool = True
    human_approved: bool = False
    value: Any = None
    revised_at: datetime | None = None


@dataclass(frozen=True)
class EvidenceApplyInput:
    feature_id: str
    value_kind: str
    value_state: str
    observed_at: datetime | None = None


_REQUIRED_POLICY = {
    "merge_strategy": "merge_not_overwrite",
    "default_write_mode": "proposal_only",
    "human_review_precedence": True,
}
_REQUIRED_WRITE_MODE = "proposal_only"
_REQUIRED_VERSION = "1.0.0-draft"
_REQUIRED_DOMAIN = "plasticos"
_REQUIRED_OWNER = "eie"
_STALE_STATES = frozenset({"stale", "superseded"})


def load_evidence_odoo_mapping(path: Path) -> EvidenceOdooMapping:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("contract_version") != _REQUIRED_VERSION:
        raise ValueError("unsupported evidence mapping contract_version")
    if data.get("domain") != _REQUIRED_DOMAIN or data.get("owner") != _REQUIRED_OWNER:
        raise ValueError("evidence mapping domain/owner mismatch")
    policy_raw = data.get("policy") or {}
    for key, expected in _REQUIRED_POLICY.items():
        if policy_raw.get(key) != expected:
            raise ValueError(f"consumer requires {key}={expected!r}")
    projections: list[MappingProjection] = []
    for item in data.get("projections") or []:
        write_mode = item.get("write_mode")
        if write_mode != _REQUIRED_WRITE_MODE:
            raise ValueError(f"non-proposal write_mode forbidden: {write_mode}")
        projections.append(
            MappingProjection(
                feature_id=str(item["feature_id"]),
                odoo_model=str(item["odoo_model"]),
                odoo_field=str(item["odoo_field"]),
                unit=item.get("unit"),
                write_mode=write_mode,
                value_kinds=tuple(item.get("value_kinds") or ()),
            )
        )
    if not projections:
        raise ValueError("evidence mapping projections required")
    return EvidenceOdooMapping(
        contract_version=str(data["contract_version"]),
        domain=str(data["domain"]),
        owner=str(data["owner"]),
        policy=MappingPolicy(
            merge_strategy=str(policy_raw["merge_strategy"]),
            review_mode=str(policy_raw.get("review_mode") or "always"),
            default_write_mode=str(policy_raw["default_write_mode"]),
            human_review_precedence=True,
        ),
        projections=tuple(projections),
        rules=tuple(str(r) for r in (data.get("rules") or [])),
    )


def decide_apply(
    contract: EvidenceOdooMapping,
    evidence: EvidenceApplyInput,
    field_state: OdooFieldState,
) -> str:
    projection = contract.projection_for(evidence.feature_id)
    if projection is None:
        return "reject_unlisted"
    if evidence.value_kind not in projection.value_kinds:
        return "reject_kind_mismatch"
    if contract.policy.human_review_precedence and field_state.human_approved:
        return "reject_human_precedence"
    if (
        contract.policy.merge_strategy == _REQUIRED_POLICY["merge_strategy"]
        and not field_state.empty
        and field_state.revised_at is not None
        and evidence.observed_at is not None
        and evidence.observed_at < field_state.revised_at
    ):
        return "reject_stale"
    if (
        contract.policy.merge_strategy == _REQUIRED_POLICY["merge_strategy"]
        and not field_state.empty
        and evidence.value_state in _STALE_STATES
    ):
        return "reject_overwrite"
    if projection.write_mode != _REQUIRED_WRITE_MODE:
        return "reject_overwrite"
    return "propose_review"


def build_review_proposal(
    contract: EvidenceOdooMapping,
    evidence: EvidenceApplyInput,
    value: Any,
) -> dict[str, Any] | None:
    projection = contract.projection_for(evidence.feature_id)
    if projection is None:
        return None
    return {
        "feature_id": evidence.feature_id,
        "odoo_model": projection.odoo_model,
        "odoo_field": projection.odoo_field,
        "value": value,
        "value_kind": evidence.value_kind,
        "value_state": evidence.value_state,
        "write_mode": projection.write_mode,
        "decision": "propose_review",
    }
