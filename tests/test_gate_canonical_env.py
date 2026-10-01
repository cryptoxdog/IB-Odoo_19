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


_CLIENT_SRC = ROOT / "plasticos_gate" / "services" / "gate_client.py"
_CONFIG_SRC = ROOT / "plasticos_gate" / "services" / "gate_config.py"


def _code_lines(path: Path) -> list[str]:
    """Source lines that are code: comments and docstring prose may name a forbidden concept to explain it."""
    lines: list[str] = []
    in_doc = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.count('"""') == 1:
            in_doc = not in_doc
            continue
        if in_doc or stripped.startswith("#") or stripped.startswith('"""'):
            continue
        lines.append(line.split("#", 1)[0])
    return lines


def test_bridge_holds_no_transport_taxonomy_of_its_own():
    """GAP-01/02 — the SDK owns retryability; Odoo never imports httpx or re-derives it from status codes/types."""
    code = "\n".join(_code_lines(_CLIENT_SRC))
    assert "httpx" not in code
    assert "classify_transport_failure" not in code
    assert "status_code" not in code and "_RETRYABLE_STATUS" not in code and "_HTTP_" not in code
    assert "TimeoutException" not in code and "NetworkError" not in code
    # The projection reads the SDK's own verdict, nothing else.
    assert ".retryable" in code
    assert "def failure_class_for(" in code


def test_bridge_has_no_shadow_signing_or_compatibility_shim():
    """GAP-03/04 — the SDK builder parses L9_*; no Odoo keyring parser, no zero-argument shim."""
    code = "\n".join(_code_lines(_CONFIG_SRC))
    assert "get_gate_client_config_from_env(" in code
    for shadow in (
        "resolve_gate_signing",
        "_parse_verifying_keys",
        "gate_signing_configured",
        "_copy_supported_overrides",
        "_sdk_config_from_env",
        "model_copy(",
        "GateClientConfig(",
        "L9_SIGNING_KEY",
        "L9_VERIFYING_KEYS_JSON",
        "except TypeError",
    ):
        assert shadow not in code, f"gate_config.py still owns SDK configuration semantics: {shadow}"


def test_admission_is_authoritative_and_keyed():
    """GAP-05 — activate() is asked, never feature-detected, skipped, or cached as an unkeyed global."""
    code = "\n".join(_code_lines(_CLIENT_SRC))
    assert "client.activate(required_actions=_ODOO_REQUIRED_ACTIONS" in code
    assert "_activated_ok" not in code
    assert "_maybe_activate" not in code
    assert 'getattr(client, "activate"' not in code
    assert "admission_problems" not in code, "identity proof is the SDK's check inside activate(), not an Odoo pre-skip"
    assert "== 404" not in code
    assert "def _admission_key(" in code
    assert "tenant" in code.split("def _admission_key(", 1)[1].split("\n\n", 1)[0]


def test_downstream_shells_do_not_reclassify_gate_transport():
    """GAP-06 — persistence models consume the bridge's category; they never classify Gate failures themselves."""
    for rel in ("plasticos_matching/models/match_orchestrator.py", "plasticos_enrichment/models/enrichment_run.py"):
        code = "\n".join(_code_lines(ROOT / rel))
        assert "classify_transport_failure" not in code, rel
        assert "failure_class_for" not in code, rel
        assert "exc.failure_class or" in code, rel


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
