# ═══════════════════════════════════════════════════════════════════════════════
# test_triage_pipeline.py
# Tests for: triage_helpers.parse_weight_lbs, classification_engine.classify_lead,
#             ai_normalizer.validate_ai_output, image_analyzer.merge_vision_results
# ═══════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import importlib.util
import os
import sys
import types

import pytest

_models_dir = os.path.join(os.path.dirname(__file__), "..", "plasticos_web_leads", "models")


def _load_module(name: str, package_prefix: str = "plasticos_web_leads.models"):
    """Load a single module file, registering under its full dotted name."""
    fqn = f"{package_prefix}.{name}"
    filepath = os.path.join(_models_dir, f"{name}.py")
    spec = importlib.util.spec_from_file_location(fqn, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[fqn] = mod
    sys.modules[name] = mod  # also as short name
    spec.loader.exec_module(mod)
    return mod


# Create stub parent packages so relative imports resolve
for pkg in ("plasticos_web_leads", "plasticos_web_leads.models"):
    if pkg not in sys.modules:
        sys.modules[pkg] = types.ModuleType(pkg)

# triage_helpers first (no deps)
_th = _load_module("triage_helpers")
# patch onto the fake package so `from .triage_helpers import ...` works
sys.modules["plasticos_web_leads.models"].triage_helpers = _th

parse_weight_lbs = _th.parse_weight_lbs
safe_int = _th.safe_int
safe_float = _th.safe_float
coerce_bool = _th.coerce_bool

_ai = _load_module("ai_normalizer")
validate_ai_output = _ai.validate_ai_output

_ia = _load_module("image_analyzer")
merge_vision_results = _ia.merge_vision_results

_ce = _load_module("classification_engine")
classify_lead = _ce.classify_lead
ClassificationResult = _ce.ClassificationResult


# ═══════════════════════════════════════════════════════════════════════════════
# parse_weight_lbs
# ═══════════════════════════════════════════════════════════════════════════════
class TestParseWeightLbs:
    def test_none_returns_zero(self):
        lbs, src = parse_weight_lbs(None)
        assert lbs == 0.0
        assert src == "none"

    def test_empty_string_returns_zero(self):
        lbs, src = parse_weight_lbs("")
        assert lbs == 0.0
        assert src == "none"

    def test_explicit_lbs(self):
        lbs, src = parse_weight_lbs("40000 lbs")
        assert lbs == 40_000.0
        assert src == "explicit_lbs"

    def test_explicit_pounds(self):
        lbs, src = parse_weight_lbs("5000 pounds")
        assert lbs == 5_000.0
        assert src == "explicit_lbs"

    def test_explicit_tons(self):
        lbs, src = parse_weight_lbs("20 tons")
        assert lbs == 40_000.0
        assert src == "explicit_tons"

    def test_explicit_metric_tons(self):
        lbs, src = parse_weight_lbs("10 tonnes")
        assert lbs == pytest.approx(22046.23, rel=1e-2)
        assert src == "explicit_metric_tons"

    def test_explicit_kg(self):
        lbs, src = parse_weight_lbs("1000 kg")
        assert lbs == pytest.approx(2205.0, rel=1e-2)
        assert src == "explicit_kg"

    def test_unit_count_pallets(self):
        lbs, src = parse_weight_lbs("30 pallets")
        assert lbs == 30 * 1800.0
        assert src == "unit_count:pallet"

    def test_unit_count_single_pallet(self):
        lbs, src = parse_weight_lbs("1 pallet")
        assert lbs == 1800.0
        assert src == "unit_count:pallet"

    def test_unit_count_gaylords(self):
        lbs, src = parse_weight_lbs("5 gaylords")
        assert lbs == 5 * 1000.0
        assert src == "unit_count:gaylord"

    def test_unit_count_truckload(self):
        lbs, src = parse_weight_lbs("1 truckload")
        assert lbs == 42_000.0
        assert src == "unit_count:truckload"

    def test_unit_count_bales(self):
        lbs, src = parse_weight_lbs("10 bales")
        assert lbs == 10 * 1500.0
        assert src == "unit_count:bale"

    def test_word_number_one_truckload(self):
        lbs, src = parse_weight_lbs("one truckload")
        assert lbs == 42_000.0
        assert src == "unit_count:truckload"

    def test_word_number_two_pallets(self):
        lbs, src = parse_weight_lbs("two pallets")
        assert lbs == 2 * 1800.0
        assert src == "unit_count:pallet"

    def test_bare_large_number_assumed_lbs(self):
        lbs, src = parse_weight_lbs("42000")
        assert lbs == 42_000.0
        assert src == "bare_number:lbs_assumed"

    def test_bare_small_number_below_threshold(self):
        lbs, src = parse_weight_lbs("30")
        assert lbs == 0.0
        assert src == "none"

    def test_commas_in_number(self):
        lbs, src = parse_weight_lbs("40,000 lbs")
        assert lbs == 40_000.0
        assert src == "explicit_lbs"

    def test_unknown_text_returns_zero(self):
        lbs, src = parse_weight_lbs("unknown")
        assert lbs == 0.0
        assert src == "none"

    def test_vague_text_returns_zero(self):
        lbs, src = parse_weight_lbs("a lot")
        assert lbs == 0.0
        assert src == "none"


# ═══════════════════════════════════════════════════════════════════════════════
# safe_int / safe_float / coerce_bool
# ═══════════════════════════════════════════════════════════════════════════════
class TestHelpers:
    def test_safe_int_none(self):
        assert safe_int(None) == 0

    def test_safe_int_string(self):
        assert safe_int("42") == 42

    def test_safe_int_comma_number(self):
        assert safe_int("1,500") == 1500

    def test_safe_int_invalid(self):
        assert safe_int("abc") == 0

    def test_safe_float_none(self):
        assert safe_float(None) == 0.0

    def test_safe_float_string(self):
        assert safe_float("3.14") == pytest.approx(3.14)

    def test_coerce_bool_true(self):
        assert coerce_bool(True) is True
        assert coerce_bool("yes") is True
        assert coerce_bool("1") is True

    def test_coerce_bool_false(self):
        assert coerce_bool(False) is False
        assert coerce_bool("no") is False
        assert coerce_bool("0") is False

    def test_coerce_bool_none(self):
        assert coerce_bool(None) is None
        assert coerce_bool("maybe") is None
        assert coerce_bool("unknown") is None


# ═══════════════════════════════════════════════════════════════════════════════
# classify_lead
# ═══════════════════════════════════════════════════════════════════════════════
class TestClassifyLead:
    def test_hot_with_weight_and_polymer(self):
        result = classify_lead(
            polymer="HDPE",
            material_description="HDPE regrind from manufacturing",
            estimated_lbs=42_000.0,
            source_type="post_industrial",
            is_plastic_hint=True,
            is_commercial_hint=True,
            weight_source="explicit_lbs",
        )
        assert result.decision == "hot"
        assert not result.cold_gates_triggered
        assert len(result.hot_qualifiers_met) >= 2

    def test_cold_not_plastic(self):
        result = classify_lead(
            material_description="steel scrap",
            estimated_lbs=50_000.0,
            is_plastic_hint=False,
            weight_source="explicit_lbs",
        )
        assert result.decision == "cold"
        assert "is_plastic:false" in result.cold_gates_triggered

    def test_cold_not_commercial(self):
        result = classify_lead(
            polymer="HDPE",
            estimated_lbs=50_000.0,
            is_plastic_hint=True,
            is_commercial_hint=False,
            weight_source="explicit_lbs",
        )
        assert result.decision == "cold"
        assert "is_commercial_source:false" in result.cold_gates_triggered

    def test_cold_rejected_material(self):
        result = classify_lead(
            material_description="aluminum cans",
            estimated_lbs=40_000.0,
            is_plastic_hint=None,
            weight_source="explicit_lbs",
        )
        assert result.decision == "cold"
        assert "reject_material" in result.cold_gates_triggered

    def test_cold_rejected_source(self):
        result = classify_lead(
            polymer="HDPE",
            source_description="household cleanup",
            estimated_lbs=40_000.0,
            is_plastic_hint=True,
            weight_source="explicit_lbs",
        )
        assert result.decision == "cold"
        assert "reject_source" in result.cold_gates_triggered

    def test_cold_weight_unknown(self):
        result = classify_lead(
            polymer="HDPE",
            estimated_lbs=0.0,
            weight_source="none",
        )
        assert result.decision == "cold"
        assert "weight:unknown" in result.cold_gates_triggered

    def test_cold_weight_below_floor(self):
        result = classify_lead(
            polymer="HDPE",
            estimated_lbs=5_000.0,
            is_plastic_hint=True,
            weight_source="explicit_lbs",
        )
        assert result.decision == "cold"
        assert "weight:below_cold_floor" in result.cold_gates_triggered

    def test_cold_insufficient_qualifiers(self):
        result = classify_lead(
            estimated_lbs=42_000.0,
            is_plastic_hint=True,
            weight_source="explicit_lbs",
        )
        assert result.decision == "cold"
        assert "insufficient_qualifiers" in result.cold_gates_triggered

    def test_hot_threshold_reduced_unknown_commercial(self):
        result = classify_lead(
            polymer="PP",
            estimated_lbs=8_500.0,
            is_commercial_hint=None,
            weight_source="explicit_lbs",
        )
        assert result.effective_hot_min_lbs == pytest.approx(8_000.0)

    def test_word_boundary_reject_material_no_false_positive(self):
        """'fiberglass' should NOT trigger 'glass' reject gate."""
        result = classify_lead(
            polymer="HDPE",
            material_description="fiberglass reinforced HDPE",
            estimated_lbs=42_000.0,
            is_plastic_hint=True,
            is_commercial_hint=True,
            weight_source="explicit_lbs",
        )
        assert "reject_material" not in result.cold_gates_triggered

    def test_drop_off_source_triggers_cold(self):
        result = classify_lead(
            polymer="HDPE",
            source_description="drop off at our facility",
            estimated_lbs=42_000.0,
            is_plastic_hint=True,
            weight_source="explicit_lbs",
        )
        assert result.decision == "cold"
        assert "reject_source" in result.cold_gates_triggered


# ═══════════════════════════════════════════════════════════════════════════════
# validate_ai_output
# ═══════════════════════════════════════════════════════════════════════════════
class TestValidateAiOutput:
    def test_clamps_lbs_above_max(self):
        result = validate_ai_output({"estimated_lbs_per_load": 999_999})
        assert result["estimated_lbs_per_load"] is None

    def test_clamps_lbs_below_min(self):
        result = validate_ai_output({"estimated_lbs_per_load": 0.5})
        assert result["estimated_lbs_per_load"] is None

    def test_valid_lbs_passes(self):
        result = validate_ai_output({"estimated_lbs_per_load": 42_000})
        assert result["estimated_lbs_per_load"] == 42_000

    def test_negative_loads_nulled(self):
        result = validate_ai_output({"loads_per_month": -5})
        assert result["loads_per_month"] is None

    def test_confidence_clamped(self):
        result = validate_ai_output({"confidence": 1.5})
        assert result["confidence"] == 1.0

    def test_empty_string_fields_nulled(self):
        result = validate_ai_output({"polymer": "  ", "notes": ""})
        assert result["polymer"] is None
        assert result["notes"] is None

    def test_boolean_fields_coerced(self):
        result = validate_ai_output({"is_plastic": "yes", "is_commercial_source": "no"})
        assert result["is_plastic"] is True
        assert result["is_commercial_source"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# merge_vision_results
# ═══════════════════════════════════════════════════════════════════════════════
class TestMergeVisionResults:
    def test_empty_list_returns_none(self):
        assert merge_vision_results([]) is None

    def test_all_errors_returns_none(self):
        assert merge_vision_results([{"error": "fail"}]) is None

    def test_highest_confidence_wins(self):
        results = [
            {"observed_form": "Bale", "confidence": 0.5},
            {"observed_form": "Pellet", "confidence": 0.9},
        ]
        merged = merge_vision_results(results)
        assert merged["observed_form"] == "Pellet"

    def test_contamination_any_positive_wins(self):
        results = [
            {"contamination_visible": False, "confidence": 0.9},
            {"contamination_visible": True, "confidence": 0.5},
        ]
        merged = merge_vision_results(results)
        assert merged["contamination_visible"] is True

    def test_contamination_notes_aggregated(self):
        results = [
            {"contamination_notes": "dirt", "confidence": 0.9},
            {"contamination_notes": "labels", "confidence": 0.5},
        ]
        merged = merge_vision_results(results)
        assert "dirt" in merged["contamination_notes"]
        assert "labels" in merged["contamination_notes"]

    def test_low_confidence_nulls_polymer_hint(self):
        results = [{"observed_polymer_hint": "HDPE", "confidence": 0.1}]
        merged = merge_vision_results(results, min_confidence=0.3)
        assert merged["observed_polymer_hint"] is None

    def test_error_results_filtered(self):
        results = [
            {"error": "timeout"},
            {"observed_form": "Bale", "confidence": 0.8},
        ]
        merged = merge_vision_results(results)
        assert merged["observed_form"] == "Bale"
        assert "error" not in merged
