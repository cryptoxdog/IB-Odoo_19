#!/usr/bin/env python3
"""Scan assertion-free tests and suggest fix templates.

Sole assertion-quality owner. Walks every ``test_*.py`` at any depth beneath a
``tests/`` directory, in the repository tree and in addon trees, and skips the
same non-addon directories as the extended audit.
Counts bare ``assert``, unittest ``assert*``, ``pytest.raises`` /
``assertRaises``, ``raise AssertionError(...)``, and assertion-named helpers
as evidence. A ``check_``, ``_check_``, ``validate_``, ``_run_``, or ``_safe_``
call is not evidence.

Only reachable statements count: anything after an unconditional ``return`` /
``raise`` / ``continue`` / ``break`` in the same block, a constant-false branch,
and the bodies of nested ``def`` / ``lambda`` / ``class`` are not executed by the
test and are ignored.

A call to a helper defined in the same file is resolved one hop instead of
judged by its name: ``self.<name>()`` / ``cls.<name>()`` against the test's own
class and that class's bases defined in the file, and a bare ``<name>()``
against the file's module-level functions. The call is evidence only when the
helper's own reachable body carries direct evidence. A helper that is never
called, is called on an unreachable path, does not assert, or belongs to
another class is not evidence. A call the file does not define is judged by
its name as above.

Exit status is 1 when any test is assertion-free; CI ``static-checks`` runs this
command as a blocking check.
"""

from __future__ import annotations

import argparse
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
_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
_TERMINATORS = (ast.Return, ast.Raise, ast.Continue, ast.Break)


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


def _constant_truth(test: ast.expr) -> bool | None:
    if isinstance(test, ast.Constant):
        return bool(test.value)
    return None


def _child_blocks(stmt: ast.stmt) -> list[list[ast.stmt]]:
    """Statement lists nested in ``stmt`` that can execute, honouring constant branches."""
    if isinstance(stmt, (ast.If, ast.While)):
        truth = _constant_truth(stmt.test)
        if truth is True:
            return [stmt.body]
        if truth is False:
            return [stmt.orelse]
    blocks: list[list[ast.stmt]] = []
    for _field, value in ast.iter_fields(stmt):
        if not isinstance(value, list) or not value:
            continue
        if all(isinstance(item, ast.stmt) for item in value):
            blocks.append(value)
            continue
        for item in value:
            body = getattr(item, "body", None)
            if isinstance(item, (ast.excepthandler, ast.match_case)) and body:
                blocks.append(body)
    return blocks


def _expression_nodes(node: ast.AST):
    """Yield the expression nodes of one statement, without entering nested scopes or blocks."""
    stack = [child for child in ast.iter_child_nodes(node) if not isinstance(child, (ast.stmt, *_SCOPE_NODES))]
    while stack:
        current = stack.pop()
        if isinstance(current, (ast.excepthandler, ast.match_case)):
            continue
        yield current
        stack.extend(
            child for child in ast.iter_child_nodes(current) if not isinstance(child, (ast.stmt, *_SCOPE_NODES))
        )


def _reachable_nodes(body: list[ast.stmt]):
    """Yield every statement and expression node a call of this body can execute."""
    for stmt in body:
        if isinstance(stmt, (*_FUNCTION_NODES, ast.ClassDef)):
            continue
        yield stmt
        yield from _expression_nodes(stmt)
        for block in _child_blocks(stmt):
            yield from _reachable_nodes(block)
        if isinstance(stmt, _TERMINATORS):
            return


def _is_direct_evidence_call(name: str) -> bool:
    if name.startswith(_NON_ASSERTION_HELPER_PREFIXES):
        return False
    if name.startswith("assert") or name.startswith(_ASSERTION_HELPER_PREFIXES):
        return True
    return name in ("fail", "raises", "xfail")


def _has_assertion_evidence(func_node: ast.AST, resolve_helper=None) -> bool:
    """True when a reachable statement of ``func_node`` asserts.

    ``resolve_helper(call)`` returns the local helper definition a call targets,
    or ``None``. A resolved call is evidence only through the helper's own
    reachable body, judged without further helper resolution (one hop).
    """
    for node in _reachable_nodes(getattr(func_node, "body", [])):
        if isinstance(node, ast.Assert) or _is_raise_assertion_error(node):
            return True
        if not isinstance(node, ast.Call):
            continue
        helper = resolve_helper(node) if resolve_helper else None
        if helper is not None:
            if _has_assertion_evidence(helper):
                return True
            continue
        name = _call_name(node.func)
        if name and _is_direct_evidence_call(name):
            return True
    return False


def _is_soft_warning_only(func_node: ast.AST, resolve_helper=None) -> bool:
    if _has_assertion_evidence(func_node, resolve_helper):
        return False
    for node in _reachable_nodes(getattr(func_node, "body", [])):
        if isinstance(node, ast.Call) and _call_name(node.func) == "warn":
            return True
    return False


class _LocalHelpers:
    """One-hop resolution of helper calls to definitions in the same file."""

    def __init__(self, tree: ast.Module):
        self.functions = {node.name: node for node in tree.body if isinstance(node, _FUNCTION_NODES)}
        self.classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}

    def _method(self, class_node: ast.ClassDef, name: str, seen: set[str]):
        if class_node.name in seen:
            return None
        seen.add(class_node.name)
        for item in class_node.body:
            if isinstance(item, _FUNCTION_NODES) and item.name == name:
                return item
        for base in class_node.bases:
            base_node = self.classes.get(base.id) if isinstance(base, ast.Name) else None
            if base_node is not None:
                found = self._method(base_node, name, seen)
                if found is not None:
                    return found
        return None

    def resolver(self, owner: ast.ClassDef | None):
        def resolve(call: ast.Call):
            func = call.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if owner is not None and func.value.id in ("self", "cls"):
                    return self._method(owner, func.attr, set())
                return None
            if isinstance(func, ast.Name):
                return self.functions.get(func.id)
            return None

        return resolve


def _functions_with_owner(node: ast.AST, owner: ast.ClassDef | None = None):
    """Yield ``(function, class whose body defines it or None)`` for every function in the file."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef):
            yield from _functions_with_owner(child, child)
        elif isinstance(child, _FUNCTION_NODES):
            yield child, owner
            yield from _functions_with_owner(child, None)
        else:
            yield from _functions_with_owner(child, owner)


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

        helpers = _LocalHelpers(tree)
        weak_tests = []
        for node, owner in _functions_with_owner(tree):
            if not node.name.startswith("test_"):
                continue
            if any(_decorator_is_skip(d) for d in node.decorator_list):
                continue
            resolve = helpers.resolver(owner)
            if _has_assertion_evidence(node, resolve):
                continue
            if _is_soft_warning_only(node, resolve):
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=str(ROOT), help="tree to scan (default: repository root)")
    args = parser.parse_args(argv)
    fixer = WeakTestFixer(args.root)
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
        print(f"❌ {total_weak} assertion-free test(s) in {files_with_weak} file(s)")
        return 1
    print("✅ No assertion-free tests in any tests/ tree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
