#!/usr/bin/env python3
"""PR-fast pure-Python lane: mandatory contracts, then a proven non-marker set.

The full ``pytest tests/`` command is not constructed here. A second pytest
invocation receives only explicit test modules and ``-m 'not adversarial_contract'``.
Unknown scope fails the process after the mandatory contracts have run.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_scope():
    spec = importlib.util.spec_from_file_location("ci_pr_fast_scope", Path(__file__).with_name("pr_fast_scope.py"))
    if spec is None or spec.loader is None:
        raise SystemExit("pr_fast scope module is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SCOPE = _load_scope()
classify = _SCOPE.classify
missing_mandatory_markers = _SCOPE.missing_mandatory_markers
parse_name_status = _SCOPE.parse_name_status

MANDATORY_PYTEST = [
    "python3",
    "-m",
    "pytest",
    "tests/",
    "-m",
    "adversarial_contract",
    "-v",
    "--cov=.",
    "--cov-report=term-missing:skip-covered",
    "--junitxml=artifacts/pytest/pr-fast-contracts.xml",
]

_ARTIFACTS = Path("artifacts/pytest")
_FORBIDDEN_ENV = ("PYTEST_ADDOPTS", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "PLASTICOS_SMOKE_SOURCE")
_ZERO_SHA = "0" * 40


def scoped_pytest(modules: list[str]) -> list[str]:
    """Argv for the non-marker lane. Modules are paths, never a shell string."""
    if not modules:
        raise SystemExit("scoped pytest requires at least one module")
    for module in modules:
        path = Path(module)
        if (
            path.is_absolute()
            or ".." in path.parts
            or module.startswith("-")
            or not module.startswith("tests/")
            or not module.endswith(".py")
            or not path.name.startswith("test_")
        ):
            raise SystemExit(f"scoped module refused: {module}")
    return [
        "python3",
        "-m",
        "pytest",
        *modules,
        "-m",
        "not adversarial_contract",
        "-v",
        "--junitxml=artifacts/pytest/pr-fast-scoped.xml",
    ]


def refuse_environment() -> None:
    for key in _FORBIDDEN_ENV:
        if os.environ.get(key):
            raise SystemExit(f"pr_fast refused {key}")
    if os.environ.get("PLASTICOS_CONTRACT_CI") != "1":
        raise SystemExit("pr_fast requires PLASTICOS_CONTRACT_CI=1")
    if os.environ.get("PLASTICOS_CI_TIER") != "pr_fast":
        raise SystemExit("pr_fast requires PLASTICOS_CI_TIER=pr_fast")


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"pr_fast cannot read HEAD: {exc}") from exc


def resolve_range(head: str) -> tuple[str, str]:
    """Return ``(base, head)`` for the committed range, or exit on an unusable range."""
    declared = os.environ.get("SCOPE_HEAD_SHA", "")
    if declared and declared != head:
        raise SystemExit("pr_fast declared head does not match the checkout")
    github_sha = os.environ.get("GITHUB_SHA", "")
    if github_sha and github_sha != head:
        raise SystemExit("pr_fast github.sha does not match the checkout")
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    base = os.environ.get("SCOPE_BASE_SHA", "").strip()
    if base == _ZERO_SHA:
        raise SystemExit("pr_fast base SHA is the empty GitHub before value")
    if _sha(base):
        return base, head
    if event == "workflow_dispatch":
        parent = _parent(head)
        if parent:
            return parent, head
    raise SystemExit(f"pr_fast cannot prove a base SHA for event {event or '(missing)'}")


#: Paths whose patch text the selector reads: the harness conftest, and workflows,
#: which count as toolchain manifests only when the change is limited to tool installs.
_PATCHED_PATHS = ("tests/conftest.py", ".github/workflows/")


def split_patch(text: str) -> dict[str, str]:
    """Split a ``git diff`` into one patch per destination path."""
    patches: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text.splitlines():
        if line.startswith("diff --git "):
            path = line.rsplit(" b/", 1)[-1]
            current = patches.setdefault(path, [])
        if current is not None:
            current.append(line)
    return {path: "\n".join(lines) + "\n" for path, lines in patches.items()}


def load_diff(base: str, head: str) -> tuple[list[tuple[str, str, str | None]] | None, dict[str, str]]:
    if not _exists(base) or not _exists(head):
        return None, {}
    try:
        listed = subprocess.check_output(
            ["git", "diff", "--name-status", "-M", base, head],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        patch = subprocess.check_output(
            ["git", "diff", "-U0", base, head, "--", *_PATCHED_PATHS],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None, {}
    return parse_name_status(listed), split_patch(patch)


def write_record(head: str, base: str, receipt: dict, mandatory_code: int, scoped_code: int | None) -> None:
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)
    record = {
        "event": os.environ.get("GITHUB_EVENT_NAME", ""),
        "source_head_sha": os.environ.get("SCOPE_HEAD_SHA", head),
        "base_sha": base,
        "tested_checkout_sha": head,
        "github_sha": os.environ.get("GITHUB_SHA", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "tier": "pr_fast",
        "mandatory_exit": mandatory_code,
        "scoped_exit": scoped_code,
        "scope": receipt,
    }
    (_ARTIFACTS / "revision.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    (_ARTIFACTS / "pr-fast-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def main(launch=subprocess.call, head: str | None = None) -> int:
    refuse_environment()
    observed = head if head is not None else git_head()
    code = int(launch(MANDATORY_PYTEST))
    base = ""
    try:
        base, resolved_head = resolve_range(observed)
    except SystemExit as exc:
        receipt = classify(None, ROOT, observed_head=observed, declared_head=observed)
        receipt["reason"] = str(exc)
        receipt["status"] = "unknown"
        write_record(observed, "", receipt, code, None)
        return code or 1
    parsed, split = load_diff(base, resolved_head)
    patches: dict[str, str] | None
    if parsed is None:
        patches = None
    else:
        changed = _changed_paths(parsed)
        patches = {path: text for path, text in split.items() if path in changed}
    receipt = classify(
        parsed,
        ROOT,
        patches=patches,
        base_sha=base,
        declared_head=resolved_head,
        observed_head=observed,
    )
    missing = missing_mandatory_markers(ROOT)
    if missing:
        receipt["status"] = "unknown"
        receipt["reason"] = "mandatory adversarial marker missing: " + ", ".join(missing)
        receipt["unknown_paths"] = missing
    modules = list(receipt["scoped_nonmarker_tests"])
    scoped_code: int | None = None
    if code == 0 and receipt["status"] != "unknown" and modules:
        scoped_code = int(launch(scoped_pytest(modules)))
    write_record(observed, base, receipt, code, scoped_code)
    if code != 0 or receipt["status"] == "unknown":
        return code or 1
    return 0 if scoped_code is None else scoped_code


def _changed_paths(entries: list[tuple[str, str, str | None]]) -> set[str]:
    found = set()
    for _code, path, new_path in entries:
        found.add(path)
        if new_path:
            found.add(new_path)
    return found


def _sha(value: str) -> bool:
    return len(value) == 40 and all(char in "0123456789abcdef" for char in value) and value != _ZERO_SHA


def _exists(sha: str) -> bool:
    completed = subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], check=False, capture_output=True)
    return completed.returncode == 0


def _parent(head: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{head}^"],
        check=False,
        capture_output=True,
        text=True,
    )
    parent = completed.stdout.strip()
    if completed.returncode != 0 or not _sha(parent):
        return ""
    parents = subprocess.run(
        ["git", "rev-list", "--parents", "-n", "1", head],
        check=False,
        capture_output=True,
        text=True,
    )
    tokens = parents.stdout.split()
    if len(tokens) != 2:
        return ""
    return parent


if __name__ == "__main__":
    sys.exit(main())
