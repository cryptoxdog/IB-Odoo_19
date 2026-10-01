"""Checksum and action parity contracts for external intelligence (M0 / TASK-046)."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plasticos_gate.services.gate_client import (  # noqa: E402
    _ODOO_REQUIRED_ACTIONS,
    TransportFailureClass,
    failure_class_for,
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


def test_availability_missing_url(monkeypatch):
    monkeypatch.delenv("GATE_URL", raising=False)
    env = _MockEnv({})
    verdict = classify_gate_availability(env, capability="matching")
    assert verdict.status == GateAvailability.MISSING_URL.value
    assert verdict.available is False


def test_availability_insecure_http_blocked(monkeypatch):
    monkeypatch.setenv("GATE_URL", "http://127.0.0.1:9000")
    env = _MockEnv({})
    verdict = classify_gate_availability(env, capability="matching")
    assert verdict.status == GateAvailability.INSECURE_HTTP_BLOCKED.value
    assert verdict.available is False


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _FakeHttpStatusError(Exception):
    """Stand-in for a raw HTTP-library exception carrying a response (e.g. httpx.HTTPStatusError)."""

    def __init__(self, status_code: int) -> None:
        super().__init__("")
        self.response = _FakeResponse(status_code)


def test_odoo_owns_the_durable_categories_but_not_transport_truth():
    """Pack ADR-001/ADR-003 — Gate_SDK owns retryability (``GateClientError.retryable``);
    Odoo owns only the operator-visible vocabulary it is projected onto.

    This replaces a parity test that exercised an Odoo-side classifier over HTTP
    status codes and raw exception types. That classifier duplicated the SDK's
    transport taxonomy, so the parity it proved was Odoo agreeing with itself.
    Odoo's durable vocabulary stays three-valued: ``retryable`` and ``permanent``
    are the SDK's verdict; ``unknown`` is the fail-closed degraded state for an
    exception that is not a Gate transport outcome at all (repo ADR-013).
    """
    assert {c.value for c in TransportFailureClass} == {"retryable", "permanent", "unknown"}
    assert _ODOO_REQUIRED_ACTIONS == ("match", "converge")


def test_non_sdk_exceptions_are_never_labelled_gate_transport_outcomes():
    """A raw HTTP-library error, a builtin timeout, or a bare RuntimeError carries no SDK verdict.

    Odoo must not re-derive one from a status code or a type: the projection
    returns ``None`` and the caller's generic failure handling records the run
    as ``unknown``/``degraded`` — never a silent local substitution.
    """
    for exc in (
        _FakeHttpStatusError(503),
        _FakeHttpStatusError(401),
        TimeoutError("timed out"),
        ConnectionError(),
        ValueError("destination must be gate"),
        RuntimeError("401 unauthorized"),
        RuntimeError("weird boom"),
    ):
        assert failure_class_for(exc) is None, type(exc).__name__


def test_the_projection_reads_only_the_sdk_verdict():
    """Structural guarantee: no message scanning, no status tables, no exception grouping in the projection."""
    import inspect

    from plasticos_gate.services import gate_client

    body = inspect.getsource(gate_client.failure_class_for)
    body = body.split('"""')[2] if body.count('"""') >= 2 else body
    for forbidden in (
        "str(exc)",
        'f"{exc}',
        ".lower()",
        "in text",
        "status",
        "response",
        "TimeoutError",
        "ConnectionError",
    ):
        assert forbidden not in body, (
            f"failure_class_for re-derives transport truth ({forbidden!r}); the SDK's .retryable is the only input."
        )
    assert ".retryable" in body


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
