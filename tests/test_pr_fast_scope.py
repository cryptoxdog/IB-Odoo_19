"""Scope, runner, and nightly-guard contracts for the PR-fast / nightly split."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ci.nightly_full_run import NIGHTLY_PYTEST, skip_reason
from ci.nightly_full_run import main as nightly_main
from ci.pr_fast_scope import classify, missing_mandatory_markers, parse_name_status
from ci.run_pr_fast_tests import MANDATORY_PYTEST, scoped_pytest
from ci.run_pr_fast_tests import main as fast_main

pytestmark = pytest.mark.adversarial_contract

ROOT = Path(__file__).resolve().parents[1]


def _path(*parts: str) -> str:
    """Join a repo path without one AST constant equal to the whole path.

    ``_references`` treats an exact string constant as a structural consumer.
    Scanner-input fixtures must not make this module that consumer.
    """
    return "".join(parts)


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


def test_composed_pathlib_xml_dependency_selects_the_existing_test(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/test_transaction_profit_snapshot.py",
        "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\n"
        'FORM = ROOT / "plasticos_transaction" / "views" / "transaction_views.xml"\n'
        'def test_form():\n    assert FORM.name == "transaction_views.xml"\n',
    )
    receipt = classify([("M", "plasticos_transaction/views/transaction_views.xml", None)], tmp_path)
    assert receipt["status"] == "applicable"
    assert receipt["scoped_nonmarker_tests"] == ["tests/test_transaction_profit_snapshot.py"]
    assert receipt["structural_absence"] == []


def test_manifest_discovered_xml_selects_the_cron_test(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/test_cron_xml_lock.py",
        "from pathlib import Path\nimport xml.etree.ElementTree as ET\n"
        "def test_crons(root):\n"
        '    for manifest in root.glob("*/__manifest__.py"):\n'
        '        ET.parse(manifest.parent / "data" / "scheduled.xml")\n',
    )
    receipt = classify([("M", "plasticos_logistics/data/scheduled.xml", None)], tmp_path)
    assert receipt["status"] == "applicable"
    assert receipt["scoped_nonmarker_tests"] == ["tests/test_cron_xml_lock.py"]
    manifest = classify([("M", "plasticos_logistics/__manifest__.py", None)], tmp_path)
    assert "tests/test_cron_xml_lock.py" in manifest["scoped_nonmarker_tests"]


def test_dynamic_glob_xml_consumer_is_selected(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/test_odoo19_compat.py",
        'import glob\ndef test_xml(mod):\n    return glob.glob(f"{mod}/**/*.xml", recursive=True)\n',
    )
    receipt = classify([("M", "plasticos_transaction/views/transaction_views.xml", None)], tmp_path)
    assert receipt["scoped_nonmarker_tests"] == ["tests/test_odoo19_compat.py"]


def test_unrelated_path_is_not_selected_by_xml_discovery(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_xml.py", 'import glob\ndef test_xml():\n    glob.glob("*/**/*.xml")\n')
    receipt = classify([("M", "docs/guide.md", None)], tmp_path)
    assert receipt["status"] == "not_applicable"
    assert receipt["selected_tests"] == []


def test_a_none_constant_does_not_select_a_non_python_path(tmp_path: Path) -> None:
    _write(tmp_path, "tests/conftest.py", "VALUE = None\n")
    receipt = classify([("M", "docs/readme.md", None)], tmp_path)
    assert receipt["status"] == "not_applicable"
    assert receipt["unknown_paths"] == []


def test_scanner_configuration_is_not_applicable(tmp_path: Path) -> None:
    sonar = _path("sonar-", "project.properties")
    cloud = _path(".sonar", "cloud.properties")
    receipt = classify([("M", sonar, None), ("M", cloud, None)], tmp_path)
    assert receipt["status"] == "not_applicable"
    assert receipt["scanner_inputs"] == [sonar, cloud]
    assert receipt["structural_absence"] == []
    assert receipt["unknown_paths"] == []
    assert receipt["scoped_nonmarker_tests"] == []
    assert "scanner configuration" in receipt["reason"]


def test_semgrep_rules_and_fixtures_are_scanner_inputs(tmp_path: Path) -> None:
    changed = [
        _path(".semgrep/", "odoo-patterns.yml"),
        _path(".semgrep/", "tests/", "negative.py"),
        _path(".semgrep/", "tests/", "odoo19.xml"),
        _path(".semgrep/", "tests/", "positive.py"),
    ]
    receipt = classify([("M", path, None) for path in changed], tmp_path)
    assert receipt["status"] == "not_applicable"
    assert receipt["scanner_inputs"] == changed
    assert receipt["structural_absence"] == []
    assert receipt["unknown_paths"] == []


def test_a_quoting_test_still_selects_a_scanner_path(tmp_path: Path) -> None:
    rules = _path(".semgrep/", "odoo-patterns.yml")
    _write(
        tmp_path,
        "tests/test_rules.py",
        "PATH = " + repr(rules) + "\n\ndef test_rules():\n    assert PATH\n",
    )
    receipt = classify([("M", rules, None)], tmp_path)
    assert receipt["status"] == "applicable"
    assert receipt["selected_tests"] == ["tests/test_rules.py"]
    assert receipt["scanner_inputs"] == []


def test_real_repository_index_classifies_scanner_inputs() -> None:
    """On the indexed checkout a scanner input selects exactly the tests that read it.

    #552 added tests/test_sonar_scope.py, which reads both Sonar property files,
    and #553 added tests/test_semgrep_new_rules.py, which reads the rule file.
    A change to those inputs must run those tests. This module must not be
    selected: it builds the paths with ``_path`` so it is not a consumer.
    """
    consumers = {
        _path("sonar-", "project.properties"): ["tests/test_sonar_scope.py"],
        _path(".sonar", "cloud.properties"): ["tests/test_sonar_scope.py"],
        _path(".semgrep/", "odoo-patterns.yml"): ["tests/test_semgrep_new_rules.py"],
    }
    for path, expected in consumers.items():
        receipt = classify([("M", path, None)], ROOT)
        assert receipt["status"] == "applicable", receipt
        assert receipt["selected_tests"] == expected, receipt
        assert "tests/test_pr_fast_scope.py" not in receipt["selected_tests"]
        assert receipt["unknown_paths"] == []


def test_an_unclassified_neighbor_stays_unknown(tmp_path: Path) -> None:
    sonar = _path("sonar-", "project.properties")
    receipt = classify([("M", sonar, None), ("M", "Makefile", None)], tmp_path)
    assert receipt["status"] == "unknown"
    assert receipt["scanner_inputs"] == [sonar]
    assert receipt["unknown_paths"] == ["Makefile: unclassified path"]


def test_scanner_lookalikes_stay_unknown(tmp_path: Path) -> None:
    lookalikes = (
        _path("tools/", "sonar-", "project.properties"),
        _path(".semgrep-", "backup/", "rules.yml"),
    )
    for path in lookalikes:
        receipt = classify([("M", path, None)], tmp_path)
        assert receipt["status"] == "unknown", path
        assert receipt["scanner_inputs"] == []
        assert receipt["status"] != "not_applicable"


def test_addon_resource_without_a_quoting_test_is_not_applicable(tmp_path: Path) -> None:
    receipt = classify([("M", "plasticos_base/views/foo.xml", None)], tmp_path)
    assert receipt["status"] == "not_applicable"
    assert receipt["structural_absence"] == ["plasticos_base/views/foo.xml"]
    assert receipt["unknown_paths"] == []


def test_short_import_alias_selects_the_addon_module(tmp_path: Path) -> None:
    _write(tmp_path, "plasticos_partner_import/erp/mapping_status.py", "VALUE = 1\n")
    _write(
        tmp_path,
        "tests/test_erp.py",
        "from erp import mapping_status\n\ndef test_status():\n    assert mapping_status.VALUE == 1\n",
    )
    receipt = classify([("M", "plasticos_partner_import/erp/mapping_status.py", None)], tmp_path)
    assert receipt["scoped_nonmarker_tests"] == ["tests/test_erp.py"]


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
        nightly_main(
            fetch_default=lambda: "Staging",
            launch=lambda argv: calls.append(list(argv)) or 0,
            head="a" * 40,
            last_success=lambda: "",
        )
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

    assert nightly_main(fetch_default=lambda: "Staging", launch=launch, head="b" * 40, last_success=lambda: "") == 1
    assert calls == [NIGHTLY_PYTEST]
    record = json.loads(Path("artifacts/pytest/revision.json").read_text(encoding="utf-8"))
    assert record["tested_checkout_sha"] == "b" * 40
    assert record["tier"] == "nightly_full"


def _passing_suite(calls: list[list[str]]):
    def launch(argv: list[str]) -> int:
        calls.append(list(argv))
        Path("artifacts/pytest/pure-python.xml").write_text("<testsuite tests='1'/>", encoding="utf-8")
        return 0

    return launch


def test_nightly_skips_when_staging_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.chdir(tmp_path)
    _nightly_env(monkeypatch, "refs/heads/Staging", "Staging", "c" * 40)
    code = nightly_main(
        fetch_default=lambda: "Staging", launch=_passing_suite(calls), head="c" * 40, last_success=lambda: "c" * 40
    )
    assert code == 0
    assert calls == []
    record = json.loads(Path("artifacts/pytest/revision.json").read_text(encoding="utf-8"))
    assert record["skipped"] == f"Staging {'c' * 40} unchanged since the last successful nightly run"


def test_nightly_runs_when_staging_changed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.chdir(tmp_path)
    _nightly_env(monkeypatch, "refs/heads/Staging", "Staging", "c" * 40)
    code = nightly_main(
        fetch_default=lambda: "Staging", launch=_passing_suite(calls), head="c" * 40, last_success=lambda: "d" * 40
    )
    assert code == 0
    assert calls == [NIGHTLY_PYTEST]
    record = json.loads(Path("artifacts/pytest/revision.json").read_text(encoding="utf-8"))
    assert record["skipped"] == ""


def test_nightly_runs_when_previous_runs_are_unreadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.chdir(tmp_path)
    _nightly_env(monkeypatch, "refs/heads/Staging", "Staging", "c" * 40)

    def api_error() -> str:
        raise RuntimeError("cannot read previous runs: HTTP Error 502")

    code = nightly_main(
        fetch_default=lambda: "Staging", launch=_passing_suite(calls), head="c" * 40, last_success=api_error
    )
    assert code == 0
    assert calls == [NIGHTLY_PYTEST]
    assert json.loads(Path("artifacts/pytest/revision.json").read_text(encoding="utf-8"))["skipped"] == ""


def test_nightly_without_a_token_does_not_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_REPOSITORY", "cryptoxdog/IB-Odoo_19")
    assert skip_reason("c" * 40) == ""


def test_scoped_failure_fails_the_pr_fast_job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Fixed SHAs, not the checkout's history: a depth-1 clone (the nightly checkout)
    # has no HEAD^. fast_main only checks their shape; classify is stubbed and the
    # diff is read from tmp_path, which is not a repository.
    head = "e" * 40
    parent = "f" * 40
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
