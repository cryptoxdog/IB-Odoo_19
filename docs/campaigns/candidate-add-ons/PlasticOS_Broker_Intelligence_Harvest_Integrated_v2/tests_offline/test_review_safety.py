"""Evidence-focused pure and structural tests; Odoo ORM remains an unrun gate."""

import ast
import importlib.util
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


evidence = load("review_evidence", "plasticos_broker_intelligence/services/evidence.py")
reasoning = load("review_reasoning", "plasticos_broker_intelligence/services/reasoning.py")
rejection = load("review_rejection", "plasticos_broker_intelligence_rejections/services/rejection.py")


class FeedbackSourceEvidence(unittest.TestCase):
    def test_exact_rejection_eligible_only_for_verbatim_rejection_observation(self):
        check = evidence.is_source_rejection_evidence
        self.assertTrue(check("plasticos.offer", "rejected", "Wet cargo", "rejection", "Wet cargo"))
        self.assertTrue(check("plasticos.match.result", "rejected", "Wet cargo", "rejection", "Wet cargo"))
        for model, state, reason, kind, observation in (
            ("plasticos.intake", "rejected", "Wet cargo", "rejection", "Wet cargo"),
            ("plasticos.offer", "accepted", "Wet cargo", "rejection", "Wet cargo"),
            ("plasticos.offer", "rejected", "", "rejection", "Wet cargo"),
            ("plasticos.offer", "rejected", "Wet cargo", "quality", "Wet cargo"),
            ("plasticos.offer", "rejected", "Wet cargo", "rejection", "Materials passed inspection"),
            ("plasticos.match.result", "rejected", "Wet cargo", "correction", "Wet cargo"),
        ):
            with self.subTest(model=model, state=state, reason=reason, kind=kind):
                self.assertFalse(check(model, state, reason, kind, observation))

    def test_feedback_rule_is_actor_and_company_bounded(self):
        root = ET.parse(ROOT / "plasticos_broker_intelligence/security/record_rules.xml").getroot()
        rule = next(r for r in root.findall("record") if r.attrib["id"] == "rule_broker_feedback_company")
        domain = next(f.text for f in rule.findall("field") if f.attrib["name"] == "domain_force")
        self.assertIn("('actor_id', '=', user.id)", domain)
        self.assertIn("('company_id', 'in', company_ids)", domain)

    def test_audit_create_always_denied_in_owner_source(self):
        root = ast.parse((ROOT / "plasticos_broker_intelligence/models/audit.py").read_text())
        audit = next(x for x in root.body if isinstance(x, ast.ClassDef) and x.name == "BrokerReviewEvent")
        create = next(x for x in audit.body if isinstance(x, ast.FunctionDef) and x.name == "create")
        self.assertEqual(len(create.body), 1)
        self.assertIsInstance(create.body[0], ast.Raise)
        self.assertEqual(create.body[0].exc.func.id, "AccessError")
        owner = (ROOT / "plasticos_broker_intelligence/models/knowledge.py").read_text()
        self.assertIn("._append_from_knowledge(", owner)
        self.assertNotIn('broker.review.event"].sudo().create', owner)


class ApprovedRejectionPrerequisites(unittest.TestCase):
    def test_mfi_rejection_guidance_is_deferred_without_test_conditions(self):
        reference = {
            "state": "approved",
            "applies_to": "offer",
            "stable_key": "R:MFI",
            "version": 1,
            "name": "MFI_OUT_OF_RANGE",
            "reviewed_meaning": "Confirm test method before comparison",
            "prerequisite_keys": "mfi_value,mfi_conditions",
            "topic_tags": "mfi",
            "source_file": "reference.pdf",
            "source_sha256": "a" * 64,
            "source_selector": "p.1",
            "source_candidate_id": "R:MFI",
            "evidence_requirements": "MFI test conditions",
        }
        result = reasoning.build_response(
            "plasticos.offer",
            1,
            "rev",
            "MFI_OUT_OF_RANGE",
            {"mfi_value": {"state": "unknown", "value": None}},
            [reference],
        )
        self.assertEqual(result["approved_knowledge"], [])
        self.assertEqual(result["deferred_knowledge"][0]["missing_prerequisites"], ["mfi_value", "mfi_conditions"])
        answer = rejection.response(
            "MFI_OUT_OF_RANGE", "MFI_OUT_OF_RANGE", deferred_guidance=result["deferred_knowledge"]
        )
        self.assertIsNone(answer["approved_guidance"])
        self.assertTrue(answer["abstain"])
        self.assertFalse(answer["automatic_exclusion"])

    def test_bad_citation_never_becomes_approved_rejection_guidance(self):
        row = {
            "state": "approved",
            "applies_to": "offer",
            "stable_key": "R:OTHER",
            "version": 1,
            "name": "OTHER",
            "reviewed_meaning": "Review carefully",
            "topic_tags": "other",
            "source_file": "reference.pdf",
            "source_sha256": "invalid",
            "source_selector": "p.1",
            "source_candidate_id": "R:OTHER",
            "evidence_requirements": "Ask buyer",
        }
        result = reasoning.build_response("plasticos.offer", 1, "rev", "OTHER", {}, [row])
        self.assertFalse(result["approved_knowledge"])
        self.assertEqual(result["deferred_knowledge"][0]["reason"], "source_citation_unavailable")


