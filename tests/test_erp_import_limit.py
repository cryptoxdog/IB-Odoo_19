"""ERP_LIMIT parsing and its resolution at the worksheet selection point.

Pure-python tier (no Odoo import) — see tests/conftest.py collection rules.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plasticos_partner_import"))

from erp.limits import parse_limit, resolve_limit, validate_limit  # noqa: E402
from erp.native_orders import PINNED_WORKSHEETS, selected_worksheets  # noqa: E402


def test_count_limit_is_an_integer():
    assert parse_limit("100") == 100
    assert resolve_limit(100, 9000) == 100


def test_percent_limit_is_a_fraction_resolved_against_the_source_size():
    assert parse_limit("25%") == 0.25
    assert parse_limit(" 25 % ") == 0.25
    assert resolve_limit(0.25, 8961) == 2241
    assert resolve_limit(0.25, 1) == 1
    assert resolve_limit(0.25, 0) == 0


def test_full_percent_is_every_worksheet_and_unset_is_no_limit():
    assert parse_limit("100%") == 1.0
    assert resolve_limit(1.0, 8961) == 8961
    for raw in ("", None, "   "):
        assert parse_limit(raw) is None, raw
    assert resolve_limit(None, 10) is None


@pytest.mark.parametrize("raw", ["0", "0%", "101%", "12.5%", "abc", "-5", "25 percent", "1e3", "%"])
def test_invalid_limit_text_is_refused_not_widened_to_a_full_import(raw):
    with pytest.raises(ValueError, match="ERP_LIMIT must be"):
        parse_limit(raw)


@pytest.mark.parametrize("value", [0, -1, 0.0, 1.5, -0.25, True, False, "25%", "100"])
def test_invalid_programmatic_limit_is_refused(value):
    with pytest.raises(ValueError, match="worksheet limit must be"):
        validate_limit(value)
    with pytest.raises(ValueError, match="worksheet limit must be"):
        resolve_limit(value, 100)


def _worksheets(count: int) -> list[str]:
    # Reversed on purpose: selection is by worksheet number, not source order.
    return [str(60000 + n) for n in reversed(range(count))]


def test_quarter_selects_the_newest_quarter_at_the_selection_point():
    selected = selected_worksheets(_worksheets(400), parse_limit("25%"))
    assert selected == [str(60000 + n) for n in range(300, 400)]


def test_quarter_rounds_up_and_keeps_the_pinned_worksheet():
    numbers = [*_worksheets(10), *PINNED_WORKSHEETS]
    # ceil(11 * 0.25) = 3 newest, plus the pinned carrier chargeback the cut dropped.
    assert selected_worksheets(numbers, 0.25) == ["60007", "60008", "60009", *PINNED_WORKSHEETS]


def test_count_and_unlimited_selection_are_unchanged():
    numbers = _worksheets(5)
    assert selected_worksheets(numbers, 2) == ["60003", "60004"]
    assert selected_worksheets(numbers, None) == numbers


@pytest.mark.parametrize("value", [0, 1.5, -1, True])
def test_selection_point_refuses_an_invalid_limit(value):
    with pytest.raises(ValueError, match="worksheet limit must be"):
        selected_worksheets(_worksheets(5), value)
