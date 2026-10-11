#!/usr/bin/env python3
"""Scan assertion-free tests and suggest fix templates.

Sole assertion-quality owner. Walks every ``test_*.py`` at any depth beneath a
``tests/`` directory, in the repository tree and in addon trees, and skips the
same non-addon directories as the extended audit.
Counts bare ``assert``, unittest ``assert*``, ``pytest.raises`` /
``assertRaises``, ``raise AssertionError(...)``, and assertion-named helpers
as evidence. A ``check_``, ``_check_``, ``validate_``, ``_run_``, or ``_safe_``
call is not evidence.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_PARTS = frozenset(
    {
        ".venv",
        "venv",
        "site-packages",
        "node_modules",
        "__pycache__",
        ".git",
        "Current Work - IGNORE",
        "odoo-enterprise",
    }
)

_ASSERTION_HELPER_PREFIXES = ("assert_", "_assert")
_NON_ASSERTION_HELPER_PREFIXES = ("check_", "_check_", "validate_", "_run_", "_safe_")


def _is_skipped(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def _decorator_is_skip(dec: ast.expr) -> bool:
    return "skip" in ast.dump(dec).lower()


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_raise_assertion_error(node: ast.AST) -> bool:
    if not isinstance(node, ast.Raise) or node.exc is None:
        return False
    exc: ast.expr = node.exc
    if isinstance(exc, ast.Call):
        exc = exc.func
    if isinstance(exc, ast.Name):
        return exc.id == "AssertionError"
    if isinstance(exc, ast.Attribute):
        return exc.attr == "AssertionError"
    return False


def _has_assertion_evidence(func_node: ast.AST) -> bool:
    for node in ast.walk(func_node):
        if isinstance(node, ast.Assert) or _is_raise_assertion_error(node):
            return True
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if not name or name.startswith(_NON_ASSERTION_HELPER_PREFIXES):
                continue
            if name.startswith("assert") or name.startswith(_ASSERTION_HELPER_PREFIXES):
                return True
            if name in ("fail", "raises", "xfail"):
                return True
    return False


def _is_soft_warning_only(func_node: ast.AST) -> bool:
    if _has_assertion_evidence(func_node):
        return False
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call) and _call_name(node.func) == "warn":
            return True
    return False


def _audit_skip_parts():
    audit_dir = ROOT / "scripts" / "audit"
    if str(audit_dir) not in sys.path:
        sys.path.insert(0, str(audit_dir))
    from path_filters import SKIP_DIR_PARTS, skip_path

    return SKIP_DIR_PARTS, skip_path


class WeakTestFixer:
    def __init__(self, root_dir: str | Path | None = None):
        self.root_dir = Path(root_dir) if root_dir else ROOT

    def analyze_test_file(self, test_file: Path) -> list[dict]:
        with open(test_file, encoding="utf-8") as f:
            tree = ast.parse(f.read())

        weak_tests = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            if any(_decorator_is_skip(d) for d in node.decorator_list):
                continue
            if _has_assertion_evidence(node):
                continue
            if _is_soft_warning_only(node):
                continue
            operations = self._extract_operations(node)
            weak_tests.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "operations": operations,
                    "suggested_assertions": self._suggest_assertions(operations),
                }
            )
        return weak_tests

    def _extract_operations(self, func_node):
        ops = []
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("create", "write", "search", "unlink"):
                    ops.append(node.func.attr)
        return ops

    def _suggest_assertions(self, operations):
        suggestions = []
        if "create" in operations:
            suggestions.append("self.assertTrue(record.exists())")
            suggestions.append("assert record exists / state after create")
        if "write" in operations:
            suggestions.append("self.assertEqual(record.field_name, expected_value)")
        if "search" in operations:
            suggestions.append("self.assertEqual(len(results), expected_count)")
        if not suggestions:
            suggestions.append("add an assert / pytest.raises that encodes the contract")
        return suggestions

    def iter_test_files(self):
        """Yield every ``test_*.py`` at any depth beneath a ``tests/`` directory.

        Covers the repository ``tests/`` tree and addon ``tests/`` trees,
        including nested suites such as ``tests/contracts/``. Skips are judged
        on the path relative to ``root_dir`` so the checkout location never
        hides the population.
        """
        if not self.root_dir.is_dir():
            return
        skip_parts, skip_path = _audit_skip_parts()
        pruned = skip_parts | SKIP_PARTS
        found: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            dirnames[:] = [name for name in dirnames if name not in pruned]
            relative_dir = Path(dirpath).relative_to(self.root_dir)
            if "tests" not in relative_dir.parts:
                continue
            for name in filenames:
                if not (name.startswith("test_") and name.endswith(".py")):
                    continue
                relative = relative_dir / name
                if _is_skipped(relative) or skip_path(relative):
                    continue
                found.append(self.root_dir / relative)
        yield from sorted(found)


def main() -> int:
    fixer = WeakTestFixer(ROOT)
    total_weak = 0
    files_with_weak = 0
    for test_file in fixer.iter_test_files():
        weak_tests = fixer.analyze_test_file(test_file)
        if not weak_tests:
            continue
        files_with_weak += 1
        total_weak += len(weak_tests)
        rel = test_file.relative_to(fixer.root_dir)
        print(f"\n📄 {rel}")
        for test in weak_tests:
            print(f"  ❌ {test['name']} (line {test['line']})")
            print(f"     Operations: {', '.join(test['operations']) or '(none detected)'}")
            print("     Suggested assertions:")
            for assertion in test["suggested_assertions"]:
                print(f"       • {assertion}")

    print()
    if total_weak:
        print(f"⚠️  {total_weak} assertion-free test(s) in {files_with_weak} file(s)")
        print("   (advisory — does not fail the gate)")
        return 0
    print("✅ No assertion-free tests in any tests/ tree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
