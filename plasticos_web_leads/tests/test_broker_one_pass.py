"""One-pass broker scenarios (WL-INV-001, WL-INV-002).

Governing projection: ``l9.projection/coding-agent-execution@1``, bundle ``f8e44d1536cb``.
Source classes: ``l9.source/invariants@1``, ``l9.source/contracts@1``, ``l9.source/authority-model@1``.
Contracts applied: ``l9.contract/validation-and-correctness@1`` (assertions are not relaxed to
obtain a pass) and ``l9.contract/unknown-and-degradation@1`` (an absent flag stays a skip,
not a success).

While ``ONE_PASS_ORCHESTRATION`` is absent or false, every scenario in this module skips.
Bridge scenarios also skip until ``SPEC_PROPAGATION`` is true. Today's callers keep patching
``evaluate_economic_opportunity``. When the flag is true, triage calls ``run_broker_inference``
once on this module; that replacement returns the same assessment record plus
``economic_assessment``, and may carry ``document_specifications`` and ``representation_alignment``.
"""

from __future__ import annotations

import importlib
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

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
_SPEC_FACTS = {
    "mfi": 7.5,
    "density": 0.941,
    "moisture": 0.08,
    "notes": "Seller notes: natural pellets, no print.",
    "extracted_pdf_text": "PDF page 1: melt flow 7.5 g/10 min, density 0.941.",
}


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


def _cite_hot_assessment(assessment):
    """A HOT recommendation with no citation is forced back to REVIEW. Supply one."""
    if not isinstance(assessment, dict):
        return assessment
    core = {key: value for key, value in assessment.items() if key != "economic_assessment"}
    body = core.get("assessment")
    if not isinstance(body, dict):
        return {**core, "economic_assessment": core}
    if body.get("recommended_disposition") == "hot" and not body.get("supporting_evidence_refs"):
        body = dict(body)
        body["supporting_evidence_refs"] = ["seller.material_description"]
        core["assessment"] = body
    return {**core, "economic_assessment": core}


@contextmanager
def economic_assessment_patch(*, side_effect=None, return_value=None, document_specifications=None):
    """Patch the commercial assessment the live pipeline actually calls.

    The flag-off path patches ``evaluate_economic_opportunity`` only. The flag-on
    path also patches ``run_broker_inference`` and returns that same record.
    ``document_specifications`` is attached only when a caller supplies it.
    """

    def _assessment(*args, **kwargs):
        if side_effect is not None:
            try:
                return side_effect(*args, **kwargs)
            except TypeError:
                return side_effect(**kwargs)
        return return_value

    economic = patch(f"{_WEB_LEAD}.evaluate_economic_opportunity", side_effect=_assessment)
    if not one_pass_orchestration():
        with economic:
            yield
        return

    def _broker(*args, **kwargs):
        published = _cite_hot_assessment(_assessment(*args, **kwargs))
        if document_specifications is not None and isinstance(published, dict):
            published = dict(published)
            published["document_specifications"] = dict(document_specifications)
        return published

    with economic, patch(f"{_WEB_LEAD}.run_broker_inference", side_effect=_broker):
        yield


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


def _parent_map(root):
    parents = {}
    for parent in root.iter():
        for child in list(parent):
            parents[child] = parent
    return parents


_CONDITION_ATTRS = ("invisible", "t-if", "t-elif", "column_invisible")


def _condition_blob(element, parents):
    """Condition attributes from the element up, plus the 100/100 text itself."""
    chunks = []
    node = element
    while node is not None:
        chunks.extend(node.attrib[name] for name in _CONDITION_ATTRS if node.attrib.get(name))
        if node.text and "100/100" in node.text:
            chunks.append(node.text)
        node = parents.get(node)
    return " ".join(chunks)


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

    def _role_patches(self, recommend):
        normalize = patch(f"{_WEB_LEAD}.ai_normalizer.normalize_with_provider")
        vision = patch(f"{_WEB_LEAD}.image_analyzer.analyze_image_with_provider")
        economic = patch(f"{_WEB_LEAD}.evaluate_economic_opportunity")

        def broker(*args, **kwargs):
            try:
                assessment = recommend(*args, **kwargs)
            except TypeError:
                assessment = recommend(**kwargs)
            return _cite_hot_assessment(assessment)

        one_call = patch(f"{_WEB_LEAD}.run_broker_inference", side_effect=broker)
        return normalize, vision, economic, one_call

    def test_one_provider_request_not_three(self):
        normalize, vision, economic, one_call = self._role_patches(_recommend("hot"))
        with normalize as normalize_mock, vision as vision_mock, economic as economic_mock, one_call as broker:
            lead = self.WebLead.create_from_cognito(
                _payload("ONE-PASS-001", material="HDPE pellets", weight=f"{_GROUNDED_LBS} lbs")
            )
        broker.assert_called_once()
        normalize_mock.assert_not_called()
        vision_mock.assert_not_called()
        economic_mock.assert_not_called()
        self.assertEqual(lead.decision, "hot")
        self.assertEqual(lead.intake_id.quantity_per_load_lbs, _GROUNDED_LBS)

    def test_assessment_retry_is_the_same_single_call(self):
        with economic_assessment_patch(side_effect=_recommend("hot")):
            lead = self.WebLead.create_from_cognito(
                _payload("ONE-PASS-RETRY-001", material="HDPE pellets", weight=f"{_GROUNDED_LBS} lbs")
            )
        self.assertTrue(lead.intake_id)
        normalize, vision, economic, one_call = self._role_patches(_recommend("hot"))
        with normalize as normalize_mock, vision as vision_mock, economic as economic_mock, one_call as broker:
            lead.action_retry_economic_assessment()
        broker.assert_called_once()
        normalize_mock.assert_not_called()
        vision_mock.assert_not_called()
        economic_mock.assert_not_called()
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


