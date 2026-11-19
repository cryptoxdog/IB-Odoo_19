"""Parser contract for the one multimodal broker reading.

The transport is mocked. ``run_broker_inference`` itself is the function under test.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import types
from unittest.mock import patch

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_MODELS = os.path.join(_ROOT, "plasticos_web_leads", "models")
_PACKAGE = "plasticos_web_leads.models"


def _install_packages() -> None:
    parents = (
        ("plasticos_web_leads", os.path.join(_ROOT, "plasticos_web_leads")),
        (_PACKAGE, _MODELS),
    )
    for name, path in parents:
        module = sys.modules.get(name)
        if module is None:
            module = types.ModuleType(name)
            sys.modules[name] = module
        module.__path__ = [path]
        module.__package__ = name


def _load(name: str):
    fqn = f"{_PACKAGE}.{name}"
    existing = sys.modules.get(fqn)
    if existing is not None and getattr(existing, "__file__", "").endswith(f"{name}.py"):
        return existing
    spec = importlib.util.spec_from_file_location(fqn, os.path.join(_MODELS, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[fqn] = module
    spec.loader.exec_module(module)
    setattr(sys.modules[_PACKAGE], name, module)
    return module


_install_packages()
for _name in (
    "triage_helpers",
    "evidence_keys",
    "material_catalog",
    "ai_client",
    "quantity_normalizer",
    "inference_provider",
    "ai_normalizer",
    "image_analyzer",
    "economic_evaluator",
):
    _load(_name)

_ip = sys.modules[f"{_PACKAGE}.inference_provider"]
_catalog_module = sys.modules[f"{_PACKAGE}.material_catalog"]
CatalogEntry = _catalog_module.CatalogEntry
run_broker_inference = _ip.run_broker_inference
InferenceProvider = _ip.InferenceProvider

_PLANNING_TOKENS = ("10000", "12000", "36000", "40000", "10,000", "12,000", "36,000", "40,000")
_CATALOG = {
    "polymer": (CatalogEntry("HDPE", "HDPE"),),
    "form": (CatalogEntry("REGRIND", "Regrind"),),
}


def _provider() -> InferenceProvider:
    return InferenceProvider(
        provider="openai",
        transport="openai_compatible",
        api_key="test-key-not-used",
        model="test-model",
    )


def _reply() -> dict:
    return {
        "normalization": {
            "polymer": "HDPE",
            "form": "REGRIND",
            "confidence": 0.9,
            "estimated_lbs_per_load": 10000,
        },
        "vision": [{"observed_form": "regrind", "confidence": 0.8, "contamination_visible": False}],
        "economic": {
            "recommended_disposition": "review",
            "opportunity_signal": "review",
            "confidence": 0.7,
            "material_suitability": "supported",
            "commercial_rationale": "Seller named HDPE regrind.",
            "supporting_evidence_refs": ["seller.material_description"],
        },
        "alignment": {
            "status": "unknown",
            "representativeness": "unknown",
            "score": 20,
            "seller_confirmation_ref": None,
            "covers_photo": False,
            "covers_specs": False,
            "covers_whole_offered_lot": False,
        },
        "quality_availability_question": None,
        "document_specifications": [
            {
                "property": "MFI",
                "value": 8.5,
                "unit": "g/10min",
                "test_conditions": "190C/2.16kg",
                "source_refs": ["seller.material_description"],
                "conflicts": [],
            },
            {
                "property": "density",
                "value": 0.95,
                "unit": "g/cm3",
                "test_conditions": None,
                "source_refs": ["model.guess"],
                "conflicts": [],
            },
        ],
    }


def test_one_request_admits_bytes_catalog_and_cited_spec():
    calls = []

    def transport(provider, *, system_prompt, text_parts, images, max_tokens=4096):
        calls.append({"system_prompt": system_prompt, "text_parts": list(text_parts), "images": list(images)})
        return _reply(), {"attempts": 1}

    image = {"content": b"\xff\xd8\xff-jpeg", "content_type": "image/jpeg", "source_id": "photo-1"}
    with patch.object(_ip, "call_structured_multimodal", side_effect=transport):
        result = run_broker_inference(
            _provider(),
            seller={"material_description": "HDPE regrind, MFI 8.5 g/10min"},
            images=[
                image,
                {"content_base64": "abcd", "content_type": "image/jpeg", "source_id": "photo-b64"},
                {"content": "abcd", "content_type": "image/jpeg", "source_id": "photo-flat"},
                "not-a-record",
            ],
            pdf_page_text=["Page one already extracted.", b"%PDF-1.4"],
            planning_defaults={
                "policy_ref": "web-lead-planning-defaults/v1",
                "mixed_plastic_pallets_lbs": [10000, 12000],
                "baled_film_lbs": 36000,
                "pellets_lbs": 40000,
            },
            catalog=_CATALOG,
            quantity_evidence={"load_weight_lbs": 10000, "weight_source": "bare_number:lbs_assumed"},
        )

    assert len(calls) == 1
    assert calls[0]["images"] == [(image["content"], "image/jpeg")]
    system_prompt = calls[0]["system_prompt"]
    polymer_slot = system_prompt.split("Polymer codes:", 1)[1].split("Form codes:", 1)[0]
    form_slot = system_prompt.split("Form codes:", 1)[1].split("Material grade codes:", 1)[0]
    assert "HDPE — HDPE" in polymer_slot
    assert "REGRIND — Regrind" in form_slot
    assert "HDPE — HDPE" not in form_slot
    prompt = system_prompt + "\n" + "\n".join(calls[0]["text_parts"])
    assert "Page one already extracted." in prompt
    for token in _PLANNING_TOKENS:
        assert token not in prompt
    assert result["request_count"] == 1
    assert result["status"] == "assessed"
    issues = result["validation_issues"]
    assert "image_bytes_missing" in issues
    assert "image_not_a_record" in issues
    assert "pdf_bytes_not_parsed" in issues
    assert "specification_uncited" in issues
    specs = result["evidence_bundle"]["document_specifications"]
    assert specs == [
        {
            "property": "MFI",
            "value": 8.5,
            "unit": "g/10min",
            "test_conditions": "190C/2.16kg",
            "source_refs": ["seller.material_description"],
            "conflicts": [],
        }
    ]
    assert result["decision_inputs"]["estimated_lbs_per_load"] is None
    assert result["decision_inputs"]["quantity_per_load_lbs"] is None
    assert result["evidence_bundle"]["quantity_weight"]["estimated_lbs_per_load"] is None
    assert result["evidence_bundle"]["quantity_weight"]["weight_written_from_planning_default"] is False
    assert result["evidence_bundle"]["photo_findings"][0]["source_id"] == "photo-1"
    assert result["evidence_bundle"]["vision"][0]["source_id"] == "photo-1"


def test_missing_provider_does_not_raise():
    result = run_broker_inference(None, seller={"material_description": "HDPE regrind"})
    assert result["status"] == "unavailable"
    assert result["request_count"] == 0
    assert result["evidence_bundle"]["document_specifications"] == []
    assert result["decision_inputs"]["estimated_lbs_per_load"] is None


def test_provider_exception_does_not_raise():
    def transport(*_args, **_kwargs):
        raise RuntimeError("provider down")

    with patch.object(_ip, "call_structured_multimodal", side_effect=transport):
        result = run_broker_inference(
            _provider(),
            seller={"material_description": "HDPE regrind"},
            catalog=_CATALOG,
        )
    assert result["status"] == "unavailable"
    assert result["request_count"] == 1
    assert result["evidence_bundle"]["document_specifications"] == []


def test_run_broker_inference_rejects_removed_keywords():
    with pytest.raises(TypeError):
        run_broker_inference(_provider(), case_id="WL-1", seller_claims={}, documents=[])


def _pdf_spec_row(value, unit, refs):
    return {
        "property": "MFI",
        "value": value,
        "unit": unit,
        "test_conditions": "190C/2.16kg",
        "source_refs": refs,
        "conflicts": [],
    }


def _reply_with_specs(specs):
    reply = _reply()
    reply["document_specifications"] = specs
    return reply


def test_pdf_sources_mint_doc_scoped_keys_and_labels():
    calls = []

    def transport(provider, *, system_prompt, text_parts, images, max_tokens=4096):
        calls.append({"system_prompt": system_prompt, "text_parts": list(text_parts), "images": list(images)})
        return _reply_with_specs([_pdf_spec_row(7.5, "g/10min", ["pdf.0.page.2"])]), {"attempts": 1}

    sources = [
        {"source_ref": "pdf.0", "source_id": "src-a", "page_number": 1, "attachment_id": 11, "content_sha256": "a"},
        {"source_ref": "pdf.0", "source_id": "src-a", "page_number": 2, "attachment_id": 11, "content_sha256": "a"},
        {"source_ref": "pdf.1", "source_id": "src-b", "page_number": 1, "attachment_id": 12, "content_sha256": "b"},
    ]
    with patch.object(_ip, "call_structured_multimodal", side_effect=transport):
        result = run_broker_inference(
            _provider(),
            seller={"material_description": "HDPE regrind"},
            pdf_page_text=["Cover page text.", "MFI 7.5 g/10min.", "Density 0.941 g/cm3."],
            pdf_page_sources=sources,
            catalog=_CATALOG,
        )

    assert len(calls) == 1
    prompt = calls[0]["system_prompt"] + "\n" + "\n".join(calls[0]["text_parts"])
    # Labels carry the document and page identity the model must cite.
    assert "PDF document pdf.0 page 2" in prompt
    assert "PDF document pdf.1 page 1" in prompt
    assert "pdf.0.page.2" in prompt
    assert "pdf.1.page.1" in prompt
    # With coordinates present, the flat legacy keys are not minted.
    assert "pdf.page.0" not in prompt
    specs = result["evidence_bundle"]["document_specifications"]
    assert [row["source_refs"] for row in specs] == [["pdf.0.page.2"]]
    assert result["evidence_bundle"]["pdf_page_sources"] == sources


def test_pdf_doc_scoped_citation_cannot_land_on_another_document():
    calls = []

    def transport(provider, *, system_prompt, text_parts, images, max_tokens=4096):
        calls.append({"system_prompt": system_prompt, "text_parts": list(text_parts), "images": list(images)})
        return _reply_with_specs([_pdf_spec_row(7.5, "g/10min", ["pdf.1.page.1"])]), {"attempts": 1}

    # Two documents share a page number 1; only the cited document's page states the value.
    sources = [
        {"source_ref": "pdf.0", "page_number": 1, "attachment_id": 11},
        {"source_ref": "pdf.1", "page_number": 1, "attachment_id": 12},
    ]
    with patch.object(_ip, "call_structured_multimodal", side_effect=transport):
        result = run_broker_inference(
            _provider(),
            seller={},
            pdf_page_text=["Cover page.", "MFI 7.5 g/10min."],
            pdf_page_sources=sources,
            catalog=_CATALOG,
        )

    prompt = calls[0]["system_prompt"] + "\n" + "\n".join(calls[0]["text_parts"])
    assert "PDF document pdf.0 page 1 (already extracted text; do not parse a file):\nCover page." in prompt
    assert "PDF document pdf.1 page 1 (already extracted text; do not parse a file):\nMFI 7.5 g/10min." in prompt
    assert [row["source_refs"] for row in result["evidence_bundle"]["document_specifications"]] == [["pdf.1.page.1"]]


def test_pdf_sources_mismatch_fails_closed_to_flat_keys():
    def transport(provider, *, system_prompt, text_parts, images, max_tokens=4096):
        return _reply_with_specs([_pdf_spec_row(7.5, "g/10min", ["pdf.0.page.1"])]), {"attempts": 1}

    with patch.object(_ip, "call_structured_multimodal", side_effect=transport):
        result = run_broker_inference(
            _provider(),
            seller={},
            pdf_page_text=["MFI 7.5 g/10min.", "Density 0.941 g/cm3."],
            pdf_page_sources=[{"source_ref": "pdf.0", "page_number": 1}],
            catalog=_CATALOG,
        )

    assert "pdf_page_sources_mismatch" in result["validation_issues"]
    # Fail closed: no coordinates, so no doc-scoped key was minted or admitted.
    assert result["evidence_bundle"]["document_specifications"] == []
    assert result["evidence_bundle"]["pdf_page_sources"] == []


def test_pdf_sources_with_unknown_shape_fail_closed():
    def transport(provider, *, system_prompt, text_parts, images, max_tokens=4096):
        return _reply_with_specs([_pdf_spec_row(7.5, "g/10min", ["docA.page.1"])]), {"attempts": 1}

    with patch.object(_ip, "call_structured_multimodal", side_effect=transport):
        result = run_broker_inference(
            _provider(),
            seller={},
            pdf_page_text=["MFI 7.5 g/10min."],
            pdf_page_sources=[{"source_ref": "docA", "page_number": 1}],
            catalog=_CATALOG,
        )

    assert "pdf_page_sources_mismatch" in result["validation_issues"]
    assert result["evidence_bundle"]["document_specifications"] == []
