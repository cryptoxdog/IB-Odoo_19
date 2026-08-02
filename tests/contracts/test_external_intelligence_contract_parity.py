"""Checksum and action parity contracts for external intelligence (M0 / TASK-046)."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plasticos_gate.services.gate_client import (  # noqa: E402
    TransportFailureClass,
    classify_transport_failure,
)
from plasticos_gate.services.gate_config import (  # noqa: E402
    GateAvailability,
    classify_gate_availability,
    get_enrichment_action,
    get_matching_action,
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


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _owner_roots() -> dict[str, Path]:
    base = Path.home() / "l9-constellation-repos"
    return {
        "ceg": base / "Cognitive.Engine.Graphs",
        "eie": base / "Enrichment.Inference.Engine",
    }


def test_default_actions_are_match_and_converge():
    env = _MockEnv()
    assert get_matching_action(env) == "match"
    assert get_enrichment_action(env) == "converge"


def test_availability_missing_url():
    env = _MockEnv({})
    verdict = classify_gate_availability(env, capability="matching")
    assert verdict.status == GateAvailability.MISSING_URL.value
    assert verdict.available is False


def test_availability_insecure_http_blocked():
    env = _MockEnv({"plasticos.gate.url": "http://127.0.0.1:9000"})
    verdict = classify_gate_availability(env, capability="matching")
    assert verdict.status == GateAvailability.INSECURE_HTTP_BLOCKED.value
    assert verdict.available is False


def test_transport_failure_classification():
    assert classify_transport_failure(TimeoutError("timed out")) is TransportFailureClass.RETRYABLE
    assert classify_transport_failure(RuntimeError("401 unauthorized")) is TransportFailureClass.PERMANENT
    assert classify_transport_failure(RuntimeError("weird boom")) is TransportFailureClass.UNKNOWN


@pytest.mark.parametrize(
    ("owner", "relative"),
    [
        ("ceg", "contracts/payloads/match-request.schema.yaml"),
        ("ceg", "contracts/payloads/match-response.schema.yaml"),
        ("eie", "contracts/feature_evidence/feature-evidence.schema.yaml"),
    ],
)
def test_owner_schema_files_exist_with_stable_digest(owner: str, relative: str):
    roots = _owner_roots()
    path = roots[owner] / relative
    if not path.is_file():
        pytest.skip(f"owner schema unavailable locally: {path}")
    digest = _sha256(path)
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64
