"""Canonical Gate consumer bind — GATE_URL + L9_* only, match+converge only."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_gate.services.gate_client import _ODOO_REQUIRED_ACTIONS  # noqa: E402
from plasticos_gate.services.gate_config import (  # noqa: E402
    GateAvailability,
    classify_gate_availability,
)


class _MockICP:
    def __init__(self, params: dict[str, str]):
        self._params = params

    def get_param(self, key: str, default=None):
        return self._params.get(key, default)


class _MockEnv:
    def __init__(self, params: dict[str, str] | None = None):
        self.cr = type("CR", (), {"dbname": "testdb"})()
        self._icp = _MockICP(params or {})

    def __getitem__(self, key: str):
        if key == "ir.config_parameter":
            return self
        raise KeyError(key)

    def sudo(self):
        return self

    def get_param(self, key: str, default=None):
        return self._icp.get_param(key, default)


def test_gate_url_unset_is_missing_url(monkeypatch):
    monkeypatch.delenv("GATE_URL", raising=False)
    verdict = classify_gate_availability(_MockEnv())
    assert verdict.status == GateAvailability.MISSING_URL.value
    assert verdict.available is False
    assert verdict.gate_url_configured is False


def test_gate_url_set_is_configured_without_icp(monkeypatch):
    monkeypatch.setenv("GATE_URL", "https://gate.example.internal")
    verdict = classify_gate_availability(_MockEnv())
    assert verdict.gate_url_configured is True
    assert verdict.status != GateAvailability.MISSING_URL.value
    if verdict.status == GateAvailability.AVAILABLE.value:
        assert verdict.available is True
    else:
        assert verdict.status == GateAvailability.SDK_MISSING.value
        assert verdict.available is False


def test_activate_requests_only_match_and_converge():
    assert _ODOO_REQUIRED_ACTIONS == ("match", "converge")
    assert "sync" not in _ODOO_REQUIRED_ACTIONS
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name != "activate":
                continue
            for kw in node.keywords:
                if kw.arg != "required_actions":
                    continue
                values = []
                if isinstance(kw.value, ast.Name):
                    continue
                if isinstance(kw.value, (ast.Tuple, ast.List)):
                    values = [elt.value for elt in kw.value.elts if isinstance(elt, ast.Constant)]
                assert set(values) <= {"match", "converge"}
                assert "sync" not in values


def test_compose_lists_only_canonical_names():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for name in (
        "GATE_URL",
        "L9_NODE_NAME",
        "L9_SIGNING_KEY",
        "L9_SIGNING_KEY_ID",
        "L9_VERIFYING_KEYS_JSON",
        "L9_REQUIRE_SIGNATURE",
    ):
        assert name in compose
    assert "PLASTICOS_GATE_" not in compose
    assert "plasticos.gate.url" not in compose
