#!/usr/bin/env python3
"""
Performance Anti-Pattern Detector
Finds N+1 queries and other performance issues.
"""

import ast
import re
from pathlib import Path

from path_filters import skip_path

_QUERY_METHODS = frozenset({"search", "search_count", "search_read", "read", "read_group"})
_MUTATION_METHODS = frozenset({"create", "write", "unlink"})
_FLAGGED_METHODS = _QUERY_METHODS | _MUTATION_METHODS


def _is_env_subscription(node):
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "env"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "self"
    )


def _without_sudo(node):
    """``x.sudo()`` addresses the same model as ``x``."""
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "sudo":
        node = node.func.value
    return node


def _collect_aliases(func_node):
    aliases = set()
    for node in ast.walk(func_node):
        value = None
        targets = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        if value is not None and _is_env_subscription(_without_sudo(value)):
            for target in targets:
                if isinstance(target, ast.Name):
                    aliases.add(target.id)
    return aliases


def _orm_method(call, aliases):
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr not in _FLAGGED_METHODS:
        return None
    owner = _without_sudo(func.value)
    if isinstance(owner, ast.Name) and (owner.id == "self" or owner.id in aliases):
        return func.attr
    if _is_env_subscription(owner):
        return func.attr
    return None


def _loop_calls(tree):
    """Yield (call, loop_lineno, aliases) for ORM-shaped calls inside loops.

    Nested function and class bodies are not part of the enclosing loop.
    ``browse()`` is recordset construction and is not returned.
    """
    found = []

    def visit(node, in_loop, loop_lineno, aliases):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if in_loop:
                return
            local_aliases = aliases | _collect_aliases(node)
            for child in node.body:
                visit(child, False, 0, local_aliases)
            return
        if isinstance(node, ast.ClassDef):
            if in_loop:
                return
            for child in node.body:
                visit(child, False, 0, aliases)
            return
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            for child in node.body:
                visit(child, True, node.lineno, aliases)
            for child in node.orelse:
                visit(child, in_loop, loop_lineno, aliases)
            return
        if isinstance(node, ast.Call) and in_loop:
            method = _orm_method(node, aliases)
            if method:
                found.append((node, loop_lineno, method))
        for child in ast.iter_child_nodes(node):
            visit(child, in_loop, loop_lineno, aliases)

    visit(tree, False, 0, set())
    return found


class PerformanceAudit:
    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)

    def check_n_plus_one_queries(self):
        """Find ORM reads and writes inside loops.

        ``browse()`` builds a recordset and is not itself a query. Unknown
        call shapes are left unknown rather than guessed into findings.
        """
        errors = []

        for py_file in self.root_dir.rglob("models/*.py"):
            if skip_path(py_file):
                continue
            if ".venv" in str(py_file) or "venv" in str(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeError):
                continue
            lines = source.splitlines()
            for call, loop_start, method in _loop_calls(tree):
                line_num = call.lineno
                code = lines[line_num - 1].strip() if 0 < line_num <= len(lines) else ""
                if method in _MUTATION_METHODS:
                    message = f"ORM .{method}() inside loop (mutation in loop)"
                    fix = "Create, write, or unlink the recordset once outside the loop"
                else:
                    message = f"ORM .{method}() inside loop (query in loop)"
                    fix = "Move the query outside the loop or prefetch the recordset"
                errors.append(
                    {
                        "type": "N_PLUS_ONE_QUERY",
                        "severity": "HIGH",
                        "file": str(py_file.relative_to(self.root_dir)),
                        "line": line_num,
                        "loop_start": loop_start,
                        "code": code,
                        "message": message,
                        "fix": fix,
                    }
                )

        return errors

    def check_unbounded_searches(self):
        """Find search() calls without limit that could return huge recordsets.

        Excludes legitimate patterns:
        - Searches with 'in' operator (already bounded by input list)
        - Searches for small reference tables (country, currency, etc.)
        - Searches used for duplicate/validation checking
        - Searches assigned to variables ending in _ids, _by_*, etc. (batch lookups)
        - Searches in batch query context (preceded by comment about batch)
        """
        errors = []

        # Models that typically have small, bounded result sets
        SMALL_TABLES = {
            "res.country",
            "res.currency",
            "res.lang",
            "res.company",
            "uom.uom",
            "uom.category",
            "product.category",
            "ir.model",
            "ir.model.fields",
            "ir.module.module",
            "plasticos.material.form",
            "plasticos.source.type",
            "plasticos.document.tag",
            "plasticos.document.rule",
        }

        for py_file in self.root_dir.rglob("models/*.py"):
            if skip_path(py_file):
                continue
            # Skip virtual environments
            if ".venv" in str(py_file) or "venv" in str(py_file):
                continue

            with open(py_file, encoding="utf-8") as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                if ".search(" not in line or "limit=" in line:
                    continue

                # Skip if it's a count or boolean check
                if "len(" in line or "if " in line or "not " in line:
                    continue

                # Skip if using 'in' operator (bounded by input list)
                if '"in"' in line or "'in'" in line or ", in," in line.lower():
                    continue

                # Skip searches on small reference tables
                is_small_table = False
                for table in SMALL_TABLES:
                    if f'["{table}"]' in line or f"['{table}']" in line:
                        is_small_table = True
                        break
                if is_small_table:
                    continue

                # Skip batch lookup patterns (variable names suggest bounded use)
                if re.search(r"(\w+_by_\w+|_ids|_map|_dict)\s*=", line):
                    continue

                # Skip if preceded by batch query comment (within 3 lines)
                context_start = max(0, line_num - 4)
                context = "".join(lines[context_start:line_num])
                if "batch" in context.lower() or "Batch" in context:
                    continue

                # Skip duplicate/validation checks
                if "duplicate" in line.lower() or "existing" in line.lower():
                    continue

                errors.append(
                    {
                        "type": "UNBOUNDED_SEARCH",
                        "severity": "MODERATE",
                        "file": str(py_file.relative_to(self.root_dir)),
                        "line": line_num,
                        "code": line.strip(),
                        "message": "search() without limit may return huge recordset",
                        "fix": "Add limit parameter or use search_count()",
                    }
                )

        return errors