@tagged("post_install", "-at_install", "plasticos", "web_lead", "one_pass")
class TestRepresentationAlignmentDisplay(TransactionCase):
    """100/100 is a view condition, not a model score (WL-INV-001, WL-INV-002)."""

    def setUp(self):
        super().setUp()
        if not one_pass_orchestration():
            self.skipTest("ONE_PASS_ORCHESTRATION is absent")

    def test_one_hundred_only_when_alignment_is_confirmed_for_the_whole_lot(self):
        allowed = {path.resolve() for path in _ALIGNMENT_VIEWS}
        offenders = []
        viewed = []
        for path in _MODULE_ROOT.rglob("*"):
            if path.suffix not in {".xml", ".py", ".js"} or "__pycache__" in path.parts or "tests" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if "100/100" not in text:
                continue
            if path.resolve() not in allowed:
                offenders.append(str(path.relative_to(_MODULE_ROOT)))
            else:
                viewed.append(path)
        self.assertFalse(offenders, f"100/100 display is views-only: {offenders}")
        self.assertTrue(viewed, "100/100 display is missing from the web-lead views")
        from defusedxml import ElementTree

        for path in viewed:
            root = ElementTree.parse(path).getroot()
            parents = _parent_map(root)
            gated = False
            for element in root.iter():
                own = " ".join([*(element.attrib.values()), element.text or "", element.tail or ""])
                if "100/100" not in own:
                    continue
                blob = _condition_blob(element, parents)
                self.assertIn("aligned", blob)
                self.assertIn("confirmed_whole_lot", blob)
                self.assertIn("seller", blob)
                self.assertIn("photo", blob)
                self.assertIn("spec", blob)
                gated = True
            self.assertTrue(gated, path.name)


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

    def test_spec_facts_and_pdf_text_survive_onto_the_opportunity(self):
        with economic_assessment_patch(side_effect=_recommend("hot"), document_specifications=_SPEC_FACTS):
            lead = self.WebLead.create_from_cognito(
                _payload(
                    "ONE-PASS-SPEC-001",
                    material="HDPE pellets",
                    weight=f"{_GROUNDED_LBS} lbs",
                )
            )
        specs = (lead.evidence_bundle or {}).get("document_specifications") or {}
        self.assertEqual(specs.get("mfi"), _SPEC_FACTS["mfi"])
        self.assertEqual(specs.get("density"), _SPEC_FACTS["density"])
        self.assertEqual(specs.get("moisture"), _SPEC_FACTS["moisture"])
        self.assertEqual(specs.get("notes"), _SPEC_FACTS["notes"])
        self.assertEqual(specs.get("extracted_pdf_text"), _SPEC_FACTS["extracted_pdf_text"])
        opportunity = lead.crm_lead_id
        self.assertTrue(opportunity)
        material = opportunity.opportunity_material_ids
        self.assertEqual(len(material), 1)
        self.assertAlmostEqual(material.melt_flow_index, _SPEC_FACTS["mfi"])
        self.assertAlmostEqual(material.density, _SPEC_FACTS["density"])
        self.assertAlmostEqual(material.moisture_percent, _SPEC_FACTS["moisture"])
        self.assertIn(_SPEC_FACTS["notes"], material.freeform_notes or "")
        preserved = f"{opportunity.description or ''} {material.freeform_notes or ''}"
        self.assertIn(_SPEC_FACTS["extracted_pdf_text"], preserved)
        self.assertEqual(material.quantity_per_load_lbs, _GROUNDED_LBS)
        self.assertNotIn(int(material.quantity_per_load_lbs), _PLANNING_NUMBERS)
