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


@pytest.mark.parametrize("quantity", ["3 loads", "5 pallets", "2 gaylords", "4 bales"])
def test_inventory_units_never_become_assumed_weight(quantity):
    evidence = normalize_quantity_evidence(quantity_text=quantity, weight_per_load_text="", frequency_text="")

    assert evidence.load_weight_lbs is None
    assert evidence.weight_source == "none"
    assert evidence.current_inventory_count_low is not None
    assert evidence.loads_per_month is None


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
