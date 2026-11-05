#!/usr/bin/env python3
"""Validate commit message against PlasticOS conventional commit rules."""

from __future__ import annotations

import re
import sys

# Mirrors .cz.toml schema_pattern and .commitlintrc.json
PATTERN = re.compile(r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(\w+\))?!?: .{1,100}$")


def validate(message: str) -> None:
    header = message.strip().splitlines()[0] if message.strip() else ""
    if not header:
        raise ValueError("Commit message header is empty.")
    if len(header) > 100:
        raise ValueError(f"Commit header exceeds 100 chars ({len(header)}).")
    if not PATTERN.match(header):
        raise ValueError(
            "Commit message must match conventional format, e.g. "
            "'feat(intake): add material profile bridge'.\n"
            f"Got: {header!r}"
        )


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_conventional_commit.py <message>", file=sys.stderr)
        return 2
    try:
        validate(sys.argv[1])
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    print("✅ Conventional commit message OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
