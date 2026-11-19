# ═══════════════════════════════════════════════════════════════════════════════
# test_triage_pipeline.py
# Tests for: triage_helpers.parse_weight_lbs, classification_engine.classify_lead,
#             ai_normalizer.validate_ai_output, image_analyzer.merge_vision_results
# ═══════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import types
from unittest.mock import MagicMock, patch

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
    parent = sys.modules.get(package_prefix)
    if parent is not None:
        setattr(parent, name, mod)
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

_ac = _load_module("ai_client")
sys.modules["plasticos_web_leads.models"].ai_client = _ac

_ip = _load_module("inference_provider")
sys.modules["plasticos_web_leads.models"].inference_provider = _ip
InferenceProvider = _ip.InferenceProvider
provider_audit_metadata = _ip.provider_audit_metadata
safe_provider_error = _ip.safe_provider_error

_qn = _load_module("quantity_normalizer")
sys.modules["plasticos_web_leads.models"].quantity_normalizer = _qn

_ai = _load_module("ai_normalizer")
validate_ai_output = _ai.validate_ai_output
normalize_with_fallback = _ai.normalize_with_fallback
build_user_prompt = _ai.build_user_prompt

_ia = _load_module("image_analyzer")
merge_vision_results = _ia.merge_vision_results

_ce = _load_module("classification_engine")
classify_lead = _ce.classify_lead
ClassificationResult = _ce.ClassificationResult

_ep = _load_module("economic_policy")
evaluate_economic_eligibility = _ep.evaluate_economic_eligibility

