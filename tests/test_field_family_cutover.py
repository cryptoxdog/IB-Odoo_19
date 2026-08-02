"""TASK-035: field-family cutover ICP controls (offline / no Odoo DB)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plasticos_gate" / "services"))

from field_family_cutover import (  # noqa: E402
    APPROVED_FAMILY,
    ICP_CUTOVER_ENABLED,
    ICP_CUTOVER_FAMILY,
    ICP_OPERATOR_APPROVED,
    MODE_READY,
    REQUIRED_OBSERVATION_METRICS,
    assert_no_local_intelligence_restoration,
    classify_cutover,
    cutover_enabled,
    field_family_uses_gate_authority,
    observation_metrics_defined,
    operator_approved,
    recovery_disable,
)


def _env(params: dict[str, str]):
    store = dict(params)
    icp = MagicMock()

    def get_param(key, default=None):
        return store.get(key, default)

    def set_param(key, value):
        store[key] = value

    icp.get_param.side_effect = get_param
    icp.set_param.side_effect = set_param
    icp.sudo.return_value = icp
    env = MagicMock()
    env.__getitem__.side_effect = lambda name: {"ir.config_parameter": icp}[name]
    return env


def test_cutover_default_off() -> None:
    env = _env({})
    assert cutover_enabled(env) is False
    assert operator_approved(env) is False
    decision = classify_cutover(env)
    assert decision.mode == "off"
    assert decision.enabled is False
    assert decision.family == APPROVED_FAMILY
    assert decision.gate_authority is True
    assert decision.local_intelligence_authority is False
    assert_no_local_intelligence_restoration(decision)
    assert field_family_uses_gate_authority(env, APPROVED_FAMILY) is False


def test_enable_alone_insufficient() -> None:
    env = _env({ICP_CUTOVER_ENABLED: "1"})
    decision = classify_cutover(env)
    assert decision.mode == "off"
    assert "operator" in " ".join(decision.reasons).lower()


def test_ready_requires_both_flags() -> None:
    env = _env(
        {
            ICP_CUTOVER_ENABLED: "1",
            ICP_OPERATOR_APPROVED: "1",
            ICP_CUTOVER_FAMILY: "specification",
        }
    )
    decision = classify_cutover(env)
    assert decision.mode == MODE_READY
    assert decision.enabled is True
    assert field_family_uses_gate_authority(env, "specification") is True
    assert set(decision.observation_metrics) == set(REQUIRED_OBSERVATION_METRICS)


def test_blocked_family() -> None:
    env = _env(
        {
            ICP_CUTOVER_ENABLED: "1",
            ICP_OPERATOR_APPROVED: "1",
            ICP_CUTOVER_FAMILY: "supply",
        }
    )
    decision = classify_cutover(env)
    assert decision.mode == "blocked"
    assert field_family_uses_gate_authority(env, "supply") is False


def test_observation_metrics_defined_before_enable() -> None:
    metrics = observation_metrics_defined()
    assert len(metrics) >= 4
    assert "local_authority_attempt_count" in metrics


def test_recovery_disables_without_local_authority() -> None:
    env = _env(
        {
            ICP_CUTOVER_ENABLED: "1",
            ICP_OPERATOR_APPROVED: "1",
        }
    )
    decision = recovery_disable(env)
    assert decision.mode == "off"
    assert decision.local_intelligence_authority is False
    assert_no_local_intelligence_restoration(decision)


def test_assert_rejects_local_authority() -> None:
    decision = classify_cutover(_env({}))
    decision.local_intelligence_authority = True
    try:
        assert_no_local_intelligence_restoration(decision)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "forbidden" in str(exc).lower()


def test_seed_defaults_cutover_off() -> None:
    xml = (ROOT / "plasticos_gate" / "data" / "gate_icp_seed.xml").read_text()
    assert "plasticos.gate.field_family_cutover_enabled" in xml
    assert "plasticos.gate.field_family_cutover_operator_approved" in xml
    assert "param_gate_field_family_cutover_enabled" in xml
    assert ">specification<" in xml
