#!/usr/bin/env python3
"""
Performance Anti-Pattern Detector
Finds N+1 queries and other performance issues.
"""

import re
from pathlib import Path

from path_filters import skip_path


class PerformanceAudit:
    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)

    def check_n_plus_one_queries(self):
        """Find ORM queries inside loops"""
        errors = []

        ORM_METHODS = ["search", "browse", "read", "write", "create", "unlink"]

        for py_file in self.root_dir.rglob("models/*.py"):
            if skip_path(py_file):
                continue
            # Skip virtual environments
            if ".venv" in str(py_file) or "venv" in str(py_file):
                continue

            with open(py_file, encoding="utf-8") as f:
                lines = f.readlines()
                in_loop = False
                loop_start = 0

                for i, line in enumerate(lines, 1):
                    # Track loop context
                    if re.match(r"\s*for\s+\w+\s+in\s+", line):
                        in_loop = True
                        loop_start = i
                    elif in_loop and not line.startswith(" " * 4):
                        in_loop = False

                    # Look for ORM calls in loop
                    if in_loop:
                        for method in ORM_METHODS:
                            if f".{method}(" in line and "self.env" in line:
                                errors.append(
                                    {
                                        "type": "N_PLUS_ONE_QUERY",
                                        "severity": "HIGH",
                                        "file": str(py_file.relative_to(self.root_dir)),
                                        "line": i,
                                        "loop_start": loop_start,
                                        "code": line.strip(),
                                        "message": f"ORM .{method}() inside loop (N+1 query)",
                                        "fix": "Move query outside loop or use read_group/prefetch",
                                    }
                                )

        return errors

    def check_unbounded_searches(self):
        """Flag ORM search() calls whose intent is not a proven bound.

        A limit anywhere on the call, a positive identity predicate, a
        same-expression projection, or a search that defines a returned
        domain is retained. Spelling (variable suffixes, a nearby batch
        comment, any ``in`` operator, a table-name list) is not intent.
        """
        import ast

        errors = []
        for py_file in self.root_dir.rglob("models/*.py"):
            if skip_path(py_file) or ".venv" in py_file.parts or "venv" in py_file.parts:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeError):
                continue
            lines = source.splitlines()
            for call in _unbounded_search_calls(tree):
                line_num = call.lineno
                code = lines[line_num - 1].strip() if 0 < line_num <= len(lines) else ""
                errors.append(
                    {
                        "type": "UNBOUNDED_SEARCH",
                        "severity": "MODERATE",
                        "file": str(py_file.relative_to(self.root_dir)),
                        "line": line_num,
                        "code": code,
                        "message": "search() has no proven bound for its intent",
                        "fix": ("Match the search to its intent. Do not add limit=1 to silence this finding."),
                    }
                )
        return errors


def _unbounded_search_calls(tree):
    """ORM ``search()`` calls that are not a proven complete or bounded intent."""
    import ast

    found = []

    def visit(node, aliases):
        for child in ast.iter_child_nodes(node):
            child._unbounded_parent = node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            local = aliases | _model_aliases(node)
            for child in node.body:
                visit(child, local)
            return
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                visit(child, aliases)
            return
        if isinstance(node, ast.Call) and _is_exact_search(node) and _is_orm_owner(node, aliases):
            if not _retains_search(node, _enclosing_function(tree, node)):
                found.append(node)
        for child in ast.iter_child_nodes(node):
            visit(child, aliases)

    visit(tree, frozenset())
    return found


def _enclosing_function(tree, call):
    import ast

    owner = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _contains(node, call):
            if owner is None or _contains(owner, node):
                owner = node
    return owner


def _contains(parent, child):
    return (
        parent.lineno < child.lineno or (parent.lineno == child.lineno and parent.col_offset <= child.col_offset)
    ) and (
        getattr(parent, "end_lineno", parent.lineno) > getattr(child, "end_lineno", child.lineno)
        or (
            getattr(parent, "end_lineno", parent.lineno) == getattr(child, "end_lineno", child.lineno)
            and getattr(parent, "end_col_offset", 0) >= getattr(child, "end_col_offset", 0)
        )
    )


