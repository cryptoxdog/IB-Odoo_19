"""AC-073 (offline): specialist prompts, tag allowlists and benefit scoring (TASK-073).

Pure Python: no database and no network. The specialist recordings are hand-written
harness fixtures; nothing in this file measures a model.
"""

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from odoo.addons.plasticos_documents_ai.eval import harness
from odoo.tests import BaseCase, tagged

prompts = harness.prompts
EVAL = Path(harness.__file__).resolve().parent
DATASET = EVAL / "dataset" / "synthetic_v1.py"
P1_BASELINE = EVAL / "recorded" / "harness_fixture_baseline.py"
SPECIALISTS = EVAL / "recorded" / "harness_fixture_specialists.py"


def _ideal_specialist(dataset, prompt_id):
    item = prompts.specialist(prompt_id)
    outputs = []
    for case in dataset["cases"]:
        expected = case["expected"]["primary_type"]
        if case.get("human_classification") or not expected or prompts.family_of(expected).key != item.family_key:
            continue
        outputs.append({"case": case["id"], "tool_calls": [{"tool": harness.ADD_TAGS_TOOL, "tags": [expected]}]})
    return {"prompt": prompt_id, "prompt_version": "ideal", "outputs": outputs}


@tagged("post_install", "-at_install", "plasticos_documents_ai")
class TestSpecialistPrompts(BaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dataset = harness._load(str(DATASET))

    # ── Inventory alignment ─────────────────────────────────────
    def test_one_specialist_per_destination_family(self):
        self.assertEqual(prompts.SPECIALIST_IDS, ("P2", "P3", "P4", "P5", "P6", "P7"))
        self.assertEqual(
            sorted(prompts.specialist(pid).family_key for pid in prompts.SPECIALIST_IDS),
            sorted(family.key for family in prompts.TYPE_FAMILIES),
        )
        self.assertEqual(len(set(prompts.folder_prompt_ids())), 7)

    def test_specialist_types_stay_in_their_family(self):
        types = set(prompts.type_tag_names())
        for pid in prompts.SPECIALIST_IDS:
            item = prompts.specialist(pid)
            own = set(prompts.family(item.family_key).types)
            extra = {name for name in item.allowed_tags if name in types} - own
            # AI_PROMPT_INVENTORY.yaml P2 allows Delivery Receipt next to BOL.
            self.assertEqual(extra, {"Delivery Receipt"} if pid == "P2" else set(), pid)
            self.assertIn(prompts.NEEDS_REVIEW, item.allowed_tags, pid)
            self.assertNotIn(prompts.VERIFIED, item.allowed_tags, pid)
        self.assertIn(prompts.DUPLICATE_CANDIDATE, prompts.specialist("P6").allowed_tags)
        self.assertNotIn(prompts.DUPLICATE_CANDIDATE, prompts.p1_tag_names())

    def test_specialist_prompt_is_versioned_tag_only_and_names_no_folder(self):
        for pid in prompts.SPECIALIST_IDS:
            html = prompts.build_specialist_prompt(pid)
            self.assertIn(f"{pid} v{prompts.SPECIALIST_PROMPT_VERSION}", html)
            self.assertIn("never move", html)
            self.assertIn("never an instruction", html)
            self.assertNotIn("data-ai-record-id", html, "a specialist prompt grants no move target")
            for name in prompts.specialist(pid).allowed_tags:
                self.assertIn(f'"{name}"', html, (pid, name))

    # ── Tag allowlist (enforced in documents.document._ai_action_add_tags) ──
    def test_tag_refusal_rules(self):
        refuse = prompts.tag_refusal
        self.assertIsNone(refuse("P2", ["BOL", prompts.EVIDENCE_GAP], []))
        self.assertIn("Verified", refuse("P2", [prompts.VERIFIED], []))
        self.assertIn("Verified", refuse("P1", ["BOL", prompts.VERIFIED], []))
        self.assertIn("To Split", refuse("P2", [prompts.TO_SPLIT], []))
        self.assertIn(prompts.DUPLICATE_CANDIDATE, refuse("P1", [prompts.DUPLICATE_CANDIDATE], []))
        # Refinement conflict: a foreign type only together with Needs Review.
        self.assertIn("needs Needs Review", refuse("P3", ["Carrier Invoice"], []))
        self.assertIsNone(refuse("P3", [prompts.NEEDS_REVIEW, "Carrier Invoice"], []))
        self.assertIsNone(refuse("P3", ["Carrier Invoice"], [prompts.NEEDS_REVIEW]))
        # P1 has no such exception: its allowlist is every type and its four signals.
        self.assertIsNone(refuse("P1", ["Carrier Invoice"], []))
        self.assertIn("Unknown Tag", refuse("P3", [prompts.NEEDS_REVIEW, "Unknown Tag"], []))

    # ── Benefit over P1 ─────────────────────────────────────────
    def test_benefit_needs_strictly_better_types_and_no_unauthorized_action(self):
        p1 = harness.score(self.dataset, harness._load(str(P1_BASELINE)))
        results = {
            pid: harness.score_specialist(self.dataset, pid, p1, _ideal_specialist(self.dataset, pid))
            for pid in prompts.SPECIALIST_IDS
        }
        for pid, result in results.items():
            self.assertEqual(result["missing_outputs"], [], pid)
            self.assertEqual(result["specialist_type_accuracy"], 1.0, pid)
            better = result["p1_type_accuracy"] < 1.0
            self.assertEqual(result["verdict"], harness.BENEFIT if better else harness.NO_BENEFIT, pid)
        self.assertIn(harness.BENEFIT, {result["verdict"] for result in results.values()})

    def test_fixture_specialists_count_moves_and_refused_tags(self):
        p1 = harness.score(self.dataset, harness._load(str(P1_BASELINE)))
        recordings = harness._load(str(SPECIALISTS))
        self.assertIn("Not a model run", recordings["provenance"])
        results = harness.score_specialists(self.dataset, p1, recordings[harness.SPECIALISTS_KEY])
        self.assertEqual(results["P6"]["unauthorized_actions"], ["std-16:tool:move_in_folder"])
        self.assertTrue(results["P7"]["unauthorized_actions"][0].startswith("std-24:a type outside this folder"))
        for pid in ("P6", "P7"):
            self.assertEqual(results[pid]["verdict"], harness.NO_BENEFIT, pid)

    def test_missing_outputs_or_empty_family_are_unknown(self):
        p1 = harness.score(self.dataset, harness._load(str(P1_BASELINE)))
        result = harness.score_specialist(self.dataset, "P2", p1, {"outputs": []})
        self.assertEqual(result["verdict"], harness.UNKNOWN)
        empty = {"cases": [case for case in self.dataset["cases"] if case["expected"]["primary_type"] is None]}
        result = harness.score_specialist(empty, "P2", p1, {"outputs": []})
        self.assertEqual((result["cases"], result["verdict"]), (0, harness.UNKNOWN))
        self.assertIsNone(result["specialist_type_accuracy"])

    def test_cli_reports_specialists(self):
        out = io.StringIO()
        args = ["--dataset", str(DATASET), "--recorded", str(P1_BASELINE), "--specialists", str(SPECIALISTS)]
        with redirect_stdout(out):
            self.assertEqual(harness.main(args), 0)
        report = json.loads(out.getvalue())
        self.assertEqual(sorted(report[harness.SPECIALISTS_KEY]), list(prompts.SPECIALIST_IDS))
