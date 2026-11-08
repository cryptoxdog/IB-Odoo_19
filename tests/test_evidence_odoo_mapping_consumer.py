"""TASK-053: consume EIE evidence→Odoo mapping in plasticos_gate."""

from __future__ import annotations

from datetime import UTC, datetime

from plasticos_gate.services.evidence_mapping import (
    CONTRACT_PATH,
    EvidenceApplyInput,
    OdooFieldState,
    build_review_proposal,
    decide_apply,
    load_default_mapping,
)


def test_consumer_contract_loads() -> None:
    assert CONTRACT_PATH.is_file()
    contract = load_default_mapping()
    assert contract.policy.human_review_precedence is True
    assert len(contract.projections) >= 1


def test_allowlisted_evidence_proposes_review() -> None:
    contract = load_default_mapping()
    decision = decide_apply(
        contract,
        EvidenceApplyInput(
            feature_id="material.polymer_type",
            value_kind="string",
            value_state="observed",
            observed_at=datetime(2026, 8, 2, tzinfo=UTC),
        ),
        OdooFieldState(empty=True),
    )
    assert decision == "propose_review"
    proposal = build_review_proposal(
        contract,
        EvidenceApplyInput(
            feature_id="material.polymer_type",
            value_kind="string",
            value_state="observed",
        ),
        value="HDPE",
    )
    assert proposal is not None
    assert proposal["odoo_field"] == "x_polymer_type"


def test_human_approved_blocks() -> None:
    contract = load_default_mapping()
    decision = decide_apply(
        contract,
        EvidenceApplyInput(
            feature_id="material.polymer_type",
            value_kind="string",
            value_state="inferred",
        ),
        OdooFieldState(empty=False, human_approved=True, value="PET"),
    )
    assert decision == "reject_human_precedence"


def test_unlisted_rejected() -> None:
    contract = load_default_mapping()
    decision = decide_apply(
        contract,
        EvidenceApplyInput(
            feature_id="facility.unknown.metric",
            value_kind="number",
            value_state="observed",
        ),
        OdooFieldState(empty=True),
    )
    assert decision == "reject_unlisted"


def test_stale_vs_newer_odoo_field() -> None:
    contract = load_default_mapping()
    decision = decide_apply(
        contract,
        EvidenceApplyInput(
            feature_id="material.contamination_pct",
            value_kind="number",
            value_state="observed",
            observed_at=datetime(2026, 7, 1, tzinfo=UTC),
        ),
        OdooFieldState(
            empty=False,
            value=1.0,
            revised_at=datetime(2026, 8, 1, tzinfo=UTC),
        ),
    )
    assert decision == "reject_stale"
