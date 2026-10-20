"""Behavioral contracts for CI routing, full test reachability and skip enforcement."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.adversarial_contract


def _workflow() -> dict:
    doc = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    # PyYAML's YAML 1.1 loader recognizes unquoted `on` as a Boolean key.
    if True in doc:
        doc["on"] = doc.pop(True)
    return doc


def _child_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("COV_CORE_", "COVERAGE_", "PYTEST_", "PLASTICOS_"))}
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    # Avoid host site startup instrumentation in nested stdlib/pytest probes.
    env["PYTHONPATH"] = str(Path(pytest.__file__).resolve().parent.parent)
    return env


def _kernel(tmp_path: Path, document: dict) -> subprocess.CompletedProcess[str]:
    root = tmp_path / "kernel-probe"
    (root / "ci").mkdir(parents=True, exist_ok=True)
    (root / ".github/workflows").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "ci/check_github_actions_kernel.sh", root / "ci/check_github_actions_kernel.sh")
    (root / ".github/workflows/ci.yml").write_text(yaml.safe_dump(document, sort_keys=False))
    binary = root / "bin"
    binary.mkdir(exist_ok=True)
    python = binary / "python3"
    python.write_text(f'#!/bin/sh\nexec "{sys.executable}" -S "$@"\n')
    python.chmod(0o755)
    env = _child_env()
    env["PATH"] = str(binary) + os.pathsep + os.environ["PATH"]
    return subprocess.run(
        ["bash", "ci/check_github_actions_kernel.sh"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )


def _test_step(doc: dict) -> dict:
    return next(step for step in doc["jobs"]["pure-python-tests"]["steps"] if step.get("id") == "pure-tests")


def test_current_workflow_is_accepted_by_the_real_kernel(tmp_path: Path) -> None:
    result = _kernel(tmp_path, _workflow())
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "event_change",
    [
        {"push": None},
        {"push": {"branches": ["**"]}},
        {"push": {"branches": ["Staging"]}},
        {"pull_request": {"paths": ["scripts/**"]}},
        {"pull_request": {"types": ["opened"]}},
    ],
)
def test_wrong_ci_event_selection_fails_even_if_correct_words_exist(tmp_path: Path, event_change: dict) -> None:
    doc = _workflow()
    doc["on"].update(event_change)
    # A textual scanner can be fooled by an unrelated occurrence; YAML semantics cannot.
    doc["env"] = {"DOCUMENTATION_ONLY": "branches: [Staging, Production]"}
    result = _kernel(tmp_path, doc)
    assert result.returncode != 0, "CI_EVENTS: incorrect event routing passed the real validator"


@pytest.mark.parametrize(
    "mutation",
    [
        "skip_job",
        "skip_step",
        "skip_job_boolean",
        "skip_step_boolean",
        "mask_job",
        "mask_step",
        "remove_marker_env",
        "override_marker_env",
        "filter_tests",
        "ignore_file",
        "mask_exit",
        "duplicate_pytest",
        "drop_report",
        "missing_job",
        "drop_aggregator_dependency",
        "env_selection",
    ],
)
def test_weakened_ci_contract_is_rejected(tmp_path: Path, mutation: str) -> None:
    doc = _workflow()
    job = doc["jobs"]["pure-python-tests"]
    step = _test_step(doc)
    if mutation == "skip_job":
        job["if"] = "false"
    elif mutation == "skip_step":
        step["if"] = "false"
    elif mutation == "skip_job_boolean":
        job["if"] = False
    elif mutation == "skip_step_boolean":
        step["if"] = False
    elif mutation == "mask_job":
        job["continue-on-error"] = True
    elif mutation == "mask_step":
        step["continue-on-error"] = True
    elif mutation == "remove_marker_env":
        job["env"].pop("PLASTICOS_CONTRACT_CI")
    elif mutation == "override_marker_env":
        step["env"] = {"PLASTICOS_CONTRACT_CI": "0"}
    elif mutation == "filter_tests":
        step["run"] += " -k happy_path\n"
    elif mutation == "ignore_file":
        step["run"] += " --ignore=tests/test_install_smoke_evidence.py\n"
    elif mutation == "mask_exit":
        step["run"] += " || true\n"
    elif mutation == "duplicate_pytest":
        job["steps"].append({"run": "python3 -m pytest tests/"})
    elif mutation == "drop_report":
        job["steps"] = [s for s in job["steps"] if not str(s.get("uses", "")).startswith("actions/upload-artifact@")]
    elif mutation == "missing_job":
        doc["jobs"].pop("secret-scan")
    elif mutation == "drop_aggregator_dependency":
        doc["jobs"]["ci-gate-result"]["needs"].remove("secret-scan")
    elif mutation == "env_selection":
        job["env"]["PYTEST_ADDOPTS"] = "--ignore=tests"
    result = _kernel(tmp_path, doc)
    assert result.returncode != 0, f"CI_INTEGRITY: mutation {mutation} survived"


@pytest.mark.parametrize("attack", ["comment_only", "inert_failure", "premature_success"])
def test_aggregator_must_actually_fail_closed(tmp_path: Path, attack: str) -> None:
    doc = _workflow()
    required = ("lint", "static-checks", "pure-python-tests", "gate-sdk-tests", "secret-scan", "audit-baseline")
    aggregator = doc["jobs"]["ci-gate-result"]["steps"][0]
    if attack == "comment_only":
        aggregator["run"] = (
            "# "
            + " ".join(f"needs.{job}.result != success" for job in required)
            + "\n# exit 1\necho weak gate\nexit 0\n"
        )
    elif attack == "inert_failure":
        aggregator["run"] = (
            "echo '" + " ".join(f"needs.{job}.result != success" for job in required) + " exit 1'\nexit 0\n"
        )
    else:
        aggregator["run"] = "exit 0\n" + aggregator["run"]
    result = _kernel(tmp_path, doc)
    assert result.returncode != 0, f"AGGREGATOR_BYPASS: {attack} survived real kernel"


def _probe_pytest(
    tmp_path: Path, body: str, *, ci: bool, args: tuple[str, ...] = ()
) -> subprocess.CompletedProcess[str]:
    root = tmp_path / "pytest-probe"
    root.mkdir()
    shutil.copyfile(ROOT / "tests/conftest.py", root / "conftest.py")
    (root / "pytest.ini").write_text("[pytest]\n")
    (root / "test_probe.py").write_text(body)
    env = _child_env()
    env["PLASTICOS_CONTRACT_CI"] = "1" if ci else "0"
    return subprocess.run(
        [sys.executable, "-S", "-m", "pytest", str(root), "-q", *args],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )


@pytest.mark.parametrize("action", ["pytest.skip('missing dependency')", "pytest.xfail('known bug')"])
def test_a_required_contract_cannot_skip_or_xfail(tmp_path: Path, action: str) -> None:
    body = f"import pytest\n@pytest.mark.adversarial_contract\ndef test_contract():\n    {action}\n"
    result = _probe_pytest(tmp_path, body, ci=True)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "skip/xfail is not proof" in result.stdout


def test_an_unexpected_pass_marked_xfail_is_not_contract_proof(tmp_path: Path) -> None:
    body = (
        "import pytest\n@pytest.mark.adversarial_contract\n@pytest.mark.xfail\ndef test_contract():\n    assert True\n"
    )
    result = _probe_pytest(tmp_path, body, ci=True)
    assert result.returncode == 1, result.stdout + result.stderr


def test_zero_collected_contracts_does_not_make_ci_green(tmp_path: Path) -> None:
    result = _probe_pytest(tmp_path, "def test_unrelated():\n    assert True\n", ci=True)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Mandatory contract coverage incomplete" in result.stdout


def test_required_contracts_run_once_and_optional_skips_stay_optional(tmp_path: Path) -> None:
    body = (
        "import pytest\n@pytest.mark.adversarial_contract\ndef test_contract():\n    assert True\n"
        "def test_optional():\n    pytest.skip('different runtime tier')\n"
    )
    result = _probe_pytest(tmp_path, body, ci=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed, 1 skipped" in result.stdout


def test_ci_cannot_filter_out_the_contract_tier(tmp_path: Path) -> None:
    body = "import pytest\n@pytest.mark.adversarial_contract\ndef test_contract():\n    assert True\n"
    result = _probe_pytest(tmp_path, body, ci=True, args=("-k", "unrelated"))
    assert result.returncode != 0
    assert "may not narrow" in result.stderr + result.stdout


def test_local_focused_test_selection_remains_supported(tmp_path: Path) -> None:
    body = "import pytest\n@pytest.mark.adversarial_contract\ndef test_contract():\n    assert True\n"
    result = _probe_pytest(tmp_path, body, ci=False, args=("-k", "contract"))
    assert result.returncode == 0, result.stdout + result.stderr


# Structural trigger checks from #262. Comments are stripped and only the
# effective keys under the top-level ``on:`` and ``jobs:`` mappings are
# inspected, so a matching string in a comment or a run script proves nothing.
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

PUSH_BRANCHES = {"Staging", "Production"}
PHASE_ONE_JOBS = ("lint", "static-checks", "pure-python-tests", "gate-sdk-tests", "secret-scan", "audit-baseline")
AGGREGATOR_JOB = "ci-gate-result"

_COMMENT = re.compile(r"(^|\s)#.*$")
_KEY = re.compile(r"^(?P<indent> *)(?P<key>[A-Za-z0-9_.-]+):(?:\s+(?P<value>.*))?$")


def _lines(text: str) -> list[str]:
    return [_COMMENT.sub("", line).rstrip() for line in text.splitlines()]


def _mapping(lines: list[str], indent: int) -> dict[str, tuple[str | None, list[str]]]:
    """Keys at exactly ``indent`` -> (inline value, child lines). Duplicate keys fail."""
    result: dict[str, tuple[str | None, list[str]]] = {}
    current: list[str] | None = None
    for line in lines:
        if not line.strip():
            continue
        match = _KEY.match(line)
        if match and len(match["indent"]) == indent:
            key = match["key"]
            assert key not in result, f"duplicate key {key!r} at indent {indent}"
            current = []
            result[key] = (match["value"] or None, current)
        elif len(line) - len(line.lstrip(" ")) > indent and current is not None:
            current.append(line)
        else:
            current = None
    return result


def _list(value: str | None, children: list[str]) -> list[str] | None:
    """A flow list (``[a, b]``) or block list (``- a``); None when neither."""
    if value:
        flow = re.fullmatch(r"\[(.*)\]", value.strip())
        if not flow:
            return None
        return [item.strip().strip("'\"") for item in flow[1].split(",") if item.strip()]
    items = [line.strip() for line in children if line.strip()]
    if not items or not all(item.startswith("- ") for item in items):
        return None
    return [item[2:].strip().strip("'\"") for item in items]


def _trigger_violations(text: str) -> list[str]:
    top = _mapping(_lines(text), 0)
    if "on" not in top:
        return ["no top-level on: mapping"]
    on_value, on_children = top["on"]
    if on_value:
        return [f"on: is inline ({on_value!r}); push has no branch filter"]
    events = _mapping(on_children, 2)
    problems: list[str] = []

    if "push" not in events:
        problems.append("on.push is missing")
    else:
        push_value, push_children = events["push"]
        push = _mapping(push_children, 4) if not push_value else {}
        if "branches" not in push:
            problems.append("on.push has no branches filter (feature-branch pushes would start CI)")
        else:
            branches = _list(*push["branches"])
            if branches is None or set(branches) != PUSH_BRANCHES:
                problems.append(f"on.push.branches is {branches!r}, expected exactly {sorted(PUSH_BRANCHES)}")
        for key in sorted(set(push) & {"branches-ignore", "tags", "tags-ignore"}):
            problems.append(f"on.push.{key} widens the push trigger")

    if "pull_request" not in events:
        problems.append("on.pull_request is missing")
    else:
        pr_value, pr_children = events["pull_request"]
        restricted = set(_mapping(pr_children, 4)) & {"branches", "branches-ignore"}
        if pr_value or restricted:
            problems.append("on.pull_request is branch-restricted; PRs to every target must be validated")

    if "workflow_dispatch" not in events:
        problems.append("on.workflow_dispatch is missing (repo-index bot PRs dispatch this gate)")
    return problems


def _job_violations(text: str) -> list[str]:
    top = _mapping(_lines(text), 0)
    if "jobs" not in top:
        return ["no top-level jobs: mapping"]
    jobs = {job_id: _mapping(children, 4) for job_id, (_, children) in _mapping(top["jobs"][1], 2).items()}
    problems = [f"job {job_id} is missing" for job_id in (*PHASE_ONE_JOBS, AGGREGATOR_JOB) if job_id not in jobs]
    problems += [
        f"{job_id} has needs: (Phase 1 must stay parallel)"
        for job_id in PHASE_ONE_JOBS
        if "needs" in jobs.get(job_id, {})
    ]
    gate = jobs.get(AGGREGATOR_JOB)
    if gate is not None:
        if gate.get("name", (None,))[0] != "CI Gate Result":
            problems.append("ci-gate-result must keep the required-check name 'CI Gate Result'")
        if gate.get("if", (None,))[0] != "always()":
            problems.append("ci-gate-result must run if: always()")
        needs = _list(*gate["needs"]) if "needs" in gate else None
        if needs is None or not set(PHASE_ONE_JOBS) <= set(needs):
            problems.append(f"ci-gate-result needs {needs!r}, must cover {list(PHASE_ONE_JOBS)}")
    return problems


def test_feature_branch_pushes_do_not_start_a_second_ci_gate() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert _trigger_violations(text) == []
    assert _job_violations(text) == []


# Each mutant is derived from the real workflow, so the check is proven against
# the file it guards. The first is the audit's F262-1 probe: push unfiltered
# while the expected filter text survives as a comment.
_PUSH_FILTER = "  push:\n    branches: [Staging, Production]\n"
_MUTANTS = {
    "unfiltered_push_with_filter_in_comment": (
        _PUSH_FILTER,
        "  push:\n    # branches: [Staging, Production]\n",
    ),
    "filter_moved_to_pull_request": (
        _PUSH_FILTER + "  pull_request:\n",
        "  push:\n  pull_request:\n    branches: [Staging, Production]\n",
    ),
    "feature_branches_added": (_PUSH_FILTER, "  push:\n    branches: [Staging, Production, 'feat/**']\n"),
    "push_widened_by_tags": (_PUSH_FILTER, _PUSH_FILTER + "    tags: ['v*']\n"),
    "pull_request_removed": ("  pull_request:\n", ""),
    "workflow_dispatch_removed": ("  workflow_dispatch:\n", ""),
}


@pytest.mark.parametrize("mutant", sorted(_MUTANTS))
def test_trigger_check_rejects_broken_event_routing(mutant: str) -> None:
    original, replacement = _MUTANTS[mutant]
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert text.count(original) == 1, f"mutant {mutant} no longer matches ci.yml; update the fixture"
    assert _trigger_violations(text.replace(original, replacement)) != []
