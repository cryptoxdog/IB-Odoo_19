#!/usr/bin/env python3
"""Refuse GitHub API publication.

``make pr`` is the only publication ceremony. It consumes the live L4
check-remote provider before any remote mutation. This command used to exit 0
after ``make pr-check`` and tell the operator to push through the API, which
skipped that ceremony.
"""

from __future__ import annotations


def main() -> int:
    print("refusing API publication: the only publication ceremony is make pr")
    print("make api-push-check does not authorize a push, a new PR, or a Production promotion")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
