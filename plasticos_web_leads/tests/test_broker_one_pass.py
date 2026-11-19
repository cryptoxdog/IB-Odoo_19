"""One-pass broker scenarios (WL-INV-001, WL-INV-002).

Governing projection: ``l9.projection/coding-agent-execution@1``, bundle ``f8e44d1536cb``.
Source classes: ``l9.source/invariants@1``, ``l9.source/contracts@1``, ``l9.source/authority-model@1``.
Contracts applied: ``l9.contract/validation-and-correctness@1`` (assertions are not relaxed to
obtain a pass) and ``l9.contract/unknown-and-degradation@1`` (an absent flag stays a skip,
not a success).

While ``ONE_PASS_ORCHESTRATION`` is absent or false, every scenario in this module skips.
Bridge scenarios also skip until ``SPEC_PROPAGATION`` is true. When the flag is true, triage
calls the real ``run_broker_inference``. These tests mock only ``call_structured_multimodal``.
The provider result is the bundle ``_result`` returns. Specification fixtures are lists of records.
"""

from __future__ import annotations

import base64
import hashlib
import importlib
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase, tagged

_WEB_LEAD = "odoo.addons.plasticos_web_leads.models.web_lead"
_BRIDGE_WEB_LEAD = "odoo.addons.plasticos_crm_bridge.models.web_lead"
_PLANNING_POLICY_REF = "web-lead-planning-defaults/v1"
_PLANNING_NUMBERS = (10000, 12000, 36000, 40000)
_PELLETS_LBS = 40000
_BALED_FILM_LBS = 36000
_PALLET_LBS = (10000, 12000)
_GROUNDED_LBS = 18500
_MODULE_ROOT = Path(__file__).resolve().parents[1]
_ALIGNMENT_VIEWS = (
    _MODULE_ROOT / "views" / "web_lead_views.xml",
    _MODULE_ROOT / "views" / "web_lead_ux.xml",
)
_CAPTURED_PROMPTS: list[str] = []
_PROVIDER_SPEC: dict[str, object] = {}
_PROVIDER_SPEC["provider"] = "openai"
_PROVIDER_SPEC["transport"] = "openai_compatible"
_PROVIDER_SPEC["api_key"] = "test-not-sent"
_PROVIDER_SPEC["model"] = "test-model"
_PROVIDER_SPEC["base_url"] = None
_PROVIDER_SPEC["workspace_id"] = None
_PROVIDER_SPEC["temperature"] = 0.0
_TRANSPORT = "odoo.addons.plasticos_web_leads.models.inference_provider.call_structured_multimodal"
_CONFIG = "odoo.addons.plasticos_web_leads.models.web_lead_config.PlasticosWebLeadConfig.get_one_pass_provider"
_SELLER_REF = "seller.material_description"


def _spec(prop, value, unit, *, cited=True):
    record = {}
    record["property"] = prop
    record["value"] = value
    record["unit"] = unit
    record["test_conditions"] = "190C/2.16kg" if prop == "MFI" else None
    record["source_refs"] = [_SELLER_REF] if cited else ["model.guess"]
    record["conflicts"] = []
    return record


_CITED_SPECS = [
    _spec("MFI", 7.5, "g/10min"),
    _spec("density", 0.941, "g/cm3"),
    _spec("moisture", 0.08, "%"),
]
_UNCITED_SPEC = _spec("ash", 12, "%", cited=False)


def one_pass_orchestration():
    """True only when Lane D has switched the live triage onto one broker call."""
    module = importlib.import_module(_WEB_LEAD)
    return getattr(module, "ONE_PASS_ORCHESTRATION", False) is True


def spec_propagation():
    """True only when the CRM bridge copies one-pass spec facts onto the opportunity."""
    try:
        module = importlib.import_module(_BRIDGE_WEB_LEAD)
    except ImportError:
        return False
    return getattr(module, "SPEC_PROPAGATION", False) is True


