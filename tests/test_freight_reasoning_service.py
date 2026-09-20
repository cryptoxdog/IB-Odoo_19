"""Pure-Python regression tests for deterministic Linda explanations."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

SERVICE_PATH = Path(__file__).parents[1] / "plasticos_logistics" / "services" / "freight_reasoning.py"
SPEC = importlib.util.spec_from_file_location("freight_reasoning_service", SERVICE_PATH)
reasoning = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = reasoning
SPEC.loader.exec_module(reasoning)


def _load(**overrides):
    values = {
        "state": "ready_confirmed",
        "rate_resolution_method": False,
        "freight_context_fingerprint": False,
        "sal_decision": "not_evaluated",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_ready_load_without_resolution_is_blocked_with_existing_action():
    result = reasoning.explain_load_freight(_load())
    assert result.decision == "blocked"
    assert result.next_valid_actions == ["action_resolve_freight"]
    assert result.violations == ["no_current_freight_resolution"]


def test_sal_miss_exposes_external_delivery_unknown_without_inventing_transition():
    result = reasoning.explain_load_freight(
        _load(rate_resolution_method="manual", freight_context_fingerprint="abc", sal_decision="miss")
    )
    assert result.decision == "allowed"
    assert "outbound_delivery_unavailable" in result.unknowns
    assert result.next_valid_actions == ["action_create_freight_quote_request"]
