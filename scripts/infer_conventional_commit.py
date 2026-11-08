#!/usr/bin/env python3
"""Infer a conventional commit message from staged files (github push kernel)."""

from __future__ import annotations

import subprocess
import sys


def _staged_files() -> list[str]:
    out = subprocess.check_output(["git", "diff", "--cached", "--name-only"], text=True)
    return [line.strip() for line in out.splitlines() if line.strip()]


def _infer_type(files: list[str]) -> str:
    if any(f.startswith("tests/") or "/tests/" in f or f.startswith("test_") for f in files):
        return "test"
    if all(f.endswith((".md", ".rst")) or f.startswith("docs/") for f in files):
        return "docs"
    if any(f.startswith(".github/workflows/") for f in files):
        return "ci"
    if any("migration" in f or "__manifest__.py" in f for f in files):
        return "fix"
    if any(f.endswith(".xml") and "views/" in f for f in files):
        return "fix"
    if any(f.endswith(".py") for f in files):
        return "feat"
    return "chore"


def _infer_scope(files: list[str]) -> str | None:
    modules: set[str] = set()
    for path in files:
        if path.startswith("plasticos_"):
            modules.add(path.split("/")[0].replace("plasticos_", ""))
        elif path.startswith("tests/"):
            parts = path.split("/")
            if len(parts) > 1 and parts[1].startswith("plasticos_"):
                modules.add(parts[1].replace("plasticos_", ""))
    if len(modules) == 1:
        return next(iter(modules))
    if len(modules) > 1:
        return None
    if any(path.startswith("docs/") for path in files):
        return None
    return None


def _infer_subject(files: list[str], change_type: str) -> str:
    if len(files) == 1:
        base = files[0].split("/")[-1]
        return f"update {base}"
    modules = sorted({f.split("/")[0] for f in files if "/" in f})
    if modules:
        return f"update {', '.join(modules[:3])}"
    return "update workspace changes"


def infer_commit_message() -> str:
    files = _staged_files()
    if not files:
        return "chore: snapshot local changes"

    change_type = _infer_type(files)
    scope = _infer_scope(files)
    subject = _infer_subject(files, change_type)

    header = f"{change_type}({scope}): {subject}" if scope else f"{change_type}: {subject}"
    if len(header) > 100:
        header = header[:97] + "..."
    return header


def main() -> int:
    print(infer_commit_message())
    return 0


if __name__ == "__main__":
    sys.exit(main())
