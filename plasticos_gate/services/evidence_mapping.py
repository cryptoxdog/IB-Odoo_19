"""Thin plasticos_gate facade for the evidence mapping consumer (TASK-053).

Policy logic lives in ``scripts.evidence_odoo_mapping_consumer`` to satisfy the
phantom-enum audit for plasticos_* modules.
"""

from __future__ import annotations

from pathlib import Path

from scripts.evidence_odoo_mapping_consumer import (
    EvidenceApplyInput,
    EvidenceOdooMapping,
    MappingPolicy,
    MappingProjection,
    OdooFieldState,
    build_review_proposal,
    decide_apply,
    load_evidence_odoo_mapping,
)

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "data" / "evidence_odoo_mapping.json"


def load_default_mapping() -> EvidenceOdooMapping:
    return load_evidence_odoo_mapping(CONTRACT_PATH)


__all__ = [
    "CONTRACT_PATH",
    "EvidenceApplyInput",
    "EvidenceOdooMapping",
    "MappingPolicy",
    "MappingProjection",
    "OdooFieldState",
    "build_review_proposal",
    "decide_apply",
    "load_default_mapping",
    "load_evidence_odoo_mapping",
]
