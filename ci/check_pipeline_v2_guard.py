#!/usr/bin/env python3
"""
CI Guard: pipeline_v2.py Import Fence
======================================
pipeline_v2.py is PERMANENTLY DEFERRED. It must never be imported.
Any reference to it in Python files or XML is a CI blocker.

Exit codes: 0 = PASS, 1 = FAIL (reference found)
"""

import re
import sys
from pathlib import Path

from _git_utils import get_git_tracked_files

FORBIDDEN_PATTERNS = [
    r"from\s+.*pipeline_v2\s+import",
    r"import\s+.*pipeline_v2",
    r"pipeline_v2",
]


def main() -> int:
    root = Path(".")
    hits = []
    combined = re.compile("|".join(FORBIDDEN_PATTERNS))

    for py_file in get_git_tracked_files("*.py") or root.rglob("plasticos_*/**/*.py"):
        path = root / py_file if not Path(py_file).is_absolute() else Path(py_file)
        if "pipeline_v2" in str(path):
            continue  # the file itself is allowed to exist, just not be referenced
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for i, line in enumerate(content.splitlines(), 1):
            if combined.search(line) and not line.strip().startswith("#"):
                hits.append(f"  {path}:{i}: {line.strip()}")

    if hits:
        print("❌ FAIL: pipeline_v2.py is referenced — this file is DEFERRED and must not be imported:")
        print("\n".join(hits))
        return 1
    print("✅ PASS: pipeline_v2.py is not referenced anywhere")
    return 0


if __name__ == "__main__":
    sys.exit(main())
