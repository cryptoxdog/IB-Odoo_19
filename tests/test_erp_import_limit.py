"""ERP_LIMIT parsing for diagnostic and test-database imports.

Pure-python tier (no Odoo import) — see tests/conftest.py collection rules.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plasticos_partner_import"))

from erp.limits import parse_limit, resolve_limit  # noqa: E402


def test_count_limit_is_an_integer():
    assert parse_limit("100") == 100
    assert resolve_limit(100, 9000) == 100


def test_percent_limit_is_a_fraction_resolved_against_the_source_size():
    assert parse_limit("25%") == 0.25
    assert parse_limit(" 25 % ") == 0.25
    assert resolve_limit(0.25, 8961) == 2241
    assert resolve_limit(0.25, 1) == 1


def test_empty_zero_and_full_percent_mean_no_limit():
    for raw in ("", None, "0", "0%", "100%", "abc", "-5"):
        assert parse_limit(raw) is None, raw
    assert resolve_limit(None, 10) is None