class LeverageAlignmentRegression(unittest.TestCase):
    """Portable behavior checks; not a substitute for Odoo ORM authorization."""

    def _reference(self):
        return {
            "state": "approved",
            "applies_to": "offer",
            "stable_key": "REJ:WET",
            "version": 2,
            "name": "MOISTURE_HIGH",
            "reviewed_meaning": "Ask for lab conditions",
            "topic_tags": "moisture buyer refusal",
            "prerequisite_keys": "",
            "workflow_scope": "Only after buyer's specified moisture method is known",
            "source_file": "technical-reference.pdf",
            "source_sha256": "a" * 64,
            "source_selector": "page:3",
            "source_candidate_id": "REJ:WET",
            "evidence_requirements": "Buyer scope and measurement must be checked",
        }

    def test_approved_reference_is_not_equivalent_to_verified_applicability(self):
        response = reasoning.build_response(
            "plasticos.offer", 8, "rev1", "MOISTURE_HIGH buyer refusal", {}, [self._reference()]
        )
        approved = response["approved_knowledge"][0]
        self.assertFalse(approved["applicability_verified"])
        self.assertIn("moisture method", approved["workflow_scope"])
        self.assertIn("Verify that each cited reference", " ".join(response["next_human_actions"]))
        self.assertEqual(response["commercial_action"], "none")

    def test_truncated_knowledge_scope_must_not_claim_complete_answer(self):
        out = reasoning.build_response(
            "plasticos.offer",
            3,
            "r2",
            "MOISTURE_HIGH buyer refusal",
            {},
            [self._reference()],
            retrieval_complete=False,
            candidates_examined=150,
        )
        self.assertFalse(out["knowledge_retrieval"]["complete"])
        self.assertEqual(out["knowledge_retrieval"]["candidates_examined"], 150)
        self.assertEqual(out["uncertainty"], "unresolved")
        self.assertIn("bounded subset", " ".join(out["next_human_actions"]))
        self.assertEqual(len(out["approved_knowledge"]), 1)
        self.assertEqual(out["external_messages_sent"], 0)

    def test_complete_knowledge_scope_is_distinguished_from_truncated(self):
        out = reasoning.build_response(
            "plasticos.offer", 3, "r2", "MOISTURE_HIGH buyer refusal", {}, [self._reference()]
        )
        self.assertTrue(out["knowledge_retrieval"]["complete"])
        self.assertEqual(out["knowledge_retrieval"]["candidates_examined"], 1)
        self.assertEqual(out["uncertainty"], "conditional")

    def test_ambiguity_never_picks_first_approved_rejection_reference(self):
        from types import SimpleNamespace

        refs = [SimpleNamespace(stable_key="B"), SimpleNamespace(stable_key="A")]
        result, waiting = rejection.select_unique_reference(refs)
        self.assertIsNone(result)
        self.assertEqual(waiting[0]["reason"], "multiple_approved_references")
        self.assertEqual(waiting[0]["knowledge_keys"], ["A", "B"])
        self.assertEqual(rejection.select_unique_reference([]), (None, []))
        self.assertIs(rejection.select_unique_reference(refs[:1])[0], refs[0])

    def test_source_authorization_has_one_model_owner(self):
        service = (ROOT / "plasticos_broker_intelligence/models/advice_service.py").read_text()
        feedback = (ROOT / "plasticos_broker_intelligence/models/feedback.py").read_text()
        self.assertIn("source_id <= 0", service)
        self.assertIn("except (TypeError, ValueError)", service)
        self.assertIn("._authorized_target(model, res_id)", feedback)
        self.assertNotIn('record.check_access("read")', feedback)
        self.assertIn("len(knowledge) > 150", service)