def _provider_body(disposition, specifications=None):
    """One provider reply. The real parser keeps only cited specification records."""
    specs = list(specifications or [])
    normalization: dict[str, object] = {}
    normalization["polymer"] = None
    normalization["confidence"] = 0.9
    normalization["estimated_lbs_per_load"] = None
    normalization["is_plastic"] = None
    return {
        "normalization": normalization,
        "vision": [],
        "economic": {
            "recommended_disposition": disposition,
            "opportunity_signal": "strong" if disposition == "hot" else "unknown",
            "confidence": 0.9,
            "material_suitability": "unsuitable" if disposition == "cold" else "supported",
            "commercial_rationale": "deterministic test recommendation",
            "supporting_evidence_refs": [_SELLER_REF],
            "contradictory_evidence_refs": [],
            "missing_information": [],
            "recommended_clarification": [],
            "disposition_rationale": "test",
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
        "document_specifications": specs,
    }


def _sample_disposition(sample):
    """Disposition named by an older assessment fake. Unavailable stays a failure."""
    if not isinstance(sample, dict):
        return "review", False
    if sample.get("status") == "unavailable":
        return "review", True
    assessment = sample.get("assessment") if isinstance(sample.get("assessment"), dict) else {}
    named = assessment.get("recommended_disposition") or assessment.get("recommendation")
    if named in {"hot", "review", "cold"}:
        return named, False
    return "review", False


@contextmanager
def economic_assessment_patch(*, side_effect=None, return_value=None, document_specifications=None):
    """Run the real broker function with the transport mocked.

    ``side_effect`` is ``_recommend(disposition)``. Specification rows are a list.
    An absent provider is left absent when ``return_value`` is ``"no_provider"``.
    """
    disposition = "review"
    unavailable = False
    sample = None
    if side_effect is not None:
        sample = side_effect(qualification_signals={})
    elif isinstance(return_value, dict):
        sample = return_value
    if sample is not None:
        disposition, unavailable = _sample_disposition(sample)
    specs = list(document_specifications or [])

    def transport(*_args, **kwargs):
        parts = [str(kwargs.get("system_prompt") or "")]
        parts.extend(str(part) for part in (kwargs.get("text_parts") or []))
        _CAPTURED_PROMPTS.append("\n".join(parts))
        if unavailable:
            raise RuntimeError("economic_provider_failed")
        return _provider_body(disposition, specs), {"attempts": 1}

    if return_value == "no_provider" or not one_pass_orchestration():
        fallback = side_effect or (lambda **_kwargs: return_value)
        with patch(f"{_WEB_LEAD}.evaluate_economic_opportunity", side_effect=fallback, create=True):
            yield
        return

    with (
        patch(_CONFIG, return_value=dict(_PROVIDER_SPEC)),
        patch(_TRANSPORT, side_effect=transport) as mocked,
    ):
        yield mocked, MagicMock()


def _payload(external_id, *, material, quantity="Two truckloads every month", weight=""):
    payload = {
        "Entry": {"Number": external_id},
        "YourBusinessCompanyName": f"Seller {external_id}",
        "DescribeYourMaterial": material,
        "WhatIsTheSourceOfThisMaterial": "Manufacturing production scrap",
        "WhatIsTheQuantity": quantity,
        "AreThereAnyContaminants": "none",
    }
    if weight:
        payload["WeightPerLoad"] = weight
    return payload


def _recommend(disposition):
    """Provider-shaped v2 assessment. Evidence refs come from the caller when it has them."""

    def fake(**kwargs):
        signals = kwargs.get("qualification_signals") or {}
        refs = sorted(signals.get("evidence_refs") or {})[:3] or ["seller.material_description"]
        return {
            "schema_version": "web-lead-economic-assessment/v2",
            "status": "assessed",
            "assessment": {
                "recommended_disposition": disposition,
                "opportunity_signal": "strong",
                "confidence": 0.9,
                "material_suitability": "supported",
                "commercial_rationale": "deterministic test recommendation",
                "supporting_evidence_refs": refs,
                "contradictory_evidence_refs": [],
                "missing_information": [],
                "recommended_clarification": [],
                "clarifications": [],
                "validation_issues": [],
            },
        }

    return fake


def _contains_number(node, number):
    if isinstance(node, bool):
        return False
    if isinstance(node, (int, float)) and node == number:
        return True
    if isinstance(node, dict):
        return any(_contains_number(value, number) for value in node.values())
    if isinstance(node, (list, tuple)):
        return any(_contains_number(value, number) for value in node)
    return False


def _planning_basis(bundle):
    basis = (bundle or {}).get("planning_basis")
    if not isinstance(basis, dict):
        raise AssertionError(f"evidence_bundle.planning_basis is missing: {bundle!r}"[:500])
    if basis.get("policy_ref") != _PLANNING_POLICY_REF:
        raise AssertionError(f"planning basis policy_ref is {basis.get('policy_ref')!r}")
    return basis


@tagged("post_install", "-at_install", "plasticos", "web_lead", "one_pass")
class TestBrokerOnePassScenarios(TransactionCase):
    """Scenarios that run only after ONE_PASS_ORCHESTRATION is true."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WebLead = cls.env["plasticos.web.lead"]
        cls.Activity = cls.env["mail.activity"]
        cls.config = cls.env["plasticos.web.lead.config"].sudo().get_config()
        cls.reviewer = cls.env.ref("base.user_admin")
        cls.config.write(
            {
                "ai_enabled": False,
                "vision_enabled": False,
                "hot_intake_reviewer_id": cls.reviewer.id,
                "attachment_allowed_hosts": False,
                "qualification_mode": "live",
            }
        )

    def setUp(self):
        super().setUp()
        if not one_pass_orchestration():
            self.skipTest("ONE_PASS_ORCHESTRATION is absent")

    def _hot_spy(self):
        calls = []
        model = type(self.WebLead)
        origin = model._process_hot_lead_triage

        def wrapper(records, merged, config):
            calls.extend(records.ids)
            return origin(records, merged, config)

        return calls, patch.object(model, "_process_hot_lead_triage", wrapper)

    def test_one_provider_request_not_three(self):
        with economic_assessment_patch(side_effect=_recommend("hot")) as mocks:
            lead = self.WebLead.create_from_cognito(
                _payload("ONE-PASS-001", material="HDPE pellets", weight=f"{_GROUNDED_LBS} lbs")
            )
        transport, economic = mocks
        transport.assert_called_once()
        economic.assert_not_called()
        self.assertEqual(lead.decision, "hot")
        self.assertEqual(lead.intake_id.quantity_per_load_lbs, _GROUNDED_LBS)

    def test_planning_basis_round_trips_as_json_on_the_lead(self):
        import json

        module = importlib.import_module(_WEB_LEAD)
        basis = module._planning_basis(module.PLANNING_DEFAULTS_V1)
        encoded = json.dumps(basis)
        self.assertEqual(json.loads(encoded)["policy_ref"], _PLANNING_POLICY_REF)
        self.assertIn("full domestic 53-foot trailer", basis["trailers"])
        lead = self.WebLead.create(
            {
                "lead_id": "PLAN-JSON-1",
                "decision": "review",
                "company_name": "Plan Co",
                "evidence_bundle": {"planning_basis": basis},
            }
        )
        stored = lead.evidence_bundle["planning_basis"]
        self.assertEqual(json.loads(json.dumps(stored)), json.loads(encoded))
        self.assertEqual(lead.estimated_lbs_per_load, 0)

    def test_assessment_retry_is_the_same_single_call(self):
        with economic_assessment_patch(side_effect=_recommend("hot")):
            lead = self.WebLead.create_from_cognito(
                _payload("ONE-PASS-RETRY-001", material="HDPE pellets", weight=f"{_GROUNDED_LBS} lbs")
            )
        self.assertTrue(lead.intake_id)
        with economic_assessment_patch(side_effect=_recommend("hot")) as mocks:
            lead.action_retry_economic_assessment()
        transport, economic = mocks
        transport.assert_called_once()
        economic.assert_not_called()
        self.assertEqual(self.env["plasticos.intake"].search_count([("source_lead_id", "=", lead.id)]), 1)

    def test_hot_without_grounded_weight_does_not_create_an_intake(self):
        calls, spy = self._hot_spy()
        with economic_assessment_patch(side_effect=_recommend("hot")), spy:
            lead = self.WebLead.create_from_cognito(_payload("ONE-PASS-HOT-001", material="HDPE pellets"))
        self.assertEqual(calls, [])
        self.assertEqual(lead.decision, "hot")
        self.assertEqual(lead.state, "review_pending")
        self.assertFalse(lead.intake_id)
        self.assertEqual(lead.estimated_lbs_per_load, 0)
        basis = _planning_basis(lead.evidence_bundle)
        self.assertTrue(_contains_number(basis, _PELLETS_LBS))
        self.assertFalse(_contains_number((lead.evidence_bundle or {}).get("quantity"), _PELLETS_LBS))
        analysis = lead.ai_analysis if isinstance(lead.ai_analysis, dict) else {}
        self.assertEqual(int(analysis.get("estimated_lbs") or 0), 0)
        activities = self.Activity.search([("res_model", "=", "plasticos.web.lead"), ("res_id", "=", lead.id)])
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities.user_id, self.reviewer)

    def test_later_grounded_weight_creates_one_intake(self):
        calls, spy = self._hot_spy()
        with economic_assessment_patch(side_effect=_recommend("hot")), spy:
            lead = self.WebLead.create_from_cognito(_payload("ONE-PASS-LATER-001", material="HDPE pellets"))
            self.assertEqual(calls, [])
            self.assertFalse(lead.intake_id)
            lead.estimated_lbs_per_load = _GROUNDED_LBS
            lead.action_retry_triage()
        self.assertEqual(calls, [lead.id])
        self.assertEqual(lead.decision, "hot")
        self.assertEqual(lead.state, "intake_created")
        self.assertEqual(lead.estimated_lbs_per_load, _GROUNDED_LBS)
        self.assertEqual(lead.intake_id.quantity_per_load_lbs, _GROUNDED_LBS)
        self.assertEqual(self.env["plasticos.intake"].search_count([("source_lead_id", "=", lead.id)]), 1)

    def test_planning_numbers_are_never_written_as_load_weight(self):
        cases = (
            ("ONE-PASS-PLAN-PELLET", "HDPE pellets", (_PELLETS_LBS,)),
            ("ONE-PASS-PLAN-FILM", "HDPE baled film", (_BALED_FILM_LBS,)),
            ("ONE-PASS-PLAN-PALLET", "mixed plastic pallets", _PALLET_LBS),
        )
        for external_id, material, figures in cases:
            with self.subTest(material=material):
                with economic_assessment_patch(side_effect=_recommend("hot")):
                    lead = self.WebLead.create_from_cognito(_payload(external_id, material=material))
                self.assertEqual(lead.estimated_lbs_per_load, 0, material)
                self.assertFalse(lead.intake_id, material)
                basis = _planning_basis(lead.evidence_bundle)
                for figure in figures:
                    self.assertTrue(_contains_number(basis, figure), material)
                    self.assertNotEqual(lead.estimated_lbs_per_load, figure, material)
                quantity = (lead.evidence_bundle or {}).get("quantity") or {}
                for key in ("load_weight_lbs", "quantity_per_load_lbs", "estimated_lbs_per_load"):
                    value = quantity.get(key)
                    if isinstance(value, (int, float)):
                        self.assertNotIn(int(value), _PLANNING_NUMBERS, key)

    def test_absent_provider_is_review_evidence_not_an_error(self):
        lead = self.WebLead.create_from_cognito(_payload("ONE-PASS-NOPROVIDER", material="HDPE pellets"))
        self.assertNotEqual(lead.state, "error")
        self.assertEqual(lead.decision, "review")
        bundle = lead.evidence_bundle or {}
        assessment = bundle.get("economic_assessment") or {}
        self.assertEqual(assessment.get("status"), "unavailable")
        self.assertEqual(lead.estimated_lbs_per_load, 0)

    def test_cold_recommendation_keeps_the_evidence(self):
        offered = [*_CITED_SPECS, _UNCITED_SPEC]
        with economic_assessment_patch(side_effect=_recommend("cold"), document_specifications=offered):
            lead = self.WebLead.create_from_cognito(
                _payload("ONE-PASS-COLD", material="copper scrap", quantity="scrap metal", weight="")
            )
        self.assertNotEqual(lead.state, "error")
        self.assertEqual(lead.decision, "cold")
        specs = (lead.evidence_bundle or {}).get("document_specifications") or []
        self.assertTrue(any(row.get("property") == "MFI" for row in specs if isinstance(row, dict)))
        self.assertFalse(any(row.get("property") == "ash" for row in specs if isinstance(row, dict)))
        self.assertTrue((lead.evidence_bundle or {}).get("economic_assessment"))

    def test_image_bytes_are_admitted_and_pdf_text_stays_unknown(self):
        module = importlib.import_module(_WEB_LEAD)
        prepare = getattr(module, "_broker_request_media", None)
        self.assertTrue(callable(prepare))
        raw = b"\xff\xd8\xff\xd9"
        attachment = self.env["ir.attachment"].create(
            {
                "name": "lot.jpg",
                "datas": base64.b64encode(raw),
                "mimetype": "image/jpeg",
            }
        )
        images, _documents, omissions = prepare(
            self.env["plasticos.web.lead"],
            [
                {
                    "content_type": "image/jpeg",
                    "acquisition_status": "success",
                    "ir_attachment_id": attachment.id,
                    "source_id": "photo-1",
                },
                {"content_type": "application/pdf", "source_id": "pdf-1", "pages": []},
            ],
        )
        self.assertEqual(images[0]["content"], raw)
        self.assertTrue(str(images[0]["content_type"]).startswith("image/"))
        self.assertNotIn("content_base64", images[0])
        self.assertTrue(any(item.get("reason") == "document_text_extraction_not_enabled" for item in omissions))

    def test_same_checksum_pdfs_remain_distinct(self):
        copy_pdfs = getattr(self.env["crm.lead"], "_plasticos_copy_web_lead_pdfs", None)
        if not callable(copy_pdfs):
            self.skipTest("PDF copy is owned by the CRM bridge")
        lead = self.WebLead.create({"lead_id": "PDF-IDENTITY-1", "decision": "review", "company_name": "PDF Co"})
        opportunity = self.env["crm.lead"].create({"name": "PDF identity", "type": "opportunity"})
        lead.crm_lead_id = opportunity
        encoded = base64.b64encode(b"%PDF-1.4 identical")
        for name in ("a.pdf", "b.pdf"):
            self.env["ir.attachment"].create(
                {
                    "name": name,
                    "datas": encoded,
                    "mimetype": "application/pdf",
                    "res_model": "plasticos.web.lead",
                    "res_id": lead.id,
                }
            )
        self.assertEqual(opportunity._plasticos_copy_web_lead_pdfs(), 2)
        self.assertEqual(opportunity._plasticos_copy_web_lead_pdfs(), 0)
        stored = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "crm.lead"),
                ("res_id", "=", opportunity.id),
                ("mimetype", "=", "application/pdf"),
            ]
        )
        self.assertEqual(len(stored), 2)


@tagged("post_install", "-at_install", "plasticos", "web_lead", "one_pass")
class TestRepresentationAlignmentDisplay(TransactionCase):
    """The model computes 100/100. The view displays that field (WL-INV-001, WL-INV-002)."""

    def setUp(self):
        super().setUp()
        if not one_pass_orchestration():
            self.skipTest("ONE_PASS_ORCHESTRATION is absent")

    def test_label_is_computed_and_the_view_displays_the_field(self):
        module = importlib.import_module(_WEB_LEAD)
        label = module.representation_alignment_label
        flags_without_evidence = {
            "seller": {"confirmation": "The photo and the specs cover the whole offered lot."},
            "representation_alignment": {
                "status": "aligned",
                "representativeness": "confirmed_whole_lot",
                "seller_confirmation_ref": "seller.confirmation",
                "covers_photo": True,
                "covers_specs": True,
                "covers_whole_offered_lot": True,
                "whole_lot_confirmed": True,
            },
        }
        confirmed = {
            "seller": {
                "confirmation": "The photo and the specs cover the whole offered lot.",
                "material_description": "MFI 7.5 g/10min",
            },
            "photo_findings": [{"source_id": "photo-1"}],
            "document_specifications": [_spec("MFI", 7.5, "g/10min")],
            "representation_alignment": {
                "status": "aligned",
                "representativeness": "confirmed_whole_lot",
                "seller_confirmation_ref": "seller.confirmation",
                "covers_photo": False,
                "covers_specs": False,
                "covers_whole_offered_lot": False,
                "whole_lot_confirmed": False,
            },
        }
        self.assertNotEqual(label(flags_without_evidence), "100/100")
        self.assertEqual(label(confirmed), "100/100")
        from defusedxml import ElementTree

        displayed = False
        for path in _ALIGNMENT_VIEWS:
            root = ElementTree.parse(path).getroot()
            for element in root.iter():
                blob = " ".join([*(element.attrib.values()), element.text or ""])
                if "representation_alignment_display" in blob:
                    displayed = True
        self.assertTrue(displayed, "the view must display representation_alignment_display")


@tagged("post_install", "-at_install", "plasticos", "web_lead", "one_pass")
class TestSpecPropagationToOpportunity(TransactionCase):
    """Spec facts and PDF text reach the opportunity only after SPEC_PROPAGATION is true."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WebLead = cls.env["plasticos.web.lead"]
        cls.config = cls.env["plasticos.web.lead.config"].sudo().get_config()
        cls.config.write(
            {
                "ai_enabled": False,
                "vision_enabled": False,
                "hot_intake_reviewer_id": cls.env.ref("base.user_admin").id,
                "attachment_allowed_hosts": False,
                "qualification_mode": "live",
            }
        )

    def setUp(self):
        super().setUp()
        if not spec_propagation():
            self.skipTest("SPEC_PROPAGATION is absent")
        if not one_pass_orchestration():
            self.skipTest("ONE_PASS_ORCHESTRATION is absent")

    def _spec_map(self, lead):
        rows = (lead.evidence_bundle or {}).get("document_specifications") or []
        self.assertIsInstance(rows, list)
        return {row.get("property"): row for row in rows if isinstance(row, dict)}

    def test_cited_specs_are_kept_and_an_uncited_number_is_refused(self):
        offered = [*_CITED_SPECS, _UNCITED_SPEC]
        with economic_assessment_patch(side_effect=_recommend("hot"), document_specifications=offered):
            lead = self.WebLead.create_from_cognito(
                _payload("ONE-PASS-SPEC-001", material="HDPE pellets", weight=f"{_GROUNDED_LBS} lbs")
            )
        specs = self._spec_map(lead)
        self.assertEqual(specs["MFI"]["value"], 7.5)
        self.assertEqual(specs["MFI"]["unit"], "g/10min")
        self.assertNotIn("ash", specs)
        opportunity = lead.crm_lead_id
        self.assertTrue(opportunity)
        material = opportunity.opportunity_material_ids
        self.assertEqual(len(material), 1)
        self.assertFalse(material.melt_flow_index)
        self.assertFalse(material.density)
        self.assertFalse(material.moisture_percent)
        self.assertFalse(lead.intake_id.mfi_value)
        self.assertIn("MFI", material.freeform_notes or "")
        self.assertIn("7.5", material.freeform_notes or "")
        self.assertNotIn("ash", material.freeform_notes or "")
        self.assertEqual(material.quantity_per_load_lbs, _GROUNDED_LBS)
        self.assertNotIn(int(material.quantity_per_load_lbs), _PLANNING_NUMBERS)

    def test_substantiated_seller_text_fills_empty_columns(self):
        stated = "HDPE pellets. MFI 7.5 g/10min. Density 0.941 g/cm3. Moisture 0.08 %."
        with economic_assessment_patch(side_effect=_recommend("hot"), document_specifications=_CITED_SPECS):
            lead = self.WebLead.create_from_cognito(
                _payload("ONE-PASS-SPEC-PROVEN", material=stated, weight=f"{_GROUNDED_LBS} lbs")
            )
        material = lead.crm_lead_id.opportunity_material_ids
        self.assertAlmostEqual(material.melt_flow_index, 7.5)
        self.assertAlmostEqual(material.density, 0.941)
        self.assertAlmostEqual(material.moisture_percent, 0.08)
        self.assertAlmostEqual(lead.intake_id.mfi_value, 7.5)
        self.assertAlmostEqual(lead.intake_id.density_value, 0.941)
        self.assertAlmostEqual(lead.intake_id.moisture_pct, 0.08)

    def test_two_values_for_one_property_stay_in_the_note(self):
        stated = "HDPE pellets. MFI 7.5 g/10min. MFI 4.2 g/10min."
        offered = [_spec("MFI", 7.5, "g/10min"), _spec("MFI", 4.2, "g/10min")]
        with economic_assessment_patch(side_effect=_recommend("hot"), document_specifications=offered):
            lead = self.WebLead.create_from_cognito(
                _payload("ONE-PASS-SPEC-CONFLICT", material=stated, weight=f"{_GROUNDED_LBS} lbs")
            )
        material = lead.crm_lead_id.opportunity_material_ids
        self.assertFalse(material.melt_flow_index)
        self.assertFalse(lead.intake_id.mfi_value)
        notes = material.freeform_notes or ""
        self.assertIn("7.5", notes)
        self.assertIn("4.2", notes)

    def test_replay_replaces_the_owned_specification_and_keeps_later_notes(self):
        stated = "HDPE pellets. MFI 7.5 g/10min. Density 0.941 g/cm3. Moisture 0.08 %."
        with economic_assessment_patch(side_effect=_recommend("hot"), document_specifications=_CITED_SPECS):
            lead = self.WebLead.create_from_cognito(
                _payload("ONE-PASS-SPEC-REPLAY", material=stated, weight=f"{_GROUNDED_LBS} lbs")
            )
        material = lead.crm_lead_id.opportunity_material_ids
        self.assertAlmostEqual(material.melt_flow_index, 7.5)
        material.freeform_notes = f"{material.freeform_notes}\nBroker measured the lot on site."
        corrected = [_spec("MFI", 4.2, "g/10min"), _spec("density", 0.941, "g/cm3"), _spec("moisture", 0.08, "%")]
        seller = dict((lead.evidence_bundle or {}).get("seller") or {})
        seller["material_description"] = "HDPE pellets. MFI 4.2 g/10min. Density 0.941 g/cm3. Moisture 0.08 %."
        bundle = lead.evidence_bundle or {}
        lead._write_recovered_assessment(
            bundle.get("economic_assessment") or {},
            bundle.get("economic_assessment_history") or [],
            {"seller": seller, "document_specifications": corrected},
        )
        propagate = getattr(lead, "_propagate_one_pass_spec", None)
        self.assertTrue(callable(propagate))
        propagate(lead.crm_lead_id)
        material = lead.crm_lead_id.opportunity_material_ids
        self.assertAlmostEqual(material.melt_flow_index, 4.2)
        notes = material.freeform_notes or ""
        self.assertIn("4.2", notes)
        self.assertIn("Broker measured the lot on site.", notes)
        self.assertNotIn("7.5", notes)
        description = str(lead.crm_lead_id.description or "")
        start = description.find('class="plasticos-spec"')
        end = description.find("</div>", start)
        block = description[start:end]
        self.assertIn("4.2", block)
        self.assertNotIn("7.5", block)

    def test_human_entered_spec_is_not_replaced(self):
        stated = "HDPE pellets. MFI 7.5 g/10min. Density 0.941 g/cm3. Moisture 0.08 %."
        with economic_assessment_patch(side_effect=_recommend("hot"), document_specifications=_CITED_SPECS):
            lead = self.WebLead.create_from_cognito(
                _payload("ONE-PASS-SPEC-HUMAN", material=stated, weight=f"{_GROUNDED_LBS} lbs")
            )
        material = lead.crm_lead_id.opportunity_material_ids
        material.melt_flow_index = 9.1
        seller = dict((lead.evidence_bundle or {}).get("seller") or {})
        seller["material_description"] = "HDPE pellets. MFI 4.2 g/10min. Density 0.941 g/cm3. Moisture 0.08 %."
        bundle = lead.evidence_bundle or {}
        lead._write_recovered_assessment(
            bundle.get("economic_assessment") or {},
            bundle.get("economic_assessment_history") or [],
            {
                "seller": seller,
                "document_specifications": [
                    _spec("MFI", 4.2, "g/10min"),
                    _spec("density", 0.941, "g/cm3"),
                    _spec("moisture", 0.08, "%"),
                ],
            },
        )
        lead._propagate_one_pass_spec(lead.crm_lead_id)
        self.assertAlmostEqual(material.melt_flow_index, 9.1)
        self.assertIn("4.2", material.freeform_notes or "")


def _ocr_response(pages, status_code=200):
    class _Response:
        status_code = status_code

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "ocr-1",
                "object": "ocr.result",
                "purpose": "text_recognition",
                "page_count": len(pages),
                "pages": pages,
            }

    return _Response()


