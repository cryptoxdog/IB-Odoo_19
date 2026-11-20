#!/usr/bin/env python3
"""Scope the local pre-push gate to what the branch changed.

``make pr-check`` asks this owner, once, which collectors the change set can
reach. Everything else is skipped on this machine. GitHub ``ci.yml`` runs the
PR-fast pure-Python lane and stays the merge verdict; the unfiltered Odoo-free
suite runs from the Staging nightly workflow, not from this local selector.

Usage::

    python3 scripts/pr_check_scope.py --base Staging [--receipt PATH] [--root DIR]

Prints ``KEY=VALUE`` lines::

    changed=<count>
    audit=0|1      static collectors (make audit + audit-baseline) when any
                   non-documentation path changed
    smoke=0|1      Odoo install-smoke when an addon load input or an installer
                   input changed
    tests=all | <space-separated test modules> | (empty: no module to run)
    runtime=all | <comma-separated PlasticOS modules> | (empty)
                   Odoo runtime tests (the runtime-test goal) for the declared
                   roster modules the change touched that ship a tests/
                   package; ``all`` when the whole gate is kept
    reason=<one line>

The change set is the committed range from the merge-base with
``origin/<base>`` plus the working tree and untracked files. Every doubt —
no base, no merge-base, no change, a selector error, ``PR_CHECK_SCOPE=full`` —
keeps the whole gate (``audit=1 smoke=1 tests=all runtime=all``).

Test selection: a changed test module selects itself. Any changed path also
selects a test module whose source contains that repo-relative path, the same
path with its suffix removed, or, for Python, the dotted module. A bare
filename stem, an addon directory name, a quoted top-level directory, and a
``plasticos_*`` tree walk do not select a test. A harness change
(``tests/conftest.py``, ``tests/common.py``, ``tests/__init__.py``,
``pyproject.toml``, ``constraints.txt``, or ``requirements*.txt``)
selects everything.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ADDON_PREFIX = "plasticos_"
# Documentation: nothing a collector reads. requirements*.txt and constraints.txt
# are dependency inputs, not documentation, so .txt is deliberately not here.
# Python under docs/ is executable source (campaign importers), not documentation.
DOCS_RE = re.compile(r"^docs/|\.(md|rst)$")
INSTALLER_RE = re.compile(
    r"^(Dockerfile[^/]*|docker-compose[^/]*\.ya?ml|config/.*|requirements[^/]*\.txt|constraints\.txt"
    r"|scripts/install_smoke\.sh|scripts/get_odoo_module_order\.py)$"
)
HARNESS = {"tests/conftest.py", "tests/common.py", "tests/__init__.py", "pyproject.toml", "constraints.txt"}
HARNESS_RE = re.compile(r"^requirements[^/]*\.txt$")


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def changed_paths(root: Path, base: str) -> list[str] | None:
    """Repository-relative changed paths, or None when they cannot be determined."""
    try:
        _git(root, "fetch", "-q", "origin", base)
        merge_base = _git(root, "merge-base", f"origin/{base}", "HEAD").strip()
        listed = (
            _git(root, "diff", "--name-only", f"{merge_base}..HEAD")
            + _git(root, "diff", "--name-only", "HEAD")
            + _git(root, "ls-files", "--others", "--exclude-standard")
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return sorted({line for line in listed.split("\n") if line})


def is_docs(rel: str) -> bool:
    return bool(DOCS_RE.search(rel)) and not rel.endswith(".py")


def is_smoke_input(rel: str) -> bool:
    parts = Path(rel).parts
    if parts[0].startswith(ADDON_PREFIX):
        return not is_docs(rel) and "tests" not in parts[1:]
    return bool(INSTALLER_RE.match(rel))


def tokens_for(rel: str) -> set[str]:
    path = Path(rel)
    found = {rel}
    if path.suffix:
        found.add(rel[: -len(path.suffix)])
    if path.suffix == ".py":
        found.add(".".join((*path.parts[:-1], path.stem)))
    return {t for t in found if t not in {"__init__", "__manifest__"}}


def _word_pattern(tokens: set[str]) -> re.Pattern[str]:
    escaped = sorted((re.escape(t) for t in tokens), key=len, reverse=True)
    return re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(escaped) + r")(?![A-Za-z0-9_])")


def select_tests(root: Path, changed: list[str]) -> list[str] | str:
    if any(rel in HARNESS or HARNESS_RE.match(rel) for rel in changed):
        return "ALL"
    selected: set[str] = set()
    tokens: set[str] = set()
    for rel in changed:
        parts = Path(rel).parts
        if parts[0] == "tests" and parts[-1].startswith("test_") and rel.endswith(".py") and (root / rel).is_file():
            selected.add(rel)
        tokens |= tokens_for(rel)
    word = _word_pattern(tokens) if tokens else None
    for module in sorted((root / "tests").rglob("test_*.py")):
        rel = module.relative_to(root).as_posix()
        if rel in selected:
            continue
        if word and word.search(module.read_text(encoding="utf-8", errors="replace")):
            selected.add(rel)
    return sorted(selected)


def runtime_roster(root: Path) -> list[str] | None:
    """The declared PlasticOS roster ``scripts/test_env.sh`` accepts as a test scope."""
    try:
        out = subprocess.run(
            [sys.executable, str(root / "scripts" / "get_odoo_module_order.py")],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [m for m in out.strip().split(",") if m]


def select_runtime(root: Path, changed: list[str]) -> str:
    """Comma list of roster modules the change touched that ship Odoo tests.

    A module outside the roster is refused by the runner, and a module with no
    ``tests`` package would make it fail on zero tests, so both are dropped.
    Documentation inside an addon does not select it. An unreadable roster
    keeps the whole runtime gate.
    """
    touched = {
        Path(rel).parts[0] for rel in changed if Path(rel).parts[0].startswith(ADDON_PREFIX) and not is_docs(rel)
    }
    if not touched:
        return ""
    roster = runtime_roster(root)
    if roster is None:
        return "all"
    return ",".join(m for m in roster if m in touched and (root / m / "tests" / "__init__.py").is_file())


def plan(root: Path, base: str) -> dict:
    whole = {"audit": 1, "smoke": 1, "tests": "all", "runtime": "all"}
    if os.environ.get("PR_CHECK_SCOPE") == "full":
        return {"changed": None, **whole, "reason": "forced by PR_CHECK_SCOPE=full"}
    changed = changed_paths(root, base)
    if changed is None:
        return {"changed": None, **whole, "reason": f"change set against origin/{base} unknown"}
    if not changed:
        return {"changed": [], **whole, "reason": f"no change against origin/{base}"}
    tests = select_tests(root, changed)
    return {
        "changed": changed,
        "audit": int(any(not is_docs(rel) for rel in changed)),
        "smoke": int(any(is_smoke_input(rel) for rel in changed)),
        "tests": "all" if tests == "ALL" else tests,
        "runtime": select_runtime(root, changed),
        "reason": f"{len(changed)} changed path(s); "
        + ("whole test suite (harness changed)" if tests == "ALL" else f"{len(tests)} test module(s) reached"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--base", default="Staging", help="publication base branch on origin")
    parser.add_argument("--receipt", help="also write the plan as JSON here")
    parser.add_argument("--root", help="repository root (default: this script's parent directory)")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    result = plan(root, args.base)
    if args.receipt:
        receipt = Path(args.receipt)
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps({"schema": "l9.pr-check-scope.v1", "base": args.base, **result}, indent=2) + "\n")
    tests = result["tests"]
    print(f"changed={len(result['changed']) if result['changed'] is not None else 'unknown'}")
    print(f"audit={result['audit']}")
    print(f"smoke={result['smoke']}")
    print("tests=" + (tests if isinstance(tests, str) else " ".join(tests)))
    print("runtime=" + result["runtime"])
    print("reason=" + result["reason"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
