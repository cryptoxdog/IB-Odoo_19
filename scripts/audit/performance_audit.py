#!/usr/bin/env python3
"""
Performance Anti-Pattern Detector
Finds N+1 queries and other performance issues.
"""

import ast
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
        """Flag ORM search() calls whose intent is not a proven bound.

        A search is retained only on proof: a positive limit, a domain in
        which every OR branch carries a non-null identity predicate on every
        execution path, a same-expression projection, or a search that
        defines a returned domain. A zero, None, negative or unresolved
        limit is not a bound; a predicate appended on only some paths is
        not a bound; a categorical ``in`` list is not an identity set.
        Spelling (variable suffixes, a nearby batch comment, a table-name
        list) is not intent. A bound that cannot be resolved is reported as
        UNKNOWN, never assumed.
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
            for call, verdict in _unbounded_search_calls(tree):
                line_num = call.lineno
                code = lines[line_num - 1].strip() if 0 < line_num <= len(lines) else ""
                if verdict == _UNKNOWN:
                    message = "search() bound is UNKNOWN: its limit or domain could not be resolved"
                else:
                    message = "search() has no proven bound for its intent"
                errors.append(
                    {
                        "type": "UNBOUNDED_SEARCH",
                        "severity": "MODERATE",
                        "file": str(py_file.relative_to(self.root_dir)),
                        "line": line_num,
                        "bound": verdict,
                        "code": code,
                        "message": message,
                        "fix": ("Match the search to its intent. Do not add limit=1 to silence this finding."),
                    }
                )
        return errors


_BOUNDED = "bounded"
_UNBOUNDED = "unbounded"
_UNKNOWN = "unknown"
_MAX_DOMAIN_PATHS = 64
_MAX_RESOLUTION_DEPTH = 4
_READ_ONLY_METHODS = frozenset({"copy", "count", "index"})


def _unbounded_search_calls(tree):
    """``(call, verdict)`` for ORM ``search()`` calls without a proven bound."""
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
            verdict = _search_verdict(node, _enclosing_function(tree, node))
            if verdict != _BOUNDED:
                found.append((node, verdict))
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


def _search_verdict(call, func):
    limit = _limit_verdict(call, func)
    if limit == _BOUNDED or _is_projection(call) or _defines_returned_domain(call, func):
        return _BOUNDED
    domain = _domain_verdict(call, func)
    if domain == _BOUNDED:
        return _BOUNDED
    return _UNKNOWN if _UNKNOWN in (limit, domain) else _UNBOUNDED


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


# -- limit ------------------------------------------------------------------


def _limit_verdict(call, func):
    """Whether the call's ``limit`` proves a positive bound.

    Odoo 19 ``search(domain, offset=0, limit=None, order=None)`` emits no
    LIMIT for None, False or 0, and PostgreSQL rejects a negative LIMIT, so
    only a provably positive integer bounds the result.
    """
    import ast

    for keyword in call.keywords:
        if keyword.arg == "limit":
            return _positive_int(keyword.value, func, call, 0)
    if len(call.args) >= 3 and not any(isinstance(arg, ast.Starred) for arg in call.args[:3]):
        return _positive_int(call.args[2], func, call, 0)
    if any(keyword.arg is None for keyword in call.keywords) or any(isinstance(arg, ast.Starred) for arg in call.args):
        return _UNKNOWN
    return _UNBOUNDED


def _positive_int(node, func, anchor, depth):
    import ast

    if depth > _MAX_RESOLUTION_DEPTH:
        return _UNKNOWN
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or node.value is None:
            return _UNBOUNDED
        if isinstance(node.value, int):
            return _BOUNDED if node.value > 0 else _UNBOUNDED
        return _UNKNOWN
    if isinstance(node, ast.UnaryOp) and isinstance(node.operand, ast.Constant):
        if isinstance(node.op, ast.USub) and isinstance(node.operand.value, int):
            return _UNBOUNDED
        return _UNKNOWN
    if isinstance(node, ast.Name):
        return _combine_paths(
            [
                _UNKNOWN if state == _UNKNOWN else _positive_int(state[0], func, state[1], depth + 1)
                for state in _reaching(func, node.id, anchor, "value", depth + 1)
            ]
        )
    if isinstance(node, ast.IfExp):
        return _combine_paths(
            [_positive_int(node.body, func, anchor, depth + 1), _positive_int(node.orelse, func, anchor, depth + 1)]
        )
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        # ``a or b`` returns the first truthy operand, so a falsy constant is
        # never the result; every other operand must be positive.
        operands = [value for value in node.values[:-1] if not (isinstance(value, ast.Constant) and not value.value)]
        return _combine_paths([_positive_int(value, func, anchor, depth + 1) for value in [*operands, node.values[-1]]])
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"max", "min"}
        and node.args
        and not node.keywords
        and not any(isinstance(arg, ast.Starred) for arg in node.args)
    ):
        verdicts = [_positive_int(arg, func, anchor, depth + 1) for arg in node.args]
        if node.func.id == "max":
            if _BOUNDED in verdicts:
                return _BOUNDED
            return _UNKNOWN if _UNKNOWN in verdicts else _UNBOUNDED
        return _combine_paths(verdicts)
    return _UNKNOWN


# -- domain -----------------------------------------------------------------


def _domain_verdict(call, func):
    """Bound proven by the domain on every execution path that reaches the call."""
    import ast

    domain = None
    for keyword in call.keywords:
        if keyword.arg == "domain":
            domain = keyword.value
    if domain is None and call.args and not isinstance(call.args[0], ast.Starred):
        domain = call.args[0]
    if domain is None:
        return _UNKNOWN
    return _combine_paths(
        [_UNKNOWN if path == _UNKNOWN else _elements_verdict(path) for path in _expr_paths(domain, func, call, 0)]
    )


def _elements_verdict(elements):
    """Evaluate one concrete Odoo prefix domain (``&``/``|``/``!``, implicit AND)."""
    position = 0

    def parse():
        nonlocal position
        if position >= len(elements):
            return None
        node = elements[position]
        position += 1
        operator = _domain_operator(node)
        if operator == "!":
            child = parse()
            if child is None:
                return None
            # The complement of a bound is never a proven bound.
            return _UNKNOWN if child == _UNKNOWN else _UNBOUNDED
        if operator in {"&", "|"}:
            left = parse()
            right = parse() if left is not None else None
            if right is None:
                return None
            return _all_of(left, right) if operator == "&" else _any_of(left, right)
        return _term_verdict(node)

    verdicts = []
    while position < len(elements):
        verdict = parse()
        if verdict is None:
            return _UNKNOWN
        verdicts.append(verdict)
    if not verdicts:
        return _UNBOUNDED
    return _all_of(*verdicts)


def _all_of(*verdicts):
    """Conjunction: one bounded operand bounds the intersection."""
    if _BOUNDED in verdicts:
        return _BOUNDED
    return _UNKNOWN if _UNKNOWN in verdicts else _UNBOUNDED


def _any_of(*verdicts):
    """Disjunction: every branch must be bounded."""
    if _UNBOUNDED in verdicts:
        return _UNBOUNDED
    return _UNKNOWN if _UNKNOWN in verdicts else _BOUNDED


def _combine_paths(verdicts):
    """A bound holds only if it holds on every path; one unbounded path is unbounded."""
    if not verdicts:
        return _UNKNOWN
    return _any_of(*verdicts)


def _domain_operator(node):
    import ast

    if isinstance(node, ast.Constant) and node.value in {"&", "|", "!"}:
        return node.value
    return None


def _term_verdict(term):
    import ast

    if not isinstance(term, (ast.List, ast.Tuple)) or len(term.elts) != 3:
        return _UNKNOWN
    field, operator, value = term.elts
    if not isinstance(field, ast.Constant):
        return _UNKNOWN
    if not isinstance(field.value, str):
        return _UNBOUNDED
    if not (isinstance(operator, ast.Constant) and isinstance(operator.value, str)):
        return _UNKNOWN
    if operator.value not in {"=", "in"}:
        return _UNBOUNDED
    identity = _is_identity_field(field.value)
    if operator.value == "=":
        if not identity:
            return _UNBOUNDED
        return _identity_value(value)
    if identity:
        if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            return _any_of(*[_identity_value(elt) for elt in value.elts]) if value.elts else _BOUNDED
        return _identity_value(value)
    if isinstance(value, (ast.List, ast.Tuple, ast.Set, ast.Constant)):
        # A literal list on a non-identity field is a categorical filter.
        return _UNBOUNDED
    # A dynamic set on a non-identity field may be a batch of keys or a
    # population-wide category; its spelling cannot decide which.
    return _UNKNOWN


def _is_identity_field(name):
    return name in {"id", "res_id"} or name.endswith("_id") or name.endswith("_ids")


def _identity_value(node):
    """A non-null record identity: a positive literal id or a dynamic value."""
    import ast

    if isinstance(node, ast.Constant):
        if isinstance(node.value, int) and not isinstance(node.value, bool):
            return _BOUNDED
        return _UNBOUNDED
    if isinstance(
        node,
        (ast.Name, ast.Attribute, ast.Subscript, ast.Call, ast.ListComp, ast.SetComp, ast.GeneratorExp),
    ):
        return _BOUNDED
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return _any_of(*[_identity_value(elt) for elt in node.elts]) if node.elts else _BOUNDED
    return _UNKNOWN


# -- reaching definitions ---------------------------------------------------


def _expr_paths(expr, func, anchor, depth):
    """Possible element sequences of a domain expression at ``anchor``.

    Each path is a tuple of domain elements; ``_UNKNOWN`` marks a path whose
    elements cannot be resolved.
    """
    import ast

    if expr is None or depth > _MAX_RESOLUTION_DEPTH:
        return [_UNKNOWN]
    if isinstance(expr, (ast.List, ast.Tuple)):
        paths = [()]
        for elt in expr.elts:
            if isinstance(elt, ast.Starred):
                paths = _concat_paths(paths, _expr_paths(elt.value, func, anchor, depth + 1))
            else:
                paths = _concat_paths(paths, [(elt,)])
        return paths
    if isinstance(expr, ast.Name):
        return _reaching(func, expr.id, anchor, "domain", depth + 1)
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        return _concat_paths(
            _expr_paths(expr.left, func, anchor, depth + 1),
            _expr_paths(expr.right, func, anchor, depth + 1),
        )
    if (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == "list"
        and len(expr.args) == 1
        and not expr.keywords
    ):
        return _expr_paths(expr.args[0], func, anchor, depth + 1)
    return [_UNKNOWN]


def _concat_paths(lefts, rights):
    out = []
    for left in lefts:
        for right in rights:
            out.append(_UNKNOWN if _UNKNOWN in (left, right) else left + right)
    return _dedupe_states(out)


def _dedupe_states(states):
    seen = set()
    out = []
    for state in states:
        key = _UNKNOWN if state == _UNKNOWN else tuple(id(node) for node in state)
        if key not in seen:
            seen.add(key)
            out.append(state)
    if len(out) > _MAX_DOMAIN_PATHS:
        return [_UNKNOWN]
    return out


def _reaching(func, name, anchor, kind, depth):
    """States of local ``name`` on every path that reaches ``anchor``.

    ``kind`` is ``"domain"`` (a state is a tuple of domain elements) or
    ``"value"`` (a state is ``(expression, assigning statement)``). A name
    that is a parameter, is mutated in a loop or ``try``, or is changed in
    a way not modelled here reaches the anchor as ``_UNKNOWN``.
    """
    if func is None or depth > _MAX_RESOLUTION_DEPTH:
        return [_UNKNOWN]
    states, _ = _simulate(func.body, [_UNKNOWN], name, anchor, kind, func, depth)
    return states or [_UNKNOWN]


def _simulate(stmts, states, name, anchor, kind, func, depth):
    """Walk ``stmts`` in order; return ``(states, reached_anchor)``."""
    import ast

    for stmt in stmts:
        if _contains(stmt, anchor):
            return _descend(stmt, states, name, anchor, kind, func, depth), True
        if isinstance(stmt, ast.If):
            body, _ = _simulate(stmt.body, states, name, anchor, kind, func, depth)
            orelse, _ = _simulate(stmt.orelse, states, name, anchor, kind, func, depth)
            states = _dedupe_states(
                (body if not _terminates(stmt.body) else []) + (orelse if not _terminates(stmt.orelse) else [])
            )
            if _touches(stmt.test, name):
                states = [*states, _UNKNOWN]
        elif isinstance(stmt, ast.With | ast.AsyncWith) and not any(_touches(item, name) for item in stmt.items):
            states, _ = _simulate(stmt.body, states, name, anchor, kind, func, depth)
        elif _is_simple(stmt):
            states = _transfer(stmt, states, name, kind, func, depth)
        elif _touches(stmt, name):
            # Loops, try blocks, match, nested definitions: a change inside
            # them is loop-, exception- or call-dependent.
            states = _dedupe_states([*states, _UNKNOWN])
        if not states:
            return [], False
    return states, False


def _descend(stmt, states, name, anchor, kind, func, depth):
    import ast

    def inside(block):
        return any(_contains(child, anchor) for child in block)

    def run(block, entry):
        return _simulate(block, entry, name, anchor, kind, func, depth)[0]

    loop_entry = _dedupe_states([*states, _UNKNOWN]) if _touches(stmt, name) else states
    if isinstance(stmt, ast.If):
        if inside(stmt.body):
            return run(stmt.body, states)
        if inside(stmt.orelse):
            return run(stmt.orelse, states)
        return states
    if isinstance(stmt, ast.For | ast.AsyncFor | ast.While):
        if inside(stmt.body):
            return run(stmt.body, loop_entry)
        if inside(stmt.orelse):
            return run(stmt.orelse, loop_entry)
        return states if isinstance(stmt, ast.For | ast.AsyncFor) else loop_entry
    if isinstance(stmt, ast.With | ast.AsyncWith):
        if inside(stmt.body):
            return run(stmt.body, states)
        return states
    if isinstance(stmt, ast.Try | ast.TryStar):
        if inside(stmt.body):
            return run(stmt.body, states)
        for handler in stmt.handlers:
            if inside(handler.body):
                return run(handler.body, loop_entry)
        if inside(stmt.orelse):
            return run(stmt.orelse, run(stmt.body, states))
        return loop_entry
    if _is_simple(stmt):
        return states
    return _dedupe_states([*states, _UNKNOWN])


def _transfer(stmt, states, name, kind, func, depth):
    """Apply one simple statement to the reaching states of ``name``."""
    import ast

    target_value = None
    if isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in stmt.targets):
        if any(not isinstance(t, ast.Name) for t in stmt.targets):
            return [_UNKNOWN]
        target_value = stmt.value
    elif (
        isinstance(stmt, ast.AnnAssign)
        and isinstance(stmt.target, ast.Name)
        and stmt.target.id == name
        and stmt.value is not None
    ):
        target_value = stmt.value
    if target_value is not None:
        if kind == "value":
            return [(target_value, stmt)]
        return _expr_paths(target_value, func, stmt, depth + 1)
    if kind == "domain":
        extension = None
        if (
            isinstance(stmt, ast.AugAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.target.id == name
            and isinstance(stmt.op, ast.Add)
        ):
            extension = _expr_paths(stmt.value, func, stmt, depth + 1)
        elif (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute)
            and isinstance(stmt.value.func.value, ast.Name)
            and stmt.value.func.value.id == name
            and stmt.value.func.attr in {"append", "extend"}
            and len(stmt.value.args) == 1
            and not stmt.value.keywords
            and not isinstance(stmt.value.args[0], ast.Starred)
        ):
            arg = stmt.value.args[0]
            if stmt.value.func.attr == "append":
                extension = [(arg,)]
            else:
                extension = _expr_paths(arg, func, stmt, depth + 1)
        if extension is not None:
            return _concat_paths(states, extension)
    if _touches(stmt, name):
        return [_UNKNOWN]
    return states


def _is_simple(stmt):
    import ast

    return not isinstance(
        stmt,
        (
            ast.If,
            ast.For,
            ast.AsyncFor,
            ast.While,
            ast.With,
            ast.AsyncWith,
            ast.Try,
            ast.TryStar,
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
            ast.Match,
        ),
    )


def _terminates(block):
    """Whether control never falls through the end of ``block``."""
    import ast

    if not block:
        return False
    last = block[-1]
    if isinstance(last, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
        return True
    if isinstance(last, ast.If):
        return _terminates(last.body) and _terminates(last.orelse)
    return False


def _touches(node, name):
    """Whether ``node`` may rebind or mutate local ``name``."""
    import ast

    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id == name and isinstance(child.ctx, (ast.Store, ast.Del)):
            return True
        if (
            isinstance(child, ast.Subscript)
            and isinstance(child.value, ast.Name)
            and child.value.id == name
            and isinstance(child.ctx, (ast.Store, ast.Del))
        ):
            return True
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and isinstance(child.func.value, ast.Name)
            and child.func.value.id == name
            and child.func.attr not in _READ_ONLY_METHODS
        ):
            return True
        if isinstance(child, (ast.Global, ast.Nonlocal)) and name in child.names:
            return True
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child.name == name:
            return True
    return False
