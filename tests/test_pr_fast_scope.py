"""Scope, runner, and nightly-guard contracts for the PR-fast / nightly split."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ci.nightly_full_run import NIGHTLY_PYTEST
from ci.nightly_full_run import main as nightly_main
from ci.pr_fast_scope import classify, missing_mandatory_markers, parse_name_status
from ci.run_pr_fast_tests import MANDATORY_PYTEST, scoped_pytest
from ci.run_pr_fast_tests import main as fast_main

pytestmark = pytest.mark.adversarial_contract

ROOT = Path(__file__).resolve().parents[1]


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_required_marker_modules_stay_marked() -> None:
    assert missing_mandatory_markers(ROOT) == []


def test_changed_unmarked_test_is_selected(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_new.py", "def test_new():\n    assert True\n")
    receipt = classify([("A", "tests/test_new.py", None)], tmp_path)
    assert receipt["status"] == "applicable"
    assert receipt["scoped_nonmarker_tests"] == ["tests/test_new.py"]


def test_docs_only_change_is_not_applicable(tmp_path: Path) -> None:
    receipt = classify([("M", "docs/readme.md", None)], tmp_path)
    assert receipt["status"] == "not_applicable"
    assert receipt["scoped_nonmarker_tests"] == []


def test_executable_docs_python_is_unknown(tmp_path: Path) -> None:
    receipt = classify([("A", "docs/tool.py", None)], tmp_path)
    assert receipt["status"] == "unknown"
    assert receipt["status"] != "not_applicable"


def test_unresolvable_diff_is_unknown(tmp_path: Path) -> None:
    assert parse_name_status("U\tunknown\n") is None
    assert parse_name_status("M\t../secret\n") is None
    receipt = classify(None, tmp_path)
    assert receipt["status"] == "unknown"


def test_harness_and_requirements_block_selective_routing(tmp_path: Path) -> None:
    for path in ("pyproject.toml", "requirements.txt", "requirements-dev.txt", "tests/common.py"):
        receipt = classify([("M", path, None)], tmp_path)
        assert receipt["status"] == "unknown", path
        assert receipt["status"] != "not_applicable"


def test_ci_workflow_change_is_covered_by_mandatory_contracts(tmp_path: Path) -> None:
    receipt = classify([("M", ".github/workflows/ci.yml", None)], tmp_path)
    assert receipt["status"] == "applicable"
    assert receipt["covered_by_mandatory"] == [".github/workflows/ci.yml"]
    assert receipt["gate_sdk_job"] == "required"
    assert receipt["scoped_nonmarker_tests"] == []


def test_conftest_collection_change_is_not_a_bounded_fast_scope(tmp_path: Path) -> None:
    patch = "--- a/tests/conftest.py\n+++ b/tests/conftest.py\n@@\n-collect_ignore = []\n+collect_ignore = ['x']\n"
    receipt = classify([("M", "tests/conftest.py", None)], tmp_path, patches={"tests/conftest.py": patch})
    assert receipt["status"] == "unknown"


def test_conftest_without_a_patch_is_unknown(tmp_path: Path) -> None:
    receipt = classify([("M", "tests/conftest.py", None)], tmp_path)
    assert receipt["status"] == "unknown"


def test_conftest_tier_edit_stays_on_the_mandatory_contracts(tmp_path: Path) -> None:
    patch = "--- a/tests/conftest.py\n+++ b/tests/conftest.py\n@@\n-def _enforce_pr_fast():\n+def _enforce_pr_fast():\n+    return None\n"
    receipt = classify([("M", "tests/conftest.py", None)], tmp_path, patches={"tests/conftest.py": patch})
    assert receipt["status"] == "applicable"
    assert "tests/conftest.py" in receipt["covered_by_mandatory"]


def test_structural_import_selects_the_test_module(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/mod.py", "VALUE = 1\n")
    _write(tmp_path, "tests/test_mod.py", "import pkg.mod\n\ndef test_mod():\n    assert pkg.mod.VALUE == 1\n")
    receipt = classify([("M", "pkg/mod.py", None)], tmp_path)
    assert receipt["scoped_nonmarker_tests"] == ["tests/test_mod.py"]


def test_exact_path_constant_selects_the_test_module(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/mod.py", "VALUE = 1\n")
    _write(tmp_path, "tests/test_mod.py", "PATH = 'pkg/mod.py'\n\ndef test_mod():\n    assert PATH\n")
    receipt = classify([("M", "pkg/mod.py", None)], tmp_path)
    assert receipt["selected_tests"] == ["tests/test_mod.py"]


def test_a_none_constant_does_not_select_a_non_python_path(tmp_path: Path) -> None:
    _write(tmp_path, "tests/conftest.py", "VALUE = None\n")
    receipt = classify([("M", "docs/readme.md", None)], tmp_path)
    assert receipt["status"] == "not_applicable"
    assert receipt["unknown_paths"] == []


def test_a_substring_mention_does_not_select_a_test(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/mod.py", "VALUE = 1\n")
    _write(tmp_path, "tests/test_mod.py", "note = 'see pkg/mod for context'\n\ndef test_mod():\n    assert note\n")
    receipt = classify([("M", "pkg/mod.py", None)], tmp_path)
    assert receipt["selected_tests"] == []
    assert receipt["status"] == "not_applicable"


def test_rename_selects_the_new_test_name(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_new.py", "def test_new():\n    assert True\n")
    parsed = parse_name_status("R100\ttests/test_old.py\ttests/test_new.py\n")
    assert parsed == [("R", "tests/test_old.py", "tests/test_new.py")]
    receipt = classify(parsed or [], tmp_path)
    assert "tests/test_new.py" in receipt["selected_tests"]
    assert "tests/test_old.py" not in receipt["selected_tests"]
    assert receipt["renames"] == [{"old": "tests/test_old.py", "new": "tests/test_new.py"}]


def test_deleted_test_is_recorded_and_not_an_empty_success(tmp_path: Path) -> None:
    receipt = classify([("D", "tests/test_old.py", None)], tmp_path)
    assert receipt["status"] == "applicable"
    assert receipt["deleted"] == ["tests/test_old.py"]
    assert receipt["scoped_nonmarker_tests"] == []
    assert "deleted" in receipt["reason"]


def test_marked_module_is_not_run_twice(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/test_contract.py",
        "import pytest\npytestmark = pytest.mark.adversarial_contract\n\ndef test_contract():\n    assert True\n",
    )
    receipt = classify([("M", "tests/test_contract.py", None)], tmp_path)
    assert receipt["scoped_nonmarker_tests"] == []
    assert receipt["mandatory_modules"] == ["tests/test_contract.py"]


def test_checkout_sha_mismatch_is_unknown(tmp_path: Path) -> None:
    receipt = classify([], tmp_path, declared_head="a" * 40, observed_head="b" * 40)
    assert receipt["status"] == "unknown"


def test_gate_source_keeps_the_bridge_job_required(tmp_path: Path) -> None:
    receipt = classify([("M", "plasticos_gate/services/gate_client.py", None)], tmp_path)
    assert receipt["status"] == "applicable"
    assert receipt["gate_sdk_job"] == "required"
    assert receipt["gate_sdk_paths"] == ["plasticos_gate/services/gate_client.py"]


def test_scoped_argv_rejects_the_full_tree() -> None:
    with pytest.raises(SystemExit):
        scoped_pytest(["tests/"])
    argv = scoped_pytest(["tests/test_plain.py"])
    assert "tests/" not in argv
    assert "-m" in argv and "not adversarial_contract" in argv
    assert MANDATORY_PYTEST[MANDATORY_PYTEST.index("adversarial_contract") - 1] == "-m"
    assert "adversarial_contract" not in NIGHTLY_PYTEST
    assert "-k" not in NIGHTLY_PYTEST
    assert "--ignore" not in NIGHTLY_PYTEST
    assert NIGHTLY_PYTEST[NIGHTLY_PYTEST.index("pytest") + 1] == "tests/"


def _nightly_env(monkeypatch: pytest.MonkeyPatch, ref: str, branch: str, sha: str) -> None:
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_REF", ref)
    monkeypatch.setenv("GITHUB_SHA", sha)
    monkeypatch.setenv("PLASTICOS_CONTRACT_CI", "1")
    monkeypatch.setenv("PLASTICOS_CI_TIER", "nightly_full")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)


def test_production_dispatch_does_not_start_pytest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.chdir(tmp_path)
    _nightly_env(monkeypatch, "refs/heads/Production", "Staging", "a" * 40)
    with pytest.raises(SystemExit, match="refused ref"):
        nightly_main(fetch_default=lambda: "Staging", launch=lambda argv: calls.append(list(argv)) or 0, head="a" * 40)
    assert calls == []


def test_staging_nightly_runs_the_unfiltered_suite_and_keeps_a_red_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.chdir(tmp_path)
    _nightly_env(monkeypatch, "refs/heads/Staging", "Staging", "b" * 40)

    def launch(argv: list[str]) -> int:
        calls.append(list(argv))
        Path("artifacts/pytest/pure-python.xml").write_text("<testsuite tests='1' failures='1'/>", encoding="utf-8")
        return 1

    assert nightly_main(fetch_default=lambda: "Staging", launch=launch, head="b" * 40) == 1
    assert calls == [NIGHTLY_PYTEST]
    record = json.loads(Path("artifacts/pytest/revision.json").read_text(encoding="utf-8"))
    assert record["tested_checkout_sha"] == "b" * 40
    assert record["tier"] == "nightly_full"


def test_scoped_failure_fails_the_pr_fast_job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    parent = subprocess.check_output(["git", "rev-parse", "HEAD^"], text=True).strip()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PLASTICOS_CONTRACT_CI", "1")
    monkeypatch.setenv("PLASTICOS_CI_TIER", "pr_fast")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_SHA", head)
    monkeypatch.setenv("SCOPE_HEAD_SHA", head)
    monkeypatch.setenv("SCOPE_BASE_SHA", parent)
    monkeypatch.setattr("ci.run_pr_fast_tests.missing_mandatory_markers", lambda _root: [])
    monkeypatch.setattr(
        "ci.run_pr_fast_tests.classify",
        lambda *_args, **_kwargs: {
            "status": "applicable",
            "scoped_nonmarker_tests": ["tests/test_plain.py"],
            "gate_sdk_job": "required",
        },
    )
    calls: list[list[str]] = []

    def launch(argv: list[str]) -> int:
        calls.append(list(argv))
        return 0 if len(calls) == 1 else 1

    assert fast_main(launch=launch, head=head) == 1
    assert calls[0] == MANDATORY_PYTEST
    assert "tests/test_plain.py" in calls[1]
    assert "not adversarial_contract" in calls[1]
    assert "tests/" not in calls[1]


def test_unknown_scope_fails_without_a_second_suite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PLASTICOS_CONTRACT_CI", "1")
    monkeypatch.setenv("PLASTICOS_CI_TIER", "pr_fast")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_SHA", head)
    monkeypatch.setenv("SCOPE_HEAD_SHA", head)
    monkeypatch.delenv("SCOPE_BASE_SHA", raising=False)
    calls: list[list[str]] = []
    assert fast_main(launch=lambda argv: calls.append(list(argv)) or 0, head=head) == 1
    assert calls == [MANDATORY_PYTEST]
    receipt = json.loads(Path("artifacts/pytest/pr-fast-receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "unknown"
