# ═══════════════════════════════════════════════════════════════════════════════
# test_triage_pipeline.py
# Tests for: triage_helpers.parse_weight_lbs, classification_engine.classify_lead,
#             ai_normalizer.validate_ai_output, image_analyzer.merge_vision_results
# ═══════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import importlib.util
import json
import os
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
