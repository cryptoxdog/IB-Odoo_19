"""Every lock-owned tool pin in this repository equals Core's toolchain lock.

The organization's tool versions are owned by `Quantum-L9/l9-ci-core`
(`.github/actions/install-consumer-ci/toolchain-lock.json`). This repository is
an Odoo addon suite with no `[project]` table and no `uv.lock` (AGENTS.md,
`.cursor/rules/88`), so it cannot let the lock drive one resolver. Instead it
keeps a byte copy of that file, `ci/core-toolchain-lock.json`, with its Core
commit in `ci/core-toolchain-lock.provenance.json`, and pins the lock's
versions at each site that installs a tool. This module is what makes the copy
the single source: any site that differs from it, or installs a lock-owned
tool unpinned, fails here and is named.

Refresh: replace the copy with Core's file at a newer commit, record the
commit, and run this module. It lists every site that must follow.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

# Mandatory PR-fast lane: a PR that changes only a workflow pin is routed through
# COVERED_BY_MANDATORY and never structurally selects this module, so the guard
# must run on every pull request rather than only when it is selected.
pytestmark = pytest.mark.adversarial_contract

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "ci" / "core-toolchain-lock.json"
PROVENANCE_PATH = ROOT / "ci" / "core-toolchain-lock.provenance.json"
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

#: Lock-owned tools that are installed with pip at some site in this repository.
PIP_INSTALLED = ("ruff", "mypy", "pytest", "semgrep", "pre-commit", "pip", "bandit", "pip-audit")


@pytest.fixture(scope="module")
def lock() -> dict[str, str]:
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def _python_minor(lock: dict[str, str]) -> str:
    return ".".join(lock["python"].split(".")[:2])


def _pins(text: str) -> dict[str, list[str]]:
    """`name==version` pins found in requirement or install text, by name."""

    found: dict[str, list[str]] = {}
    for name, version in re.findall(r"(?<![\w.-])([A-Za-z][\w.-]*)==([\w.]+)", text):
        found.setdefault(name.lower(), []).append(version)
    return found


def test_lock_copy_is_well_formed_and_traceable(lock) -> None:
    for tool in (*PIP_INSTALLED, "python", "gitleaks"):
        assert re.fullmatch(r"\d+\.\d+\.\d+", lock[tool]), tool
    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    assert provenance["repository"] == "Quantum-L9/l9-ci-core"
    assert provenance["path"] == ".github/actions/install-consumer-ci/toolchain-lock.json"
    assert re.fullmatch(r"[0-9a-f]{40}", provenance["commit"])


@pytest.mark.parametrize(
    ("relative", "tools"),
    [
        ("requirements-dev.txt", ("ruff", "mypy", "pytest", "semgrep", "pre-commit")),
        ("requirements-ci.txt", ("pytest",)),
    ],
)
def test_requirement_files_pin_the_lock(lock, relative, tools) -> None:
    text = (ROOT / relative).read_text(encoding="utf-8")
    pins = _pins(text)
    for tool in tools:
        assert pins.get(tool) == [lock[tool]], f"{relative}: {tool} must be =={lock[tool]}"
    # Any other lock-owned tool the file names must carry the exact lock pin too.
    for line in text.splitlines():
        requirement = line.split("#", 1)[0].strip()
        name = re.split(r"[\s<>=!~;\[@]", requirement, maxsplit=1)[0].lower()
        if name in PIP_INSTALLED:
            assert requirement.replace(" ", "") == f"{name}=={lock[name]}", f"{relative}: {requirement!r}"


def test_pyproject_follows_the_lock(lock) -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'required-version = "=={lock["ruff"]}"' in text
    minor = _python_minor(lock)
    assert f'target-version = "py{minor.replace(".", "")}"' in text
    assert f'python_version = "{minor}"' in text


def test_pre_commit_hook_revs_follow_the_lock(lock) -> None:
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    revs = {repo["repo"]: repo.get("rev") for repo in config["repos"]}
    assert revs["https://github.com/astral-sh/ruff-pre-commit"] == f"v{lock['ruff']}"
    assert revs["https://github.com/pre-commit/mirrors-mypy"] == f"v{lock['mypy']}"


def test_makefile_pins_pip(lock) -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert makefile.count(f"pip install --quiet pip=={lock['pip']}") == 2  # make venv, make lock-deps
    assert "--upgrade pip" not in makefile


def _install_lines(path: Path) -> list[str]:
    """Whole ``pip install`` commands, with backslash continuations joined."""
    joined = re.sub(r"\\\n\s*", " ", path.read_text(encoding="utf-8"))
    return [line for line in joined.splitlines() if re.search(r"\bpip install\b", line)]


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_workflow_installs_pin_the_lock(lock, workflow) -> None:
    for line in _install_lines(workflow):
        packages = line.split("pip install", 1)[1]
        pins = _pins(packages)
        for tool in PIP_INSTALLED:
            for version in pins.get(tool, []):
                assert version == lock[tool], f"{workflow.name}: {tool}=={version}, lock is {lock[tool]}"
            bare = re.search(rf"(?<![\w.=-]){re.escape(tool)}(?![\w.=-])", packages)
            assert not bare, f"{workflow.name}: {tool} installed without the lock pin: {line.strip()}"


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_workflow_python_is_the_locked_minor(lock, workflow) -> None:
    for version in re.findall(r"python-version:\s*[\"']?([\d.]+)", workflow.read_text(encoding="utf-8")):
        assert version == _python_minor(lock), f"{workflow.name}: python-version {version}"


def test_gitleaks_action_runs_the_locked_gitleaks(lock) -> None:
    ci = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    steps = [step for job in ci["jobs"].values() for step in job.get("steps", [])]
    gitleaks = [step for step in steps if str(step.get("uses", "")).startswith("gitleaks/gitleaks-action@")]
    assert gitleaks
    for step in gitleaks:
        assert step["env"]["GITLEAKS_VERSION"] == lock["gitleaks"]
