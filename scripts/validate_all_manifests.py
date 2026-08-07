#!/usr/bin/env python3
"""Validate plasticos_* (+ tests) __manifest__.py files. Space-safe path walk."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "scripts" / "validate_manifest.py"


def main() -> int:
    paths = sorted(ROOT.glob("plasticos_*/__manifest__.py"))
    paths += sorted(ROOT.glob("tests/__manifest__.py"))
    errors = 0
    for path in paths:
        rc = subprocess.call([sys.executable, str(VALIDATOR), str(path.relative_to(ROOT))], cwd=ROOT)
        if rc != 0:
            errors += 1
    if errors:
        print(f"❌ {errors} manifest(s) failed validation")
        return 1
    print("✅ All manifests valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