def _model_aliases(func):
    import ast

    aliases = set()
    for node in ast.walk(func):
        value = None
        targets = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        if _is_env_model(value):
            for target in targets:
                if isinstance(target, ast.Name):
                    aliases.add(target.id)
    return aliases


def _is_exact_search(call):
    import ast

    func = call.func
    return isinstance(func, ast.Attribute) and func.attr == "search"


def _unwrap_model(node):
    import ast

    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr not in {"sudo", "with_context", "with_user"}:
            break
        node = node.func.value
    return node


def _is_env_model(node):
    import ast

    node = _unwrap_model(node) if node is not None else None
    return isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == "env"


def _is_orm_owner(call, aliases):
    import ast

    owner = _unwrap_model(call.func.value)
    if isinstance(owner, ast.Name) and (owner.id == "self" or owner.id in aliases):
        return True
    return _is_env_model(owner)


def _retains_search(call, func):
    if any(keyword.arg == "limit" for keyword in call.keywords):
        return True
    if _is_projection(call) or _defines_returned_domain(call, func):
        return True
    return _domain_has_identity(call, func)


def _is_projection(call):
    import ast

    parent = getattr(call, "_unbounded_parent", None)
    return isinstance(parent, ast.Attribute) and parent.attr == "mapped" and parent.value is call


def _defines_returned_domain(call, func):
    import ast

    if func is None:
        return False
    names = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and node.value is call:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    if not names:
        return False
    for node in ast.walk(func):
        if not isinstance(node, ast.Return):
            continue
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Attribute)
                and child.attr == "ids"
                and isinstance(child.value, ast.Name)
                and child.value.id in names
            ):
                return True
    return False


def _domain_has_identity(call, func):
    domain = None
    for keyword in call.keywords:
        if keyword.arg == "domain":
            domain = keyword.value
    if domain is None and call.args:
        domain = call.args[0]
    return _terms_have_identity(_domain_terms(domain, func, getattr(call, "lineno", 0)))


def _domain_terms(domain, func, call_line):
    import ast

    if isinstance(domain, (ast.List, ast.Tuple)):
        return list(domain.elts)
    if isinstance(domain, ast.Name) and func is not None:
        return _assigned_terms(func, domain.id, call_line)
    return []


def _assigned_terms(func, name, call_line):
    import ast

    terms = []

    def visit(stmts):
        for stmt in stmts:
            if getattr(stmt, "lineno", 0) > call_line:
                continue
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id == name
                        and isinstance(stmt.value, (ast.List, ast.Tuple))
                    ):
                        terms.clear()
                        terms.extend(stmt.value.elts)
            elif (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Attribute)
                and stmt.value.func.attr == "append"
                and isinstance(stmt.value.func.value, ast.Name)
                and stmt.value.func.value.id == name
                and stmt.value.args
                and stmt.lineno <= call_line
            ):
                terms.append(stmt.value.args[0])
            for block in _nested_statements(stmt):
                visit(block)

    visit(func.body)
    return terms


def _nested_statements(stmt):
    import ast

    blocks = []
    for name in ("body", "orelse", "finalbody"):
        block = getattr(stmt, name, None)
        if block and isinstance(block, list) and block and isinstance(block[0], ast.stmt):
            blocks.append(block)
    return blocks


def _terms_have_identity(terms):
    import ast

    for term in terms:
        if not isinstance(term, (ast.List, ast.Tuple)) or len(term.elts) < 3:
            continue
        field, operator = term.elts[0], term.elts[1]
        if not (isinstance(field, ast.Constant) and isinstance(field.value, str)):
            continue
        if not (isinstance(operator, ast.Constant) and operator.value in {"=", "in"}):
            continue
        if not _is_explicit_value(term.elts[2]):
            continue
        if operator.value == "in":
            return True
        name = field.value
        if name in {"id", "res_id"} or name.endswith("_id") or name.endswith("_ids"):
            return True
    return False


def _is_explicit_value(node):
    import ast

    if isinstance(node, ast.Constant):
        return False
    if isinstance(node, (ast.Name, ast.Attribute, ast.Subscript, ast.Call)):
        return True
    if isinstance(node, (ast.List, ast.Tuple)):
        return bool(node.elts) and all(_is_explicit_value(elt) for elt in node.elts)
    return False
