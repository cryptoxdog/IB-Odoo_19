"""Thin plasticos_gate facade for the evidence mapping consumer (TASK-053).

Policy logic lives in ``scripts.evidence_odoo_mapping_consumer`` to satisfy the
phantom-enum audit for plasticos_* modules.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Odoo 19 registers addon roots on odoo.addons.__path__ only. A top-level
# ``import scripts`` is therefore invisible at registry load. The consumer
# stays outside plasticos_* for the phantom-enum audit.
_CONSUMER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "evidence_odoo_mapping_consumer.py"
_spec = importlib.util.spec_from_file_location("evidence_odoo_mapping_consumer", _CONSUMER_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load evidence mapping consumer from {_CONSUMER_PATH}")
_consumer = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _consumer
_spec.loader.exec_module(_consumer)

EvidenceApplyInput = _consumer.EvidenceApplyInput
EvidenceOdooMapping = _consumer.EvidenceOdooMapping
MappingPolicy = _consumer.MappingPolicy
MappingProjection = _consumer.MappingProjection
OdooFieldState = _consumer.OdooFieldState
build_review_proposal = _consumer.build_review_proposal
decide_apply = _consumer.decide_apply
load_evidence_odoo_mapping = _consumer.load_evidence_odoo_mapping

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