_ee = _load_module("economic_evaluator")
evaluate_economic_opportunity = _ee.evaluate_economic_opportunity


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

    def test_bare_large_number_stays_unknown(self):
        lbs, src = parse_weight_lbs("42000")
        assert lbs == 0.0
        assert src == "bare_number:lbs_assumed"

    def test_unitless_10000_is_not_a_load_weight(self):
        mass = _th.parse_seller_mass("10000")
        assert mass.lbs is None
        assert mass.source == "bare_number:lbs_assumed"
        replay = _th.replay_stored_mass(quantity_text="10000", estimated_lbs=10_000)
        assert replay.lbs is None
        assert replay.source == "bare_number:lbs_assumed"

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

    def test_range_uses_the_low_number(self):
        mass = _th.parse_seller_mass("10,000 - 20,000 rough guess")
        assert mass.lbs == pytest.approx(10_000.0)
        assert mass.lbs_high == pytest.approx(20_000.0)
        assert mass.source == "range_lbs"

    def test_square_feet_are_not_pounds(self):
        lbs, src = parse_weight_lbs("65,000 sqft")
        assert lbs == 0.0
        assert src == "area_not_mass"

    def test_replay_drops_stored_pounds_when_the_text_is_area(self):
        mass = _th.replay_stored_mass(quantity_text="65,000 sqft", estimated_lbs=65_000)
        assert mass.lbs is None
        assert mass.source == "area_not_mass"

    def test_replay_keeps_parsed_tons(self):
        mass = _th.replay_stored_mass(quantity_text="100 ton", estimated_lbs=0)
        assert mass.lbs == pytest.approx(200_000.0)
        assert mass.source == "explicit_tons"


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

    def test_empty_reject_list_keeps_conduit_and_mattress_film_hot(self):
        result = classify_lead(
            polymer="PVC",
            material_description="PVC electrical conduit and mattress film",
            estimated_lbs=42_000.0,
            source_type="post_industrial",
            is_plastic_hint=True,
            is_commercial_hint=True,
            weight_source="explicit_lbs",
            reject_materials=[],
        )
        assert result.decision == "hot"
        assert "reject_material" not in result.cold_gates_triggered

    def test_vision_evidence_is_copied_in_order_with_every_key(self):
        first = {
            "quantity_notes": "one gaylord in the frame",
            "containment": "gaylord",
            "observed_polymer_hint": "PP",
            "confidence": 0.91,
            "provider": {"provider": "openai", "role": "vision_analysis"},
        }
        second = {
            "commercial_color": "natural",
            "support_unit": "pallet",
            "cleanliness": "Clean",
            "material_form_observed": "Pellet",
            "call_metadata": {"id": "call-2"},
        }
        result = classify_lead(
            polymer="HDPE",
            estimated_lbs=42_000.0,
            is_commercial_hint=True,
            weight_source="explicit_lbs",
            vision_evidence=[first, second],
        )
        assert result.vision_evidence == [first, second]
        first["quantity_notes"] = "changed after the call"
        second["call_metadata"]["id"] = "changed"
        assert result.vision_evidence[0]["quantity_notes"] == "one gaylord in the frame"
        assert result.vision_evidence[1]["call_metadata"]["id"] == "call-2"

    def test_vision_error_wrapper_is_not_evidence(self):
        result = classify_lead(
            polymer="HDPE",
            estimated_lbs=42_000.0,
            is_commercial_hint=True,
            weight_source="explicit_lbs",
            vision_evidence=[
                {"error": "provider timeout", "provider": "openai"},
                {"observed_form": "Pellet", "confidence": 0.4},
            ],
        )
        assert result.vision_evidence == [{"observed_form": "Pellet", "confidence": 0.4}]

    def test_stated_tons_stay_when_the_photo_shows_one_gaylord(self):
        result = classify_lead(
            polymer="HDPE",
            estimated_lbs=200_000.0,
            weight_source="explicit_tons",
            is_commercial_hint=True,
            vision_evidence=[
                {
                    "quantity_visible": False,
                    "quantity_notes": "one gaylord in a hand",
                    "estimated_lbs": 1_000,
                    "containment": "gaylord",
                    "cleanliness": "Clean",
                }
            ],
        )
        assert result.estimated_lbs == 200_000.0
        assert result.weight_source == "explicit_tons"
        assert result.decision == "hot"
        assert result.vision_evidence[0]["quantity_visible"] is False
        assert result.vision_evidence[0]["quantity_notes"] == "one gaylord in a hand"
        assert not any("quantity" in gate or "gaylord" in gate for gate in result.cold_gates_triggered)

    def test_agreed_vision_polymer_is_used_only_when_text_polymer_is_empty(self):
        agreed = classify_lead(
            estimated_lbs=42_000.0,
            is_commercial_hint=True,
            source_type="post_industrial",
            weight_source="explicit_lbs",
            vision_evidence=[{"observed_polymer_hint": "PP", "confidence": 0.8}],
        )
        assert "polymer_confirmed:pp" in agreed.hot_qualifiers_met

        conflict = classify_lead(
            estimated_lbs=42_000.0,
            is_commercial_hint=True,
            source_type="post_industrial",
            weight_source="explicit_lbs",
            vision_evidence=[
                {"observed_polymer_hint": "PP"},
                {"observed_polymer_hint": "HDPE"},
            ],
        )
        assert not any(item.startswith("polymer_confirmed:") for item in conflict.hot_qualifiers_met)
        assert [item["observed_polymer_hint"] for item in conflict.vision_evidence] == ["PP", "HDPE"]

        text_wins = classify_lead(
            polymer="HDPE",
            estimated_lbs=42_000.0,
            is_commercial_hint=True,
            weight_source="explicit_lbs",
            vision_evidence=[{"observed_polymer_hint": "PP", "confidence": 0.99}],
        )
        assert "polymer_confirmed:hdpe" in text_wins.hot_qualifiers_met
        assert "polymer_confirmed:pp" not in text_wins.hot_qualifiers_met
        assert text_wins.vision_evidence[0]["observed_polymer_hint"] == "PP"

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

    def test_positive_pounds_with_a_missing_source_are_usable(self):
        for source in ("none", "ai_text"):
            result = classify_lead(
                polymer="PP",
                estimated_lbs=200_000.0,
                weight_source=source,
            )
            assert "weight:unknown" not in result.cold_gates_triggered
            assert result.decision == "hot"

    def test_area_source_is_not_a_pound_figure(self):
        result = classify_lead(
            polymer="PP",
            estimated_lbs=65_000.0,
            weight_source="area_not_mass",
        )
        assert result.decision == "cold"
        assert "weight:unknown" in result.cold_gates_triggered

    def test_stored_seven_thousand_two_hundred_stays_cold(self):
        result = classify_lead(
            polymer="HDPE",
            estimated_lbs=7_200.0,
            weight_source="stored_lbs",
        )
        assert result.decision == "cold"
        assert "weight:below_cold_floor" in result.cold_gates_triggered

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

    def test_unknown_commercial_never_reduces_hot_threshold(self):
        result = classify_lead(
            polymer="PP",
            estimated_lbs=8_500.0,
            is_commercial_hint=None,
            weight_source="explicit_lbs",
        )
        assert result.effective_hot_min_lbs == pytest.approx(10_000.0)
        assert result.decision == "cold"

    def test_policy_qualifier_can_support_hot_without_lowering_threshold(self):
        result = classify_lead(
            estimated_lbs=8_500.0,
            is_commercial_hint=True,
            weight_source="explicit_lbs",
            hot_min_lbs=8_000.0,
            economic_eligible=True,
            economic_policy_reasons=["policy:reusable_item"],
        )
        assert result.decision == "hot"
        assert "economic_policy:eligible" in result.hot_qualifiers_met

    def test_hot_with_unknown_commercial_evidence_requires_broker_review(self):
        result = classify_lead(
            polymer="HDPE",
            estimated_lbs=42_000.0,
            is_commercial_hint=None,
            weight_source="explicit_lbs",
        )

        assert result.decision == "hot"
        assert result.review_required is True
        assert any("Commercial source evidence is unknown" in reason for reason in result.review_reasons)

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


