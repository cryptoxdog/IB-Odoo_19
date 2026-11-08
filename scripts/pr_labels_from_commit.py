#!/usr/bin/env python3
"""Map conventional commit type to GitHub PR labels (space-separated for shell)."""

from __future__ import annotations

import re
import sys

TYPE_TO_LABELS: dict[str, list[str]] = {
    "feat": ["enhancement"],
    "fix": ["bug"],
    "docs": ["documentation"],
    "test": ["tests"],
    "ci": ["ci"],
    "build": ["build"],
    "chore": ["chore"],
    "refactor": ["refactor"],
    "perf": ["performance"],
    "style": ["style"],
    "revert": ["bug"],
}


def labels_for_commit_header(header: str) -> list[str]:
    match = re.match(r"^(\w+)", header.strip())
    if not match:
        return []
    return TYPE_TO_LABELS.get(match.group(1), [])


def main() -> int:
    header = sys.argv[1] if len(sys.argv) > 1 else ""
    labels = labels_for_commit_header(header)
    # Only emit labels that exist — gh pr create fails on unknown labels; filter via gh api
    if not labels:
        return 0
    print(" ".join(labels))
    return 0


if __name__ == "__main__":
    sys.exit(main())
