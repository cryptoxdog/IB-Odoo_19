#!/usr/bin/env python3
"""Scope the local pre-push gate to what the branch changed.

``make pr-check`` asks this owner, once, which collectors the change set can
reach. Everything else is skipped on this machine; GitHub ``ci.yml`` still runs
the whole suite on the PR and stays the merge verdict.

Usage::

    python3 scripts/pr_check_scope.py --base Staging [--receipt PATH] [--root DIR]

Prints ``KEY=VALUE`` lines::

    changed=<count>
    audit=0|1      static collectors (make audit + audit-baseline) when any
                   non-documentation path changed
    smoke=0|1      Odoo install-smoke when an addon load input or an installer
                   input changed
    tests=all | <space-separated test modules> | (empty: no module to run)
    reason=<one line>

The change set is the committed range from the merge-base with
``origin/<base>`` plus the working tree and untracked files. Every doubt —
no base, no merge-base, no change, a selector error, ``PR_CHECK_SCOPE=full`` —
keeps the whole gate (``audit=1 smoke=1 tests=all``).

Test selection: a changed test module selects itself; any other changed path
selects every test module that names it as a whole word (its path, its stem of
three characters or more, its addon, its dotted module path) or that reads its
top directory as a tree (``ROOT / "scripts"`` without a pinned file). A path
under an addon also selects the modules that walk the addon tree
(``plasticos_*`` globs). A harness change (``tests/conftest.py``,
``tests/common.py``, ``pyproject.toml``, requirements) selects everything.
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
DOCS_RE = re.compile(r"^docs/|\.(md|rst|txt)$")
INSTALLER_RE = re.compile(
    r"^(Dockerfile[^/]*|docker-compose[^/]*\.ya?ml|config/.*|requirements[^/]*\.txt|constraints\.txt"
    r"|scripts/install_smoke\.sh|scripts/get_odoo_module_order\.py)$"
)
HARNESS = {"tests/conftest.py", "tests/common.py", "tests/__init__.py", "pyproject.toml", "constraints.txt"}
HARNESS_RE = re.compile(r"^requirements[^/]*\.txt$")
TREE_WALK_RE = re.compile(r"plasticos_\*|startswith\(\s*[\"']plasticos_[\"']|glob\(\s*[\"']plasticos")


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


def is_smoke_input(rel: str) -> bool:
    parts = Path(rel).parts
    if parts[0].startswith(ADDON_PREFIX):
        return not DOCS_RE.search(rel) and "tests" not in parts[1:]
    return bool(INSTALLER_RE.match(rel))


def tokens_for(rel: str) -> set[str]:
    path = Path(rel)
    found = {rel}
    if path.suffix:
        found.add(rel[: -len(path.suffix)])
    if len(path.stem) >= 3:
        found.add(path.stem)
    if path.parts[0].startswith(ADDON_PREFIX):
        found.add(path.parts[0])
    if path.suffix == ".py":
        found.add(".".join((*path.parts[:-1], path.stem)))
    return {t for t in found if t not in {"__init__", "__manifest__"}}


def _word_pattern(tokens: set[str]) -> re.Pattern[str]:
    escaped = sorted((re.escape(t) for t in tokens), key=len, reverse=True)
    return re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(escaped) + r")(?![A-Za-z0-9_])")


def _dir_pattern(dirs: set[str]) -> re.Pattern[str]:
    # "scripts" or "scripts/" quoted and not followed by a pinned "/ "<file>"".
    escaped = "|".join(re.escape(d) for d in sorted(dirs))
    return re.compile(r"[\"'](?:" + escaped + r")/?[\"'](?!\s*/\s*[\"'])")


def select_tests(root: Path, changed: list[str]) -> list[str] | str:
    if any(rel in HARNESS or HARNESS_RE.match(rel) for rel in changed):
        return "ALL"
    selected: set[str] = set()
    tokens: set[str] = set()
    dirs: set[str] = set()
    addon_changed = False
    for rel in changed:
        parts = Path(rel).parts
        if parts[0] == "tests" and parts[-1].startswith("test_") and rel.endswith(".py"):
            if (root / rel).is_file():
                selected.add(rel)
            continue
        if parts[0].startswith(ADDON_PREFIX):
            addon_changed = True
        elif len(parts) > 1 and parts[0] != "tests":
            dirs.add(parts[0])
        tokens |= tokens_for(rel)
    word = _word_pattern(tokens) if tokens else None
    tree = _dir_pattern(dirs) if dirs else None
    for module in sorted((root / "tests").rglob("test_*.py")):
        rel = module.relative_to(root).as_posix()
        if rel in selected:
            continue
        text = module.read_text(encoding="utf-8", errors="replace")
        if (
            (word and word.search(text))
            or (tree and tree.search(text))
            or (addon_changed and TREE_WALK_RE.search(text))
        ):
            selected.add(rel)
    return sorted(selected)


def plan(root: Path, base: str) -> dict:
    whole = {"audit": 1, "smoke": 1, "tests": "all"}
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
        "audit": int(any(not DOCS_RE.search(rel) for rel in changed)),
        "smoke": int(any(is_smoke_input(rel) for rel in changed)),
        "tests": "all" if tests == "ALL" else tests,
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
    print("reason=" + result["reason"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
