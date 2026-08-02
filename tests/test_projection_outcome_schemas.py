"""TASK-042: Odoo producer schemas for projection sync + outcome feedback."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from projection_outcome_schemas import (  # noqa: E402
    OutcomeFeedbackStore,
    ProjectionOutcomeError,
    ProjectionStore,
    validate_canonical_projection,
    validate_outcome_feedback,
    validate_sync_projection,
)

DRAFT = ROOT / "contracts" / "schemas" / "draft"
EXAMPLES = ROOT / "contracts" / "schemas" / "examples"
NEGATIVES = ROOT / "contracts" / "schemas" / "negative_examples"

SCHEMA_FILES = (
    "common.schema.yaml",
    "canonical-projection.schema.yaml",
    "sync-projection.schema.yaml",
    "outcome-feedback.schema.yaml",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_schema_files_exist() -> None:
    for name in SCHEMA_FILES:
        assert (DRAFT / name).is_file(), name


def test_canonical_fixture() -> None:
    validate_canonical_projection(_load(EXAMPLES / "canonical-projection.json"))


def test_sync_and_tombstone_fixtures() -> None:
    validate_sync_projection(_load(EXAMPLES / "sync-projection.json"))
    validate_sync_projection(_load(EXAMPLES / "sync-projection-tombstone.json"))


def test_outcome_fixture() -> None:
    validate_outcome_feedback(_load(EXAMPLES / "outcome-feedback.json"))


def test_canonical_rejects_transport() -> None:
    with pytest.raises(ProjectionOutcomeError, match="transport"):
        validate_canonical_projection(_load(NEGATIVES / "canonical-projection-transport-field.json"))


def test_sync_rejects_unknown_operation() -> None:
    with pytest.raises(ProjectionOutcomeError, match="operation"):
        validate_sync_projection(_load(NEGATIVES / "sync-projection-unknown-operation.json"))


def test_outcome_rejects_unknown_type() -> None:
    with pytest.raises(ProjectionOutcomeError, match="outcome_type"):
        validate_outcome_feedback(_load(NEGATIVES / "outcome-feedback-unknown-type.json"))


def test_sync_idempotent_and_rebuild() -> None:
    store = ProjectionStore()
    upsert = _load(EXAMPLES / "sync-projection.json")
    first = store.apply(upsert)
    assert first.accepted == ["res.partner:102"]
    second = store.apply(upsert)
    assert second.reused == ["res.partner:102"]
    tomb = _load(EXAMPLES / "sync-projection-tombstone.json")
    tomb_result = store.apply(tomb)
    assert tomb_result.accepted == ["res.partner:102"]
    assert store.get("res.partner:102") is not None
    assert store.get("res.partner:102").tombstoned is True

    rebuilt = ProjectionStore()
    rebuilt.rebuild_from(
        [
            *validate_sync_projection(upsert)["records"],
            *validate_sync_projection(tomb)["records"],
        ]
    )
    assert rebuilt.get("res.partner:102").tombstoned is True
    assert rebuilt.get("res.partner:102").revision == 9


def test_outcome_idempotent_replay() -> None:
    store = OutcomeFeedbackStore()
    payload = _load(EXAMPLES / "outcome-feedback.json")
    first = store.apply(payload)
    assert first.accepted == ["match-501-accepted-20260802"]
    second = store.apply(payload)
    assert second.reused == ["match-501-accepted-20260802"]
    assert store.get("match-501-accepted-20260802") is not None


def test_odoo_remains_authority_marker() -> None:
    text = (DRAFT / "canonical-projection.schema.yaml").read_text(encoding="utf-8")
    assert "never the business system of record" in text.lower() or "never the business" in text
    sync = (DRAFT / "sync-projection.schema.yaml").read_text(encoding="utf-8")
    assert "Odoo remains authority" in sync