def _ocr_page(index, text, finish_reason="stop"):
    return {"index": index, "text": text, "finish_reason": finish_reason}


@tagged("post_install", "-at_install", "plasticos", "web_lead", "one_pass")
class TestPdfOcrIntegration(TransactionCase):
    """DeepSeek-hosted PDF OCR: admission, doc-scoped citations, replay, and failure visibility."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WebLead = cls.env["plasticos.web.lead"]
        cls.config = cls.env["plasticos.web.lead.config"].sudo().get_config()
        cls.config.write({"deepseek_api_key": "test-ocr-key", "qualification_mode": "legacy"})

    def setUp(self):
        super().setUp()
        if not one_pass_orchestration():
            self.skipTest("ONE_PASS_ORCHESTRATION is absent")

    def _pdf_attachment(self, lead, payload=b"%PDF-1.4", name="sheet.pdf"):
        return self.env["ir.attachment"].create(
            {
                "name": name,
                "datas": base64.b64encode(payload),
                "mimetype": "application/pdf",
                "res_model": "plasticos.web.lead",
                "res_id": lead.id,
            }
        )

    def test_ocr_rows_reach_the_broker_with_doc_scoped_citations(self):
        module = importlib.import_module(_WEB_LEAD)
        lead = self.WebLead.create({"lead_id": "OCR-MEDIA-1", "company_name": "OCR Co"})
        content = b"%PDF-1.4 scanned sheet"
        results = module.process_attachments(
            lead=lead,
            attachments=[
                {
                    "source_id": "src-a",
                    "attachment_index": 0,
                    "filename": "sheet.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": len(content),
                    "source_url": "https://files.example.test/sheet.pdf",
                }
            ],
            allowed_hosts=("files.example.test",),
            resolver=lambda _host: ["93.184.216.34"],
            http_get=lambda *_args, **_kwargs: _plain_response(content),
            ocr_api_key="test-ocr-key",
            http_post=lambda _url, **_kwargs: _ocr_response(
                [_ocr_page(0, "MFI 7.5 g/10min"), _ocr_page(1, "Density 0.941 g/cm3")]
            ),
        )
        row = results[0]
        self.assertEqual(row["acquisition_status"], "success")
        self.assertEqual(row["analysis_status"], "extracted")
        self.assertIsNone(row["error"])
        self.assertEqual([page["parse_status"] for page in row["pages"]], ["parsed", "parsed"])
        self.assertEqual([page["page_number"] for page in row["pages"]], [1, 2])

        images, documents, omissions = module._broker_request_media(lead, results)
        self.assertEqual(images, [])
        self.assertEqual(omissions, [])
        pages, sources = module._pdf_media(documents)
        self.assertEqual(pages, ["MFI 7.5 g/10min", "Density 0.941 g/cm3"])
        self.assertEqual([source["source_ref"] for source in sources], ["pdf.0", "pdf.0"])
        self.assertEqual([source["page_number"] for source in sources], [1, 2])
        self.assertEqual(sources[0]["attachment_id"], row["ir_attachment_id"])

    def test_two_documents_with_identical_bytes_never_conflate_citations(self):
        module = importlib.import_module(_WEB_LEAD)
        bundle = {
            "pdf_page_text": ["Cover A.", "MFI 7.5 g/10min", "Cover B.", "MFI 4.2 g/10min"],
            "pdf_page_sources": [
                {"source_ref": "pdf.0", "page_number": 1, "attachment_id": 1},
                {"source_ref": "pdf.0", "page_number": 2, "attachment_id": 1},
                {"source_ref": "pdf.1", "page_number": 1, "attachment_id": 2},
                {"source_ref": "pdf.1", "page_number": 2, "attachment_id": 2},
            ],
        }
        self.assertIn("7.5", module._citation_text("pdf.0.page.2", bundle))
        self.assertIn("4.2", module._citation_text("pdf.1.page.2", bundle))
        self.assertIn("Cover A.", module._citation_text("pdf.0.page.1", bundle))
        self.assertIn("Cover B.", module._citation_text("pdf.1.page.1", bundle))
        # A page that does not exist in the cited document resolves nowhere.
        self.assertEqual(module._citation_text("pdf.0.page.9", bundle), "")
        self.assertEqual(module._citation_text("pdf.3.page.1", bundle), "")
        # Legacy flat citations keep their original meaning.
        self.assertIn("7.5", module._citation_text("pdf.page.1", bundle))

    def test_contradictory_pdf_specs_fill_no_column_and_stay_visible(self):
        module = importlib.import_module(_WEB_LEAD)
        bundle = {
            "pdf_page_text": ["MFI 7.5 g/10min", "MFI 4.2 g/10min"],
            "pdf_page_sources": [
                {"source_ref": "pdf.0", "page_number": 1},
                {"source_ref": "pdf.0", "page_number": 2},
            ],
        }
        specs = [
            {
                "property": "MFI",
                "value": 7.5,
                "unit": "g/10min",
                "test_conditions": None,
                "source_refs": ["pdf.0.page.1"],
            },
            {
                "property": "MFI",
                "value": 4.2,
                "unit": "g/10min",
                "test_conditions": None,
                "source_refs": ["pdf.0.page.2"],
            },
        ]
        measures, notes = module._intake_spec_facts(specs, bundle)
        self.assertNotIn("mfi_value", measures)
        self.assertIn("7.5", notes)
        self.assertIn("4.2", notes)
        self.assertIn("pdf.0.page.1", notes)
        self.assertIn("pdf.0.page.2", notes)

    def test_replay_reuses_complete_ocr_and_recovers_legacy_rows(self):
        module = importlib.import_module(_WEB_LEAD)
        lead = self.WebLead.create({"lead_id": "OCR-REPLAY-1", "company_name": "Replay Co"})
        attachment = self._pdf_attachment(lead, payload=b"%PDF-1.4 legacy sheet")
        legacy_row = {
            "source_id": "src-a",
            "attachment_index": 0,
            "filename": "sheet.pdf",
            "content_type": "application/pdf",
            "content_sha256": hashlib.sha256(b"%PDF-1.4 legacy sheet").hexdigest(),
            "ir_attachment_id": attachment.id,
            "acquisition_status": "success",
            "analysis_status": "unsupported",
            "error": {"code": "document_text_extraction_not_enabled", "message": "not enabled in V1"},
            "pages": [],
        }
        post_path = "odoo.addons.plasticos_web_leads.models.attachment_processor.requests.post"
        resolver_path = "odoo.addons.plasticos_web_leads.models.attachment_processor.resolve_host_addresses"
        with (
            patch(resolver_path, return_value=["93.184.216.34"]),
            patch(post_path, side_effect=lambda _url, **_kwargs: _ocr_response([_ocr_page(0, "MFI 7.5 g/10min")])),
        ):
            refreshed = lead._refresh_pdf_ocr_rows([legacy_row], self.config, force=False)
        self.assertEqual(refreshed[0]["ocr_status"], "complete")
        self.assertIsNone(refreshed[0]["error"])
        self.assertEqual(refreshed[0]["pages"][0]["text"], "MFI 7.5 g/10min")

        # Ordinary replay: complete results for the unchanged revision cost nothing.
        with patch(post_path, side_effect=AssertionError("a paid OCR call ran again")):
            second = lead._refresh_pdf_ocr_rows([refreshed[0]], self.config, force=False)
        self.assertEqual(second[0], refreshed[0])

        # A changed revision is never mistaken for the previous result.
        attachment.write({"datas": base64.b64encode(b"%PDF-1.4 revised sheet")})
        with (
            patch(resolver_path, return_value=["93.184.216.34"]),
            patch(post_path, side_effect=lambda _url, **_kwargs: _ocr_response([_ocr_page(0, "MFI 4.2 g/10min")])),
        ):
            changed = lead._refresh_pdf_ocr_rows([refreshed[0]], self.config, force=False)
        self.assertEqual(changed[0]["pages"][0]["text"], "MFI 4.2 g/10min")

    def test_explicit_retry_reattempts_a_failed_extraction_only_when_forced(self):
        module = importlib.import_module(_WEB_LEAD)
        lead = self.WebLead.create({"lead_id": "OCR-RETRY-1", "company_name": "Retry Co"})
        attachment = self._pdf_attachment(lead, payload=b"%PDF-1.4 locked sheet")
        failed_row = {
            "source_id": "src-a",
            "attachment_index": 0,
            "content_type": "application/pdf",
            "content_sha256": hashlib.sha256(b"%PDF-1.4 locked sheet").hexdigest(),
            "ir_attachment_id": attachment.id,
            "acquisition_status": "success",
            "ocr_attempted_sha256": hashlib.sha256(b"%PDF-1.4 locked sheet").hexdigest(),
            "error": {"code": "document_text_extraction_failed", "message": "HTTP 503"},
            "pages": [],
        }
        # Ordinary replay never re-pays a failed extraction.
        with patch(
            "odoo.addons.plasticos_web_leads.models.attachment_processor.requests.post",
            side_effect=AssertionError("a failed extraction was retried without an explicit re-run"),
        ):
            ordinary = lead._refresh_pdf_ocr_rows([failed_row], self.config, force=False)
        self.assertEqual(ordinary[0]["error"]["code"], "document_text_extraction_failed")

        # An explicit re-run may read the saved original and try again.
        with (
            patch(
                "odoo.addons.plasticos_web_leads.models.attachment_processor.resolve_host_addresses",
                return_value=["93.184.216.34"],
            ),
            patch(
                "odoo.addons.plasticos_web_leads.models.attachment_processor.requests.post",
                side_effect=lambda _url, **_kwargs: _ocr_response([_ocr_page(0, "MFI 7.5 g/10min")]),
            ),
        ):
            recovered = lead._refresh_pdf_ocr_rows([failed_row], self.config, force=True)
        self.assertEqual(recovered[0]["ocr_status"], "complete")
        self.assertIsNone(recovered[0]["error"])

    def test_ocr_failure_stays_document_local_and_seller_evidence_survives(self):
        module = importlib.import_module(_WEB_LEAD)
        lead = self.WebLead.create({"lead_id": "OCR-FAIL-1", "company_name": "Fail Co"})
        content = b"%PDF-1.4 encrypted sheet"
        results = module.process_attachments(
            lead=lead,
            attachments=[
                {
                    "source_id": "src-a",
                    "attachment_index": 0,
                    "filename": "sheet.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": len(content),
                    "source_url": "https://files.example.test/sheet.pdf",
                }
            ],
            allowed_hosts=("files.example.test",),
            resolver=lambda _host: ["93.184.216.34"],
            http_get=lambda *_args, **_kwargs: _plain_response(content),
            ocr_api_key="test-ocr-key",
            http_post=lambda _url, **_kwargs: _ocr_response(
                {"error": {"message": "password protected", "code": "invalid_file_format_error"}}
            ),
        )
        row = results[0]
        self.assertEqual(row["acquisition_status"], "success")
        self.assertEqual(row["error"]["code"], "document_text_extraction_failed")
        self.assertIn("password protected", row["error"]["message"])
        images, _documents, omissions = module._broker_request_media(lead, results)
        self.assertEqual(images, [])
        self.assertTrue(any(item.get("reason") == "document_text_extraction_failed" for item in omissions))
        # The failure never erases seller evidence or the stored bytes.
        stored = self.env["ir.attachment"].browse(row["ir_attachment_id"])
        self.assertTrue(stored.exists())
        self.assertEqual(module._image_content_bytes(stored.datas), content)


class _PlainResponse:
    def __init__(self, content):
        self.content = content
        self.status_code = 200
        self.headers = {"Content-Type": "application/pdf"}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        del chunk_size
        yield self.content


def _plain_response(content):
    return _PlainResponse(content)