class TestEconomicPolicy:
    def test_ldpe_film_does_not_receive_reusable_item_threshold(self):
        result = evaluate_economic_eligibility(
            estimated_lbs=8_500.0,
            standard_hot_min_lbs=10_000.0,
            reusable_item_hot_min_lbs=8_000.0,
            polymer_code="LDPE",
            form_code="ROLLSTOCK",
            reusable_item_policy_codes=frozenset({"PLASTIC_PALLETS", "PALLETS", "TOTES", "CRATES"}),
        )

        assert result.eligible is False
        assert result.applicable_hot_min_lbs == 10_000.0
        assert "polymer_only_no_lower_threshold" in result.reasons

    @pytest.mark.parametrize("form_code", ["PALLETS", "TOTES", "CRATES"])
    def test_only_approved_reusable_item_forms_receive_lower_threshold(self, form_code):
        result = evaluate_economic_eligibility(
            estimated_lbs=8_500.0,
            standard_hot_min_lbs=10_000.0,
            reusable_item_hot_min_lbs=8_000.0,
            polymer_code=None,
            form_code=form_code,
            reusable_item_policy_codes=frozenset({"PLASTIC_PALLETS", "PALLETS", "TOTES", "CRATES"}),
        )

        assert result.eligible is True
        assert result.policy_applied == "reusable_item"
        assert result.applicable_hot_min_lbs == 8_000.0


class TestEconomicEvaluator:
    def test_missing_provider_requires_broker_review_instead_of_silent_decision(self):
        assessment = evaluate_economic_opportunity(
            provider=None,
            canonical_payload={"material_description": "HDPE regrind", "contact_email": "private@example.test"},
            evidence_bundle={"quantity": {"load_weight_lbs": 42_000.0}},
            classification={"decision": "hot"},
            eligibility={"eligible": True},
        )

        assert assessment["status"] == "unavailable"
        assert assessment["reason"] == "no_economic_provider_configured"
        assert "contact_email" not in assessment["context"]["seller_material_and_supply"]


class TestInferenceProviderAudit:
    def test_provider_audit_never_includes_credentials_or_base_url(self):
        provider = InferenceProvider(
            provider="anthropic",
            transport="anthropic_messages",
            api_key="secret-value",
            model="claude-haiku-test",
            base_url="https://private.gateway.test",
            workspace_id="private-workspace",
        )

        metadata = provider_audit_metadata(provider, role="economic_evaluation")
        error = safe_provider_error(RuntimeError("provider unavailable"), provider, role="economic_evaluation")

        assert metadata == {
            "role": "economic_evaluation",
            "provider": "anthropic",
            "transport": "anthropic_messages",
            "model": "claude-haiku-test",
        }
        assert "secret-value" not in str(error)
        assert "private.gateway.test" not in str(error)
        assert "private-workspace" not in str(error)


# ═══════════════════════════════════════════════════════════════════════════════
# validate_ai_output
# ═══════════════════════════════════════════════════════════════════════════════
_SIGNED_URL = "https://files.cognitoforms.com/material.jpg?sig=SECRET-TOKEN"


