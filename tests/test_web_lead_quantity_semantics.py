"""Pure component tests for canonical quantity and bounded AI JSON behavior."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "plasticos_web_leads"

package = sys.modules.setdefault("plasticos_web_leads", types.ModuleType("plasticos_web_leads"))
package.__path__ = [str(PACKAGE_ROOT)]
models_package = sys.modules.setdefault("plasticos_web_leads.models", types.ModuleType("plasticos_web_leads.models"))
models_package.__path__ = [str(PACKAGE_ROOT / "models")]

from plasticos_web_leads.models.ai_client import call_json_with_retry, extract_json  # noqa: E402
from plasticos_web_leads.models.quantity_normalizer import normalize_quantity_evidence  # noqa: E402


@pytest.mark.parametrize(
    ("weight", "expected", "source"),
    [
        ("40,000 lbs", 40_000.0, "explicit_lbs"),
        ("20 tons", 40_000.0, "explicit_tons"),
        ("18,000 kg", 39_690.0, "explicit_kg"),
    ],
)
def test_explicit_mass_is_deterministic(weight, expected, source):
    evidence = normalize_quantity_evidence(quantity_text="", weight_per_load_text=weight, frequency_text="")

    assert evidence.load_weight_lbs == pytest.approx(expected)
    assert evidence.weight_source == source


@pytest.mark.parametrize(
    ("quantity", "expected_lbs", "source"),
    [
        ("3 loads", 126_000.0, "unit_count:load"),
        ("5 pallets", 9_000.0, "unit_count:pallet"),
        ("2 gaylords", 2_000.0, "unit_count:gaylord"),
        ("4 bales", 6_000.0, "unit_count:bale"),
    ],
)
def test_stated_unit_count_becomes_mass_and_keeps_inventory(quantity, expected_lbs, source):
    evidence = normalize_quantity_evidence(quantity_text=quantity, weight_per_load_text="", frequency_text="")

    assert evidence.load_weight_lbs == pytest.approx(expected_lbs)
    assert evidence.weight_source == source
    assert evidence.assumptions
    assert evidence.current_inventory_count_low is not None
    assert evidence.loads_per_month is None


def test_one_truckload_uses_the_unit_table():
    evidence = normalize_quantity_evidence(quantity_text="1 truckload", weight_per_load_text="", frequency_text="")

    assert evidence.load_weight_lbs == pytest.approx(42_000.0)
    assert evidence.weight_source == "unit_count:truckload"
    assert evidence.assumptions


def test_range_classifies_on_the_low_number_and_keeps_the_high_number():
    evidence = normalize_quantity_evidence(
        quantity_text="10,000 - 20,000 rough guess",
        weight_per_load_text="",
        frequency_text="",
    )

    assert evidence.load_weight_lbs == pytest.approx(10_000.0)
    assert evidence.load_weight_lbs_high == pytest.approx(20_000.0)
    assert evidence.weight_source == "range_lbs"


def test_square_feet_do_not_become_pounds():
    evidence = normalize_quantity_evidence(quantity_text="65,000 sqft", weight_per_load_text="", frequency_text="")

    assert evidence.load_weight_lbs is None
    assert evidence.weight_source == "area_not_mass"


def test_one_hundred_short_tons_are_two_hundred_thousand_pounds():
    evidence = normalize_quantity_evidence(quantity_text="", weight_per_load_text="100 ton", frequency_text="")

    assert evidence.load_weight_lbs == pytest.approx(200_000.0)
    assert evidence.weight_source == "explicit_tons"


@pytest.mark.parametrize(
    ("text", "expected_period", "expected_monthly"),
    [
        ("3 loads/week", "weekly", 13.0),
        ("2 loads per month", "monthly", 2.0),
        ("3 loads every other week", "every_other_week", 6.5),
        ("2 loads twice monthly", "twice_monthly", 4.0),
        ("6 loads quarterly", "quarterly", 2.0),
        ("12 loads annually", "annual", 1.0),
    ],
)
def test_explicit_cadence_uses_deterministic_monthly_conversion(text, expected_period, expected_monthly):
    evidence = normalize_quantity_evidence(quantity_text=text, weight_per_load_text="", frequency_text="")

    assert evidence.cadence_period == expected_period
    assert evidence.loads_per_month == pytest.approx(expected_monthly)
    assert evidence.load_weight_lbs is None


def test_ongoing_and_unknown_cadence_remain_non_numeric_when_not_explicit():
    ongoing = normalize_quantity_evidence(quantity_text="", weight_per_load_text="", frequency_text="ongoing supply")
    unknown = normalize_quantity_evidence(quantity_text="", weight_per_load_text="", frequency_text="")

    assert ongoing.supply_mode == "ongoing"
    assert ongoing.loads_per_month is None
    assert any("cadence" in request.lower() for request in ongoing.clarification_requests)
    assert unknown.supply_mode == "unclear"
    assert unknown.loads_per_month is None


class _Response:
    def __init__(self, content):
        self.choices = [types.SimpleNamespace(message=types.SimpleNamespace(content=content))]
        self.usage = types.SimpleNamespace(prompt_tokens=3, completion_tokens=5, total_tokens=8)


class _Completions:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def create(self, **_kwargs):
        self.calls += 1
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return _Response(value)


class _Client:
    def __init__(self, responses):
        self.completions = _Completions(responses)
        self.chat = types.SimpleNamespace(completions=self.completions)


def test_extract_json_supports_raw_and_fenced_json():
    assert extract_json('{"polymer": "HDPE"}') == {"polymer": "HDPE"}
    assert extract_json('```json\n{"polymer": "PP"}\n```') == {"polymer": "PP"}


def test_bounded_ai_retry_recovers_json_after_transient_failure():
    client = _Client([RuntimeError("temporary"), '```json\n{"polymer": "PP"}\n```'])
    payload, metadata = call_json_with_retry(
        client=client,
        model="test-model",
        messages=[{"role": "user", "content": "test"}],
        max_attempts=3,
    )

    assert payload == {"polymer": "PP"}
    assert metadata["attempts"] == 2
    assert metadata["total_tokens"] == 8


def test_bounded_ai_retry_fails_after_configured_attempts():
    client = _Client([ValueError("bad one"), ValueError("bad two")])

    with pytest.raises(ValueError, match="after 2 attempts"):
        call_json_with_retry(
            client=client,
            model="test-model",
            messages=[{"role": "user", "content": "test"}],
            max_attempts=2,
        )
