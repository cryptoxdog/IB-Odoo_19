"""Enrichment sweep settings and buyer selection (plasticos_enrichment/services/sweep_policy.py).

Pure Python. The module is loaded by path: importing the plasticos_enrichment
package would import its Odoo models.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "sweep_policy_under_test", ROOT / "plasticos_enrichment" / "services" / "sweep_policy.py"
)
policy = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = policy  # dataclasses resolve their module through sys.modules
_SPEC.loader.exec_module(policy)

KEYS = policy.SelectionKeys(
    capability_type_codes=frozenset({"injection_molding", "compounding", "extrusion"}),
    application_classes=frozenset({"food", "packaging"}),
    feedstock_types=frozenset({"post_industrial", "post_consumer"}),
)
NOW = datetime(2026, 11, 15, 2, 0, 0)


def _settings(params):
    return policy.read_settings(params.get, KEYS)


# ── settings ──────────────────────────────────────────────────────────────


def test_defaults_are_off_five_dollars_fifty_buyers_thirty_days():
    s = _settings({})
    assert (s.enabled, s.daily_budget_usd, s.max_candidates, s.cooldown_days) == (False, 5.0, 50, 30)
    assert s.capability_type_codes == s.capability_type_ids == ()


def test_odoo_boolean_spellings_are_read():
    for raw in ("1", "True", "true"):
        assert _settings({policy.ICP_ENABLED: raw}).enabled
    assert not _settings({policy.ICP_ENABLED: "False"}).enabled


def test_multi_values_accept_json_or_comma_lists_and_normalize():
    s = _settings(
        {
            policy.ICP_CAPABILITY_TYPE_CODES: "injection_molding, compounding",
            policy.ICP_APPLICATION_CLASSES: '["packaging"]',
            policy.ICP_CAPABILITY_TYPE_IDS: "[3, 1, 3]",
            policy.ICP_POLYMER_IDS: "7,2",
        }
    )
    assert s.capability_type_codes == ("compounding", "injection_molding")
    assert s.application_classes == ("packaging",)
    assert s.capability_type_ids == (1, 3)
    assert s.polymer_ids == (2, 7)
    assert json.loads(policy.dump_list(s.capability_type_ids)) == [1, 3]
    assert policy.dump_list([]) == ""


@pytest.mark.parametrize(
    "params",
    [
        {policy.ICP_ENABLED: "maybe"},
        {policy.ICP_DAILY_BUDGET_USD: "0"},
        {policy.ICP_DAILY_BUDGET_USD: "-1"},
        {policy.ICP_DAILY_BUDGET_USD: "nan"},
        {policy.ICP_DAILY_BUDGET_USD: "five"},
        {policy.ICP_MAX_CANDIDATES: "0"},
        {policy.ICP_MAX_CANDIDATES: "501"},
        {policy.ICP_COOLDOWN_DAYS: "-1"},
        {policy.ICP_CAPABILITY_TYPE_CODES: "injection,blow_molding"},
        {policy.ICP_FEEDSTOCK_TYPES: '["virgin"]'},
        {policy.ICP_APPLICATION_CLASSES: '{"food": 1}'},
        {policy.ICP_CAPABILITY_TYPE_IDS: "[1, 0]"},
        {policy.ICP_CAPABILITY_TYPE_IDS: "a,b"},
        {policy.ICP_POLYMER_IDS: "[true]"},
        {policy.ICP_POLYMER_IDS: "[1.5]"},
        {policy.ICP_MIN_CAPACITY_LBS_MONTH: "-5"},
    ],
)
def test_malformed_settings_fail_closed(params):
    with pytest.raises(policy.SweepSettingsError):
        _settings(params)


# ── domain ────────────────────────────────────────────────────────────────


def test_domain_selects_active_partnered_buyers_and_no_filter_widens_nothing():
    domain = policy.facility_domain(_settings({}))
    assert ("active", "=", True) in domain
    assert ("partner_id", "!=", False) in domain
    assert ("partner_id.active", "=", True) in domain
    i = domain.index("|")
    assert domain[i : i + 5] == [
        "|",
        "|",
        ("partner_id.customer_rank", ">", 0),
        ("partner_id.commercial_partner_id.customer_rank", ">", 0),
        ("partner_id.parent_id.commercial_partner_id.customer_rank", ">", 0),
    ]
    assert len(domain) == 8


def test_domain_adds_each_configured_filter():
    domain = policy.facility_domain(
        _settings(
            {
                policy.ICP_CAPABILITY_TYPE_CODES: "compounding,injection_molding",
                policy.ICP_APPLICATION_CLASSES: "food",
                policy.ICP_FEEDSTOCK_TYPES: "post_industrial",
                policy.ICP_CAPABILITY_TYPE_IDS: "4",
                policy.ICP_POLYMER_IDS: "9",
                policy.ICP_MIN_CAPACITY_LBS_MONTH: "100000",
            }
        )
    )
    assert ("capability_ids.capability_type_id.code", "in", ["compounding", "injection_molding"]) in domain
    assert ("application_class", "in", ["food"]) in domain
    assert ("feedstock_type", "in", ["post_industrial"]) in domain
    assert ("capability_ids.capability_type_id", "in", [4]) in domain
    assert (
        "partner_id.material_profile_ids",
        "any",
        [("polymer_id", "in", [9]), ("direction", "=", "in")],
    ) in domain
    assert ("capacity_lbs_month", ">=", 100000) in domain


# ── ordering, cooldown, cap ───────────────────────────────────────────────


def _h(fid, days_ago=None, **kw):
    when = None if days_ago is None else NOW - timedelta(days=days_ago)
    return policy.FacilityHistory(facility_id=fid, last_enriched_at=when, **kw)


def test_never_enriched_first_then_oldest_then_id():
    history = [_h(5, 40), _h(3), _h(9, 90), _h(1), _h(2, 40)]
    assert policy.order_candidates(history, now=NOW, cooldown_days=30, cap=10) == [1, 3, 9, 2, 5]


def test_cooldown_review_and_pending_are_excluded():
    history = [_h(1, 10), _h(2, 31), _h(3, in_review=True), _h(4, 100, pending_in_sweep=True), _h(5)]
    assert policy.order_candidates(history, now=NOW, cooldown_days=30, cap=10) == [5, 2]


def test_zero_cooldown_keeps_recent_but_never_review():
    history = [_h(1, 0), _h(2, in_review=True)]
    assert policy.order_candidates(history, now=NOW, cooldown_days=0, cap=10) == [1]


def test_cap_is_applied_after_ordering_and_is_deterministic():
    history = [_h(i) for i in range(10, 0, -1)]
    first = policy.order_candidates(history, now=NOW, cooldown_days=30, cap=3)
    assert first == [1, 2, 3]
    assert first == policy.order_candidates(list(reversed(history)), now=NOW, cooldown_days=30, cap=3)
    assert policy.order_candidates(history, now=NOW, cooldown_days=30, cap=0) == []
