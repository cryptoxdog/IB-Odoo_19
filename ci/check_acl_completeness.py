#!/usr/bin/env python3
"""
CI Check: ACL Completeness
==========================
Every model defined with _name = 'x' must have an entry in ir.model.access.csv.
Missing entries cause AccessError on fresh Odoo installs.

Exit codes: 0 = PASS, 1 = FAIL
"""

import ast
import csv
import sys
from pathlib import Path

from _git_utils import get_git_tracked_files


def _class_defines_abstract_or_transient(node: ast.ClassDef) -> bool:
    """True if class extends AbstractModel / TransientModel or sets _abstract."""
    for base in node.bases:
        if isinstance(base, ast.Attribute) and base.attr in frozenset({"AbstractModel", "TransientModel"}):
            return True
        if isinstance(base, ast.Name) and base.id in frozenset({"AbstractModel", "TransientModel"}):
            return True
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.target.id == "_abstract":
            if isinstance(item.value, ast.Constant) and item.value.value is True:
                return True
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id == "_abstract":
                    if isinstance(item.value, ast.Constant) and item.value.value is True:
                        return True
    return False


def _class_model_name(node: ast.ClassDef) -> str | None:
    for item in node.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id == "_name":
                    if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                        return item.value.value
    return None


def collect_model_names(root: Path) -> dict[str, str]:
    """Return {technical model name: defining file} for concrete ``models.Model`` classes only."""
    model_map: dict[str, str] = {}
    for py_file in get_git_tracked_files("plasticos_*/models/*.py") or root.rglob("plasticos_*/models/*.py"):
        path = root / py_file if not Path(py_file).is_absolute() else Path(py_file)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if _class_defines_abstract_or_transient(node):
                continue
            name_val = _class_model_name(node)
            if name_val:
                model_map[name_val] = str(path)
    return model_map


def _model_xmlid_to_technical(model_xmlid: str) -> str | None:
    """model_plasticos_intake → plasticos.intake (ir.model.data convention)."""
    raw = model_xmlid.strip()
    if not raw.startswith("model_"):
        return None
    return raw[6:].replace("_", ".")


def collect_acl_models(root: Path) -> set[str]:
    """Returns set of model technical names covered in ir.model.access.csv files."""
    covered: set[str] = set()
    for csv_file in get_git_tracked_files("plasticos_*/security/ir.model.access.csv") or root.rglob(
        "plasticos_*/security/ir.model.access.csv"
    ):
        path = root / csv_file if not Path(csv_file).is_absolute() else Path(csv_file)
        try:
            with path.open(encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                rows = list(reader)
        except Exception:
            continue
        if not rows:
            continue
        header = [c.strip() for c in rows[0]]
        try:
            model_col = header.index("model_id:id")
        except ValueError:
            continue
        for row in rows[1:]:
            if len(row) <= model_col:
                continue
            technical = _model_xmlid_to_technical(row[model_col])
            if technical:
                covered.add(technical)
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
