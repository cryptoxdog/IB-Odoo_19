"""TASK-032: dual-write ICP controls (offline / no Odoo DB)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plasticos_gate" / "services"))

from dual_write import (  # noqa: E402
    ICP_DUAL_WRITE,
    assert_no_local_intelligence_authority,
    classify_dual_write,
    dual_write_enabled,
    plan_projection_write,
)


def _env(params: dict[str, str]):
    icp = MagicMock()
    icp.get_param.side_effect = lambda key, default=None: params.get(key, default)
    icp.sudo.return_value = icp
    env = MagicMock()
    env.__getitem__.side_effect = lambda name: {"ir.config_parameter": icp}[name]
    return env


def test_dual_write_default_off() -> None:
    env = _env({})
    assert dual_write_enabled(env) is False
    decision = classify_dual_write(env)
    assert decision.enabled is False
    assert decision.mode == "off"
    assert decision.gate_authority is True
    assert decision.local_intelligence_authority is False
    assert_no_local_intelligence_authority(decision)


def test_dual_write_opt_in() -> None:
    env = _env({ICP_DUAL_WRITE: "1"})
    assert dual_write_enabled(env) is True
    decision = classify_dual_write(env)
    assert decision.mode == "projection_audit"
    entry = plan_projection_write(
        packet_id="pkt-1",
        action="match",
        gate_payload={"candidates": []},
    )
    assert entry.status == "planned"
    assert entry.packet_id == "pkt-1"


def test_assert_rejects_local_authority() -> None:
    decision = classify_dual_write(_env({}))
    decision.local_intelligence_authority = True
    try:
        assert_no_local_intelligence_authority(decision)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "forbidden" in str(exc).lower()


def test_seed_defaults_dual_write_off() -> None:
    xml = (ROOT / "plasticos_gate" / "data" / "gate_icp_seed.xml").read_text()
    assert "plasticos.gate.dual_write_enabled" in xml
    assert '<field name="value">0</field>' in xml
