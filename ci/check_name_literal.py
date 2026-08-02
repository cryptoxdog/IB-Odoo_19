#!/usr/bin/env python3
"""Enforce `_name = "model.name"` as a string literal on Odoo model classes.

`_name = SOME_CONSTANT` breaks tooling (this repo's own audit scripts, IDE
navigation, `grep`) that locates models by scanning for `_name = "..."` —
AGENTS.md documents this as a hard rule ("`_name` MUST be a string literal —
NEVER `_name = SOME_CONSTANT`"). Single source of truth for both
`.github/workflows/ci.yml` (static-checks) and `make name-check`, so the two
cannot silently drift the way the deleted workflows' inline checks did.
"""

import re
import sys
from pathlib import Path

# Char/Selection field names that legitimately end in "_name" — excluded so
# the model-registration regex below doesn't false-positive on unrelated
# field declarations that happen to start with an uppercase constant token.
FIELD_EXCLUSIONS = re.compile(
    r"\b("
    r"display_name|model_name|field_name|_unique_name|buyer_name|"
    r"company_name|contact_name|pending_company_name|full_name|utm_name|"
    r"pickup_contact_name|delivery_contact_name"
    r")\b"
)

NAME_ASSIGN = re.compile(r"_name = [A-Z][A-Z0-9_]*")


def main() -> int:
    violations: list[str] = []
    for path in sorted(Path().glob("plasticos_*/models/*.py")):
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            # Matches the original inline check's `grep -v "#"`: any line
            # containing a "#" anywhere (not just comment-prefixed lines) is
            # skipped, not just python-style leading comments.
            if "#" in line:
                continue
            if NAME_ASSIGN.search(line) and not FIELD_EXCLUSIONS.search(line):
                violations.append(f"{path}:{lineno}: {line.strip()}")

    if violations:
        print('_name must be a string literal. Use: _name = "model.name"')
        for v in violations:
            print(v)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
