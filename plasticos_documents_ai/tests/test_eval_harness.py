"""AC-074: the evaluation harness scores recorded outputs offline (TASK-074).

No database and no network: the harness is pure Python over JSON. The recordings
used here are hand-written harness fixtures; nothing in this file measures a model.
"""

import io
import json
import re
from contextlib import redirect_stdout
from pathlib import Path

from odoo.addons.plasticos_documents_ai.eval import harness
from odoo.tests import BaseCase, tagged

EVAL = Path(harness.__file__).resolve().parent
DATASET = EVAL / "dataset" / "synthetic_v1.py"
BASELINE = EVAL / "recorded" / "harness_fixture_baseline.py"
CANDIDATE = EVAL / "recorded" / "harness_fixture_candidate.py"


def _load(path):
    return harness._load(str(path))


def _ideal_recording(dataset):
    """What a perfect P1 would do on every labeled case."""
    outputs = {}
    for case in dataset["cases"]:
        expected = case["expected"]
        if case.get("human_classification"):
            calls = []
        elif expected["primary_type"] is None:
            calls = [{"tool": harness.ADD_TAGS_TOOL, "tags": [harness.prompts.NEEDS_REVIEW]}]
        else:
            calls = [
                {"tool": harness.MOVE_TOOL, "folder": harness.prompts.family_of(expected["primary_type"]).key},
                {"tool": harness.ADD_TAGS_TOOL, "tags": [expected["primary_type"], *expected["signals"]]},
            ]
        outputs[case["id"]] = {"tool_calls": calls}
    return {"prompt": "P1", "prompt_version": "ideal", "outputs": outputs}


@tagged("post_install", "-at_install", "plasticos_documents_ai")
class TestEvalHarness(BaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dataset = _load(DATASET)

    # ── Labeled set ─────────────────────────────────────────────
    def test_every_mandatory_case_is_in_the_synthetic_set(self):
        coverage = harness.mandatory_case_coverage(self.dataset, harness.MANDATORY_CASES)
        self.assertEqual(coverage["missing"], [])

    def test_every_p1_type_has_a_standard_case(self):
        standard = {
            case["expected"]["primary_type"]
            for case in self.dataset["cases"]
            if "standard documents per category" in case["mandatory_cases"]
        }
        self.assertEqual(set(harness.prompts.type_tag_names()) - standard, set())

    def test_labels_name_only_known_types_and_signals(self):
        types = set(harness.prompts.type_tag_names())
        signals = set(harness.prompts.P1_REVIEW_SIGNALS)
        ids = [case["id"] for case in self.dataset["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        for case in self.dataset["cases"]:
            expected = case["expected"]
            self.assertTrue(expected["primary_type"] is None or expected["primary_type"] in types, case["id"])
            self.assertLessEqual(set(expected["signals"]), signals, case["id"])

    def test_no_real_document_content_is_committed(self):
        self.assertTrue(self.dataset["provenance"].startswith("Synthetic"))
        email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
        phone = re.compile(r"\+?\d[\d\s().-]{8,}\d")
        for path in [DATASET, BASELINE, CANDIDATE]:
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(email.search(text), path.name)
            self.assertIsNone(phone.search(text), path.name)
            self.assertNotIn("base64", text, path.name)
            self.assertNotIn("file_data", text, path.name)
        for recording in (_load(BASELINE), _load(CANDIDATE)):
            self.assertIn("Not a model run", recording["provenance"])

    # ── Metrics ─────────────────────────────────────────────────
    def test_ideal_outputs_meet_every_target(self):
        report = harness.score(self.dataset, _ideal_recording(self.dataset))
        metrics = report["metrics"]
        self.assertEqual(report["missing_outputs"], [])
        expected_unidentifiable = sum(1 for c in self.dataset["cases"] if c["expected"]["primary_type"] is None)
        classified = metrics["classification_documents"]
        self.assertEqual(metrics["auto_routed_share"], round((classified - expected_unidentifiable) / classified, 4))
        self.assertEqual(metrics["primary_family_accuracy_among_routed"], 1.0)
        self.assertEqual(metrics["human_classification_intervention"], 0.0)
        self.assertEqual(metrics["unnecessary_review"], 0.0)
        self.assertEqual(metrics["unauthorized_business_actions"], 0)
        self.assertEqual(metrics["human_correction_overwrites"], 0)
        self.assertTrue(all(row["met"] for row in report["targets"]), report["targets"])
        self.assertTrue(all(row["expected"] == row["predicted"] for row in report["confusion_matrix"]))

    def test_candidate_fixture_counts_every_unauthorized_action_and_overwrite(self):
        report = harness.score(self.dataset, _load(CANDIDATE))
        metrics = report["metrics"]
        unauthorized = {case_id: r["unauthorized"] for case_id, r in report["cases"].items() if r["unauthorized"]}
        self.assertEqual(
            unauthorized,
            {
                "inj-01": ["tag:Verified", "tool:create_vendor_bill"],
                "xco-01": ["move:company_b.transportation"],
            },
        )
        self.assertEqual(metrics["unauthorized_business_actions"], 3)
        self.assertEqual(metrics["human_correction_overwrites"], 1)
        self.assertEqual(
            {row["metric"]: row["met"] for row in report["targets"]}["unauthorized_business_actions"], False
        )
        self.assertIn({"expected": "Packing List", "predicted": "BOL", "count": 1}, report["confusion_matrix"])

    def test_unnecessary_review_and_conflicting_types_are_measured(self):
        report = harness.score(self.dataset, _load(BASELINE))
        self.assertEqual(report["metrics"]["unnecessary_review_count"], 1)
        self.assertTrue(report["cases"]["name-01"]["unnecessary_review"])
        self.assertEqual(report["cases"]["multi-02"]["predicted_type"], harness.CONFLICTING)
        self.assertFalse(report["cases"]["multi-02"]["routed"])

    def test_nothing_recorded_is_unknown_not_zero(self):
        report = harness.score(self.dataset, {"prompt": "P1", "prompt_version": "empty", "outputs": {}})
        self.assertEqual(len(report["missing_outputs"]), len(self.dataset["cases"]))
        self.assertEqual(report["metrics"]["auto_routed_share"], 0.0)
        self.assertIsNone(report["metrics"]["primary_family_accuracy_among_routed"])
        accuracy = {row["metric"]: row["met"] for row in report["targets"]}
        self.assertIsNone(accuracy["primary_family_accuracy_among_routed"])

    # ── Regression replay ───────────────────────────────────────
    def test_regression_replay_names_every_previously_correct_case_now_wrong(self):
        result = harness.regression(
            harness.score(self.dataset, _load(BASELINE)), harness.score(self.dataset, _load(CANDIDATE))
        )
        self.assertEqual(result["regressed"], ["human-01", "look-02", "xco-01"])
        self.assertEqual(result["fixed"], ["look-03", "multi-02", "name-01"])
        self.assertFalse(result["passes"])

    def test_cli_fails_on_regression_and_passes_without_one(self):
        args = ["--dataset", str(DATASET), "--recorded", str(CANDIDATE), "--baseline", str(BASELINE)]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(harness.main(args), 1)
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(harness.main(["--dataset", str(DATASET), "--recorded", str(BASELINE)]), 0)
        self.assertIn("auto_routed_share", json.loads(out.getvalue())["metrics"])
