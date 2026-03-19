#!/usr/bin/env python3
"""
CI Check: ACL Completeness
==========================
Every model defined with _name = 'x' must have an entry in ir.model.access.csv.
Missing entries cause AccessError on fresh Odoo installs.

Exit codes: 0 = PASS, 1 = FAIL
"""

import re
import sys
from pathlib import Path

from _git_utils import get_git_tracked_files


def collect_model_names(root: Path) -> dict[str, str]:
    """Returns {model_name: defining_file}"""
    model_map = {}
    pattern = re.compile(r'_name\s*=\s*["\']([a-z][a-z0-9_.]+)["\']')
    for py_file in get_git_tracked_files("plasticos_*/models/*.py") or root.rglob("plasticos_*/models/*.py"):
        path = root / py_file if not Path(py_file).is_absolute() else Path(py_file)
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in pattern.finditer(content):
            model_map[m.group(1)] = str(path)
    return model_map


def collect_acl_models(root: Path) -> set[str]:
    """Returns set of model names covered in ir.model.access.csv files."""
    covered = set()
    for csv_file in get_git_tracked_files("plasticos_*/security/ir.model.access.csv") or root.rglob(
        "plasticos_*/security/ir.model.access.csv"
    ):
        path = root / csv_file if not Path(csv_file).is_absolute() else Path(csv_file)
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                parts = line.split(",")
                if len(parts) >= 2:
                    # CSV format: id,name,model_id:id,...
                    # model_id:id is like model_plasticos_intake → plasticos.intake
                    raw = parts[0].strip()
                    if raw.startswith("access_"):
                        model_guess = raw.replace("access_", "").replace("_", ".", 1)
                        covered.add(model_guess)
        except Exception:
            continue
    return covered


def main() -> int:
    root = Path(".")
    model_map = collect_model_names(root)
    covered = collect_acl_models(root)

    missing = {m: f for m, f in model_map.items() if m not in covered}

    if not missing:
        print(f"✅ PASS: All {len(model_map)} models have ACL entries")
        return 0

    print(f"❌ FAIL: {len(missing)} models missing ir.model.access.csv entries:")
    for model, src in sorted(missing.items()):
        print(f"  {model}  (defined in {src})")
    print("\nFix: Add rows to the relevant plasticos_*/security/ir.model.access.csv")
    return 1


if __name__ == "__main__":
    sys.exit(main())