class TestPromptDataMinimization:
    """F187-03: signed acquisition URLs never reach an external provider."""

    def _canonical(self):
        return {
            "schema_version": "web-lead-packet/v1",
            "provider": "cognito",
            "provider_external_id": "12345",
            "idempotency_key": "CG-12345",
            "company_name": "Acme Plastics",
            "material_description": "HDPE regrind",
            "quantity_text": "3 loads",
            "attachments": [
                {
                    "source_id": "file-1",
                    "attachment_index": 0,
                    "filename": "material.jpg",
                    "content_type": "image/jpeg",
                    "size_bytes": 4,
                    # Leads admitted before the scrub can still carry this durably.
                    "source_url": _SIGNED_URL,
                }
            ],
            "raw_payload": {"UploadPhotos": [{"File": _SIGNED_URL}]},
        }

    def test_prompt_contains_no_attachment_source_url(self):
        prompt = build_user_prompt(self._canonical())
        assert "SECRET-TOKEN" not in prompt
        assert "cognitoforms.com" not in prompt
        assert "Company: Acme Plastics" in prompt
        assert "Attachments: 1 file(s): material.jpg (image/jpeg, 4 bytes)" in prompt
        assert "idempotency_key" not in prompt

    def test_legacy_raw_payload_upload_lists_are_not_serialized(self):
        prompt = build_user_prompt(
            {"DescribeYourMaterial": "PP purge", "UploadPhotos": [{"File": _SIGNED_URL}], "Name": {"First": "A"}}
        )
        assert "SECRET-TOKEN" not in prompt
        assert "Material description: PP purge" in prompt

    def test_economic_assessment_context_contains_no_attachment_source_url(self):
        result = evaluate_economic_opportunity(
            provider=None,
            canonical_payload=self._canonical(),
            evidence_bundle={"quantity": {}, "conflicts": [], "clarification_requests": [], "vision": []},
            classification={"decision": "hot"},
            eligibility={"eligible": True},
        )
        context = result["context"]
        assert "SECRET-TOKEN" not in json.dumps(context)
        assert context["seller_material_and_supply"]["attachments"][0]["filename"] == "material.jpg"
        assert "raw_payload" not in context["seller_material_and_supply"]


class TestValidateAiOutput:
    def test_weight_above_review_cap_is_kept(self):
        result = validate_ai_output({"estimated_lbs_per_load": 220_462})
        assert result["estimated_lbs_per_load"] == 220_462
        assert result["weight_above_review_cap"] is True

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
# normalize_with_fallback
# ═══════════════════════════════════════════════════════════════════════════════
class TestNormalizeWithFallback:
    def test_empty_providers_returns_configured_error(self):
        result = normalize_with_fallback(
            {"WhatIsTheQuantity": "30 pallets"},
            [],
        )
        assert result["_provider_used"] == "none"
        assert result["error"] == "no_llm_provider_configured"
        assert result["estimated_lbs_per_load"] == 30 * 1800

    @patch.object(_ai, "normalize_lead")
    @patch.object(_ai, "_build_openai_client")
    def test_first_provider_success(self, mock_build, mock_normalize):
        mock_client = MagicMock()
        mock_build.return_value = mock_client
        mock_normalize.return_value = {
            "polymer": "HDPE",
            "estimated_lbs_per_load": 42_000,
            "_inferred_fields": ["polymer"],
        }
        providers = [
            {
                "provider": "openai",
                "api_key": "sk-test",
                "model": "gpt-4o",
                "base_url": None,
            }
        ]
        payload = {"DescribeYourMaterial": "HDPE regrind"}

        result = normalize_with_fallback(payload, providers)

        assert result["_provider_used"] == "openai"
        assert result["polymer"] == "HDPE"
        assert "error" not in result
        mock_build.assert_called_once_with("sk-test", None)
        mock_normalize.assert_called_once_with(
            payload,
            mock_client,
            model="gpt-4o",
            temperature=0.0,
        )

    @patch.object(_ai, "normalize_lead")
    @patch.object(_ai, "_build_openai_client")
    def test_fallback_to_second_provider(self, mock_build, mock_normalize):
        mock_build.return_value = MagicMock()
        mock_normalize.side_effect = [
            {"_ai_error": "rate limit", "estimated_lbs_per_load": None},
            {"polymer": "PP", "_inferred_fields": []},
        ]
        providers = [
            {"provider": "openai", "api_key": "sk-1", "model": "gpt-4o", "base_url": None},
            {
                "provider": "anthropic",
                "api_key": "sk-ant-1",
                "model": "claude-sonnet-4-20250514",
                "base_url": "https://api.anthropic.com/v1/",
            },
        ]

        result = normalize_with_fallback({}, providers)

        assert result["_provider_used"] == "anthropic"
        assert result["polymer"] == "PP"
        assert mock_normalize.call_count == 2

    @patch.object(_ai, "normalize_lead")
    @patch.object(_ai, "_build_openai_client")
    def test_all_providers_fail_returns_last_error(self, mock_build, mock_normalize):
        mock_build.return_value = MagicMock()
        mock_normalize.return_value = {"_ai_error": "timeout"}
        providers = [{"provider": "openai", "api_key": "sk-1", "model": "gpt-4o", "base_url": None}]

        result = normalize_with_fallback({}, providers)

        assert result["_provider_used"] == "none"
        assert result["error"] == "provider_inference_failed"

    @patch.object(_ai, "normalize_lead")
    @patch.object(_ai, "_build_openai_client")
    def test_client_unavailable_stops_early(self, mock_build, mock_normalize):
        mock_build.return_value = None
        mock_normalize.return_value = {"estimated_lbs_per_load": None, "_inferred_fields": []}
        providers = [{"provider": "openai", "api_key": "", "model": "gpt-4o", "base_url": None}]

        result = normalize_with_fallback({}, providers)

        assert result["_provider_used"] == "none"
        assert result["error"] == "openai_client_unavailable"
        mock_normalize.assert_called_once()


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


