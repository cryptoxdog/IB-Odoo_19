"""Pure-Python regression coverage for legacy rate-memory read retirement."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SERVICE_PATH = Path(__file__).parents[1] / "plasticos_logistics" / "services" / "rate_engine.py"
SPEC = importlib.util.spec_from_file_location("retired_rate_engine", SERVICE_PATH)
rate_engine = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = rate_engine
SPEC.loader.exec_module(rate_engine)


def test_legacy_rate_memory_lookup_is_fail_closed_without_orm_access():
    assert rate_engine.get_recent_lane_rate(object(), carrier_id=123, lane_key="1-2") is None


def test_legacy_rate_memory_engine_contains_no_model_query():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert 'env["plasticos.rate.memory"]' not in source
    assert ".search(" not in source
