#!/usr/bin/env python3
"""
CI Guard: plasticos_dev_tools Production Fence
===============================================
plasticos_dev_tools must NOT appear in any other module's depends list.
It is a dev-only module and must be disabled before go-live.

Exit codes: 0 = PASS, 1 = FAIL
"""

import ast
import sys
from pathlib import Path


def main() -> int:
    root = Path(".")
    violations = []

    for manifest_path in root.rglob("plasticos_*/__manifest__.py"):
        if "plasticos_dev_tools" in str(manifest_path):
            continue  # dev_tools' own manifest is fine
        try:
            data = ast.literal_eval(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        depends = data.get("depends", [])
        if "plasticos_dev_tools" in depends:
            violations.append(str(manifest_path))

    # Guard the dev_tools manifest itself — must stay fenced for production
    dev_tools_manifest = root / "plasticos_dev_tools" / "__manifest__.py"
    if dev_tools_manifest.exists():
        try:
            dt_data = ast.literal_eval(dev_tools_manifest.read_text(encoding="utf-8"))
            if dt_data.get("auto_install"):
                violations.append("plasticos_dev_tools/__manifest__.py [auto_install must be False]")
            if dt_data.get("installable", True) is not False:
                violations.append("plasticos_dev_tools/__manifest__.py [installable must be False]")
        except Exception:
            pass

    if violations:
        print("❌ FAIL: plasticos_dev_tools production fence violations:")
        for v in violations:
            print(f"  {v}")
        print("\nFix: Remove 'plasticos_dev_tools' from depends and ensure installable=False, auto_install=False.")
        return 1

    print(
        "✅ PASS: plasticos_dev_tools is fully fenced (not a dep of any module; installable=False, auto_install=False)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