class TestVisionBytePath:
    def test_byte_path_preserves_distinct_visual_evidence(self):
        response = types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(
                        content=(
                            '{"observed_form":"Film Rolls","commercial_color":"Mixed",'
                            '"containment":"Gaylords","support_unit":"Pallets",'
                            '"observed_polymer_hint":null,"confidence":0.9}'
                        )
                    )
                )
            ]
        )
        client = MagicMock()
        client.chat.completions.create.return_value = response

        result = _ia.analyze_image_bytes(
            b"image-bytes",
            content_type="image/jpeg",
            client=client,
            model="vision-test",
        )

        assert result["observed_form"] == "Film Rolls"
        assert result["containment"] == "Gaylords"
        assert result["support_unit"] == "Pallets"
        assert result["commercial_color"] == "Mixed"
        assert result["observed_polymer_hint"] is None


def test_joint_prompt_carries_photo_codes_and_rejects_an_invented_code():
    prompt = build_user_prompt(
        {"WhatMaterialDoYouHave": "Polycarbonate plastic"},
        [
            {
                "observed_form": "SHEET",
                "observed_packaging": "palletized",
                "observed_attributes": ["printed"],
                "source_url": "https://files.example/photo?token=SECRET-TOKEN",
            }
        ],
    )
    assert "observed_form=SHEET" in prompt
    assert "observed_packaging=palletized" in prompt
    assert "observed_attributes=printed" in prompt
    assert "SECRET-TOKEN" not in prompt

    polymer = _ai.CatalogEntry("LDPE", "LDPE", "", "Low-Density Polyethylene")
    system = _ai.system_prompt({"polymer": (polymer,)})
    assert "Low-Density Polyethylene" in system
    catalog_module = sys.modules["plasticos_web_leads.models.material_catalog"]
    assert catalog_module.match_one("Low-Density Polyethylene", (polymer,)) is None

    kept = _ai.restrict_to_catalog(
        {"form": "SHEET", "packaging_type": "invented_wrap"},
        {
            "form": (_ai.CatalogEntry("SHEET", "Sheet"),),
            "packaging": (_ai.CatalogEntry("palletized", "Palletized"),),
        },
    )
    assert kept["form"] == "SHEET"
    assert kept["packaging_type"] is None


