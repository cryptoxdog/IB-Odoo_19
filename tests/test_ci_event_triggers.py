"""CI Gate runs once per relevant event.

The pure-Python job has no PyYAML, so the workflow is read structurally from
its own indentation: comments are stripped and only the effective keys under
the top-level ``on:`` and ``jobs:`` mappings are inspected. A matching string
anywhere else in the file (a comment, a run script) proves nothing.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
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
