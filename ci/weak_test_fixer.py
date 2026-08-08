#!/usr/bin/env python3
"""Scan repo tests/ for assertion-free tests and suggest fix templates.

Scoped to the repository ``tests/`` tree only — never ``.venv``, site-packages,
or ``Current Work - IGNORE``. Counts unittest ``assert*``, bare ``assert``,
and ``pytest.raises`` / ``assertRaises`` as evidence of assertions.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = ROOT / "tests"

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


def _is_skipped(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


_HELPER_PREFIXES = (
    "validate_",
    "assert_",
    "_assert",
    "_run_",
    "_check_",
    "_safe_",
    "check_",
)


def _decorator_is_skip(dec: ast.expr) -> bool:
    """True for @pytest.mark.skip / @unittest.skip / skipIf / skipUnless."""
    dump = ast.dump(dec)
    return "skip" in dump.lower()


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _has_assertion_evidence(func_node: ast.AST) -> bool:
    """True if the test body contains a meaningful assertion / expectation."""
    for node in ast.walk(func_node):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if not name:
                continue
            if name.startswith("assert") or name in ("fail", "raises", "xfail"):
                return True
            # Helpers that encode the contract (raise / assert internally).
            if name.startswith(_HELPER_PREFIXES) or name in ("_run_twice",):
                return True
    return False


def _is_soft_warning_only(func_node: ast.AST) -> bool:
    """Collect + warnings.warn without asserts — intentional soft gate, not weak."""
    has_warn = False
    has_assert = _has_assertion_evidence(func_node)
    if has_assert:
        return False
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call) and _call_name(node.func) == "warn":
            has_warn = True
    return has_warn


class WeakTestFixer:
    def __init__(self, root_dir: str | Path | None = None):
        self.root_dir = Path(root_dir) if root_dir else ROOT
        self.tests_root = self.root_dir / "tests"

    def analyze_test_file(self, test_file: Path) -> list[dict]:
        """Find tests with no assertion evidence and suggest fixes."""
        with open(test_file, encoding="utf-8") as f:
            tree = ast.parse(f.read())

        weak_tests = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            if any(_decorator_is_skip(d) for d in node.decorator_list):
                continue  # retired / explicitly skipped — not weak
            if _has_assertion_evidence(node):
                continue
            if _is_soft_warning_only(node):
                continue  # intentional soft audit (warnings.warn)
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
        if not self.tests_root.is_dir():
            return
        for test_file in sorted(self.tests_root.rglob("test_*.py")):
            if _is_skipped(test_file):
                continue
            yield test_file


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
        rel = test_file.relative_to(ROOT)
        print(f"\n📄 {rel}")
        for test in weak_tests:
            print(f"  ❌ {test['name']} (line {test['line']})")
            print(f"     Operations: {', '.join(test['operations']) or '(none detected)'}")
            print("     Suggested assertions:")
            for assertion in test["suggested_assertions"]:
                print(f"       • {assertion}")

    print()
    if total_weak:
        print(f"⚠️  {total_weak} assertion-free test(s) in {files_with_weak} file(s) under tests/")
        print("   (advisory — does not fail the gate)")
        return 0
    print("✅ No assertion-free tests under tests/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