def test_prompt_rules_name_quality_tier_and_printed_film():
    prompt = _ai.system_prompt(
        {
            "polymer": (_ai.CatalogEntry("BOPP", "BOPP", ""),),
            "form": (_ai.CatalogEntry("FILM", "Film", ""),),
            "color": (_ai.CatalogEntry("WHITE", "White", ""),),
            "attribute": (_ai.CatalogEntry("printed", "Printed", ""),),
            "quality_tier": (_ai.CatalogEntry("GRADE_A", "Grade A", ""),),
            "process": (_ai.CatalogEntry("compression_mold", "Compression Mold", ""),),
        }
    )
    assert "BOPP" in prompt
    assert "FILM" in prompt
    assert "WHITE" in prompt
    assert "printed" in prompt
    assert "w/ print" in prompt
    assert "GRADE_A" in prompt
    assert "reuseable" in prompt
    assert "Bare Mixed or mixed after a material or grade word is attribute mixed" in prompt
    assert "Only Mixed Color or mixed color is color MIXED" in prompt
    assert "Never leave quality_tier null when" in prompt
    assert "gaylord boxes as the product" in prompt
    assert "quality_tier to REUSABLE" in prompt
    assert "Do not set is_plastic=true from that phrase alone" in prompt
    assert "compression molded or compression mold maps to process_type compression_mold" in prompt
    assert "injection or injection molded maps to process_type injection" in prompt
    assert "blow molded or blow mold maps to process_type blow_mold" in prompt
    assert "Color Mixed Color is the color, not attribute mixed" not in prompt


def test_text_normalization_is_locked_to_deepseek_flash():
    config_path = os.path.join(_models_dir, "web_lead_config.py")
    xml_path = os.path.join(os.path.dirname(_models_dir), "data", "web_lead_config_data.xml")
    with open(config_path, encoding="utf-8") as handle:
        config = handle.read()
    with open(xml_path, encoding="utf-8") as handle:
        seed = handle.read()
    assert 'string="Text Inference Provider"' in config
    text_field = config.split('string="Text Inference Provider"', 1)[1].split("vision_inference_provider", 1)[0]
    assert 'default="deepseek"' in text_field
    assert 'DEEPSEEK_TEXT_MODEL = "deepseek-flash"' in config
    assert 'DEEPSEEK_BASE_URL = "https://api.deepseek.com"' in config
    assert '<field name="text_inference_provider">deepseek</field>' in seed
    assert '<field name="deepseek_model">deepseek-flash</field>' in seed
    assert (
        'default="openai"' in config.split("vision_inference_provider", 1)[1].split("economic_inference_provider", 1)[0]
    )


def _method_body(source, name):
    return source.split(f"def {name}", 1)[1].split("\n    def ", 1)[0]


def _one_pass_orchestration_enabled(source):
    return re.search(r"^ONE_PASS_ORCHESTRATION\s*(?::[^\n=]+)?=\s*True\b", source, re.MULTILINE) is not None


def _assert_one_provider_request(body):
    assert body.count("run_broker_inference(") == 1
    assert "normalize_with_provider(" not in body
    assert "analyze_image_with_provider(" not in body
    assert "evaluate_economic_opportunity(" not in body
    assert "seller=" in body
    assert "quantity_evidence=" in body
    for removed in ("case_id=", "seller_claims=", "documents=", "media_omissions=", "_catalog_for_broker("):
        assert removed not in body


def test_vision_still_reaches_the_classifier_after_it_feeds_the_normalizer():
    with open(os.path.join(_models_dir, "web_lead.py"), encoding="utf-8") as handle:
        source = handle.read()
    pipeline = _method_body(source, "_run_triage_pipeline")
    if _one_pass_orchestration_enabled(source):
        _assert_one_provider_request(pipeline)
        _assert_one_provider_request(_method_body(source, "action_retry_economic_assessment"))
        return
    assert pipeline.index("analyze_image_with_provider") < pipeline.index("normalize_with_provider")
    assert "vision_results=vision_results" in pipeline
    assert "vision_evidence=vision_results" in pipeline


def test_planning_defaults_serialize_with_units():
    basis = json.loads(json.dumps(_ep.PLANNING_DEFAULTS_V1.as_evidence()))
    assert basis["policy_ref"] == "web-lead-planning-defaults/v1"
    pallets = basis["weights"]["mixed_plastic_pallets"]
    assert pallets["low_lb"] == 10000
    assert pallets["high_lb"] == 12000
    assert pallets["unit"] == "lb"
    assert basis["weights"]["baled_film"]["lb"] == 36000
    assert basis["weights"]["pellets"] == {"lb": 40000, "unit": "lb"}
    assert "full domestic 53-foot trailer" in basis["trailers"]
