"""Behavioral contracts for CI routing, full test reachability and skip enforcement."""

from __future__ import annotations

import os
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
