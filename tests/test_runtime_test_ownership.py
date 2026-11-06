"""Odoo runtime tests have two owners: the make pr-check smoke stage and an invoked l9-pr-integration-testing.

`make test-module` / `make test-odoo` are reached only through `make runtime-test`.
The smoke stage (`scripts/pr_check_run.sh`) is the only script that builds that
goal, and every instruction surface that used to tell an agent to run the
runtime targets ad hoc now names the two owners instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

OWNERSHIP = (
    "Odoo runtime tests (`make test-module` / `make test-odoo`) run only in the `make pr-check` smoke stage "
    "or when `l9-pr-integration-testing` is invoked (`make runtime-test m=<modules>`). Do not run them ad hoc."
)

# Surfaces that carry the ownership sentence verbatim.
SENTENCE_SURFACES = [
    "skills/plasticos-odoo-docker-testing/SKILL.md",
    "skills/plasticos-odoo-docker-testing/references/test-odoo-protocol.md",
    ".cursor/rules/00-plasticos-master-context.mdc",
    ".cursor/rules/36-plasticos-docker-test-fixture.mdc",
    ".cursor/rules/86-ci-github-actions.mdc",
    ".claude/rules/testing.md",
    "skills/plasticos-odoo-sh-deploy/references/ssh-diagnose.md",
]

# Every instruction surface that names the runtime targets.
INSTRUCTION_SURFACES = [
    *SENTENCE_SURFACES,
    ".cursor/rules/30-plasticos-deploy-validation.mdc",
    ".cursor/rules/40-plasticos-zero-stub-law.mdc",
    ".cursor/rules/50-plasticos-web-lead-guard.mdc",
    ".cursor/rules/80-plasticos-testing-rules.mdc",
    ".cursor/rules/88-plasticos-odoo-python-tooling.mdc",
    "tests/README.md",
    "docs/plasticos_prompt_pack/00_master_space_prompt.md",
]

# `make test-odoo-local` is the no-Docker backend, a different target.
AD_HOC = re.compile(r"make (?:test-module|test-odoo)(?!-)")
# A make invocation whose goal is runtime-test (`make runtime-test`, `"${MAKE}" ... runtime-test`).
BUILDS_RUNTIME_TEST = re.compile(r"(?:\bmake|\$\{?MAKE\}?\"?)(?:\s+-\S+)*\s+runtime-test\b")


def _target_body(makefile: str, target: str) -> str:
    match = re.search(rf"^{re.escape(target)}:.*?(?=^\S|\Z)", makefile, flags=re.M | re.S)
    assert match, f"Makefile has no {target} target"
    return match.group(0)


def test_runtime_test_dispatches_only_to_the_existing_recipes() -> None:
    body = _target_body((ROOT / "Makefile").read_text(), "runtime-test")
    assert "$(MAKE) --no-print-directory test-odoo" in body
    assert '$(MAKE) --no-print-directory test-module m="$$mods"' in body
    assert "RUNTIME_MODULES" in body and "$(m)" in body
    assert "docker" not in body and "test_env.sh" not in body, "runtime-test owns no runner of its own"


def test_only_the_smoke_stage_builds_runtime_test() -> None:
    callers = sorted(
        path.relative_to(ROOT).as_posix()
        for folder in ("scripts", "ci", ".github")
        for path in (ROOT / folder).rglob("*")
        if path.is_file()
        and path.suffix in {".sh", ".py", ".yml", ".yaml"}
        and BUILDS_RUNTIME_TEST.search(path.read_text())
    )
    assert callers == ["scripts/pr_check_run.sh"], callers
    run = (ROOT / "scripts/pr_check_run.sh").read_text()
    fast = run.split("full | pr-check)", 1)[0]
    assert 'maybe_runtime_tests "$scope_runtime"' in run.split("full | pr-check)", 1)[1]
    assert 'maybe_runtime_tests "' not in fast, "fast mode never runs the Odoo runtime"


def test_no_script_calls_the_runtime_targets_directly() -> None:
    offenders = sorted(
        path.relative_to(ROOT).as_posix()
        for folder in ("scripts", "ci", ".github")
        for path in (ROOT / folder).rglob("*")
        if path.is_file() and path.suffix in {".sh", ".py", ".yml", ".yaml"}
        for line in path.read_text().splitlines()
        if AD_HOC.search(line) and not line.lstrip().startswith("#")
    )
    assert offenders == [], offenders


@pytest.mark.parametrize("rel", SENTENCE_SURFACES)
def test_surface_states_the_two_owners(rel: str) -> None:
    assert OWNERSHIP in (ROOT / rel).read_text(), rel


@pytest.mark.parametrize("rel", INSTRUCTION_SURFACES)
def test_surface_has_no_ad_hoc_run_instruction(rel: str) -> None:
    bad = [
        line
        for line in (ROOT / rel).read_text().splitlines()
        if AD_HOC.search(line) and "runtime-test" not in line and "smoke stage" not in line
    ]
    assert bad == [], f"{rel}: {bad}"


def test_agents_md_records_the_owners() -> None:
    agents = (ROOT / "AGENTS.md").read_text()
    tail = " ".join(agents[agents.rindex("2026-11-06 correction") :].replace("\n> ", " ").split())
    assert "make runtime-test" in tail and "l9-pr-integration-testing" in tail and "smoke stage" in tail
