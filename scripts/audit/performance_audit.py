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


_KEYSET_OPERATORS = frozenset({">", "<", ">=", "<="})


def _positive_literal_limit(call):
    """``limit=<positive int literal>`` on the call."""
    for keyword in call.keywords:
        if keyword.arg == "limit":
            value = keyword.value
            return isinstance(value, ast.Constant) and type(value.value) is int and value.value > 0
    return False


def _id_cursor(call):
    """The local name a ``("id", <, > , <=, >=, name)`` domain term compares against, else ``None``."""
    domain = None
    for keyword in call.keywords:
        if keyword.arg == "domain":
            domain = keyword.value
    if domain is None and call.args:
        domain = call.args[0]
    if not isinstance(domain, (ast.List, ast.Tuple)):
        return None
    for term in domain.elts:
        if not (isinstance(term, (ast.Tuple, ast.List)) and len(term.elts) == 3):
            continue
        field, operator, value = term.elts
        if (
            isinstance(field, ast.Constant)
            and field.value == "id"
            and isinstance(operator, ast.Constant)
            and operator.value in _KEYSET_OPERATORS
            and isinstance(value, ast.Name)
        ):
            return value.id
    return None


def _rebound_from(body, cursor, page):
    """Whether ``cursor`` is assigned somewhere in ``body`` from an expression that reads ``page``."""
    for stmt in body:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == cursor for target in node.targets):
                continue
            if any(isinstance(leaf, ast.Name) and leaf.id == page for leaf in ast.walk(node.value)):
                return True
    return False


def _keyset_page_searches(loop):
    """``search`` calls in a ``while`` body that page by keyset.

    The call is bound to a name (the page), its domain compares ``id`` with a
    cursor name, the loop body rebinds that cursor from the page, and
    ``limit=`` is a positive literal. That shape runs one bounded query per
    page, so it is not a per-record query. Any other call in the loop is.
    """
    paged = set()
    for stmt in loop.body:
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)):
            continue
        call = stmt.value
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "search"):
            continue
        if not _positive_literal_limit(call):
            continue
        cursor = _id_cursor(call)
        if cursor is None:
            continue
        if _rebound_from(loop.body, cursor, stmt.targets[0].id):
            paged.add(call)
    return paged


def _loop_calls(tree):
    """Yield (call, loop_lineno, aliases) for ORM-shaped calls inside loops.

    Nested function and class bodies are not part of the enclosing loop.
    ``browse()`` is recordset construction and is not returned. A keyset
    pagination search (``_keyset_page_searches``) is one query per page and
    is not returned either.
    """
    found = []

    def visit(node, in_loop, loop_lineno, aliases, paged):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if in_loop:
                return
            local_aliases = aliases | _collect_aliases(node)
            for child in node.body:
                visit(child, False, 0, local_aliases, paged)
            return
        if isinstance(node, ast.ClassDef):
            if in_loop:
                return
            for child in node.body:
                visit(child, False, 0, aliases, paged)
            return
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            inner = paged | _keyset_page_searches(node) if isinstance(node, ast.While) else paged
            for child in node.body:
                visit(child, True, node.lineno, aliases, inner)
            for child in node.orelse:
                visit(child, in_loop, loop_lineno, aliases, paged)
            return
        if isinstance(node, ast.Call) and in_loop and node not in paged:
            method = _orm_method(node, aliases)
            if method:
                found.append((node, loop_lineno, method))
        for child in ast.iter_child_nodes(node):
            visit(child, in_loop, loop_lineno, aliases, paged)

    visit(tree, False, 0, set(), frozenset())
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
        """Report ORM ``search()`` calls proved to read a population.

        Contract (behavior lock: ``tests/test_unbounded_search_intent.py``).
        ``_search_verdict`` is the only decider and returns ``bounded``,
        ``unbounded`` or ``unknown``. It tries, in order: a proved positive
        limit, a same-expression projection, returned-domain completeness, then
        the domain. A later ``unknown`` never cancels an earlier ``bounded``.

        A row is appended only for ``unbounded``: the search provably reads a
        population and nothing in the function shows that the whole population
        is required. ``unknown`` means a proof stopped; it is not a finding and
        it is not a bound. ``_unbounded_search_calls`` still returns both, so
        the tests can see where a proof stopped.

        Every proof is general and AST-shaped. Never add a per-line, variable
        name, method-name prefix or comment exemption here, and never log an
        ``UNBOUNDED_SEARCH`` row in a baseline. A finding is a remediation item:
        match the search to its intent. Do not add ``limit=1`` to silence it.
        """
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
                if verdict != _UNBOUNDED:
                    continue
                line_num = call.lineno
                code = lines[line_num - 1].strip() if 0 < line_num <= len(lines) else ""
                errors.append(
                    {
                        "type": "UNBOUNDED_SEARCH",
                        "severity": "MODERATE",
                        "file": str(py_file.relative_to(self.root_dir)),
                        "line": line_num,
                        "bound": verdict,
                        "code": code,
                        "message": "search() reads a population with no proven bound for its intent",
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


_CATALOG_MODELS = frozenset({"plasticos.polymer", "plasticos.penalty.rule", "plasticos.document.rule"})
_XMLID_MODEL = "ir.model.data"
_PARTNER_MODEL = "res.partner"
_WRITE_METHODS = frozenset({"create", "write", "unlink"})
_LIKE_OPERATORS = frozenset({"=like", "=ilike"})
_LIKE_WILDCARDS = ("%", "_")
_DICT_READS = frozenset({"get", "items", "keys", "values"})


def _search_calls(tree):
    """``(call, verdict)`` for every ORM ``search()`` call in ``tree``."""
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
            found.append((node, _search_verdict(node, _enclosing_function(tree, node), tree)))
        for child in ast.iter_child_nodes(node):
            visit(child, aliases)

    visit(tree, frozenset())
    return found


def _unbounded_search_calls(tree):
    """``(call, verdict)`` for ORM ``search()`` calls without a proven bound (``unbounded`` or ``unknown``)."""
    return [(call, verdict) for call, verdict in _search_calls(tree) if verdict != _BOUNDED]


def _enclosing_function(tree, call):
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
    func = call.func
    return isinstance(func, ast.Attribute) and func.attr == "search"


def _unwrap_model(node):
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr not in {"sudo", "with_context", "with_user"}:
            break
        node = node.func.value
    return node


def _is_env_model(node):
    node = _unwrap_model(node) if node is not None else None
    return isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == "env"


def _is_orm_owner(call, aliases):
    owner = _unwrap_model(call.func.value)
    if isinstance(owner, ast.Name) and (owner.id == "self" or owner.id in aliases):
        return True
    return _is_env_model(owner)


def _search_verdict(call, func, module=None):
    """The one decider: limit, then projection, then returned-domain completeness, then domain."""
    limit = _limit_verdict(call, func, module)
    if limit == _BOUNDED or _is_projection(call) or _defines_returned_domain(call, func, module):
        return _BOUNDED
    domain = _domain_verdict(call, func, module)
    if domain == _BOUNDED:
        return _BOUNDED
    return _UNKNOWN if _UNKNOWN in (limit, domain) else _UNBOUNDED


def _is_projection(call):
    parent = getattr(call, "_unbounded_parent", None)
    return isinstance(parent, ast.Attribute) and parent.attr == "mapped" and parent.value is call


def _defines_returned_domain(call, func, module=None):
    """The search is complete because it defines a domain a ``_search_*`` method returns.

    Either the searching function returns ``<result>.ids``, or (one callee) it
    returns the recordset and every same-file call of it sits in a ``_search_*``
    method whose returned domain is built from that call.
    """
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
    return _feeds_search_method(names, func, module)


def _feeds_search_method(names, func, module):
    if module is None or func.name.startswith("_search_") or _unique_function(module, func.name) is not func:
        return False
    if not any(_returns_name(func, name) for name in names):
        return False
    calls = [node for node in ast.walk(module) if isinstance(node, ast.Call) and _calls_function(node, func.name)]
    if not calls:
        return False
    for node in calls:
        caller = _enclosing_function(module, node)
        if caller is None or not caller.name.startswith("_search_") or not _flows_into_return(node, caller):
            return False
    return True


def _flows_into_return(node, func):
    """``node`` is in a returned expression, or in one local that a return reads."""
    parents = _parent_map(func)
    stmt = node
    while stmt is not None and not isinstance(stmt, ast.stmt):
        stmt = parents.get(stmt)
    if isinstance(stmt, ast.Return):
        return True
    if isinstance(stmt, ast.Assign):
        targets = [target.id for target in stmt.targets if isinstance(target, ast.Name)]
        return len(targets) == len(stmt.targets) and any(_returns_name(func, name) for name in targets)
    if (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Call)
        and isinstance(stmt.value.func, ast.Attribute)
        and stmt.value.func.attr in {"append", "extend"}
        and isinstance(stmt.value.func.value, ast.Name)
    ):
        return _returns_name(func, stmt.value.func.value.id)
    return False


# -- receiver model ---------------------------------------------------------


def _env_literal(node):
    node = _unwrap_model(node) if node is not None else None
    if not _is_env_model(node):
        return None
    key = node.slice
    return key.value if isinstance(key, ast.Constant) and isinstance(key.value, str) else None


def _receiver_model(call, func, module):
    """The model literal a search runs on: ``self.env["x"]``, an alias of it, or the class ``_name``."""
    owner = _unwrap_model(call.func.value)
    literal = _env_literal(owner)
    if literal is not None:
        return literal
    if not isinstance(owner, ast.Name) or func is None:
        return None
    if owner.id == "self":
        return _class_model_name(module, func)
    if owner.id in _parameters(func):
        return None
    values = []
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == owner.id for t in node.targets):
            values.append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == owner.id:
            values.append(node.value)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == owner.id:
            return None
    literals = {_env_literal(value) for value in values}
    if len(literals) != 1 or None in literals:
        return None
    return literals.pop()


def _class_model_name(module, func):
    if module is None:
        return None
    for node in ast.walk(module):
        if isinstance(node, ast.ClassDef) and any(child is func for child in node.body):
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and stmt.targets[0].id == "_name"
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                ):
                    return stmt.value.value
            return None
    return None


def _catalog_read(model, paths, func, module):
    """A reference catalog read: the closed catalog set, or ``ir.model.data`` of one constant module."""
    if model in _CATALOG_MODELS:
        return True
    if model != _XMLID_MODEL or not paths or _UNKNOWN in paths:
        return False
    return all(any(_module_restriction(term, func, module) for term in _conjuncts(path)) for path in paths)


def _module_restriction(term, func, module):
    if not isinstance(term, (ast.List, ast.Tuple)) or len(term.elts) != 3:
        return False
    field, operator, value = term.elts
    if not (isinstance(field, ast.Constant) and field.value == "module"):
        return False
    if not (isinstance(operator, ast.Constant) and operator.value == "="):
        return False
    if isinstance(value, ast.Constant):
        return isinstance(value.value, str)
    if isinstance(value, ast.Name) and func is not None:
        if value.id in _parameters(func) or any(_touches(stmt, value.id) for stmt in func.body):
            return False
        return value.id in _module_string_constants(module)
    return False


def _conjuncts(elements):
    """Terms that every row of the prefix domain must satisfy (implicit AND and ``&``)."""
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
            return None if child is None else ("!", child)
        if operator in {"&", "|"}:
            left = parse()
            right = parse() if left is not None else None
            return None if right is None else (operator, left, right)
        return ("term", node)

    def collect(node, out):
        if node[0] == "term":
            out.append(node[1])
        elif node[0] == "&":
            collect(node[1], out)
            collect(node[2], out)

    out = []
    while position < len(elements):
        node = parse()
        if node is None:
            return []
        collect(node, out)
    return out


def _partner_mismatch_report(call, func, model, paths):
    """A read-only ``res.partner`` report: every row of an ``= False`` domain is folded into its output.

    All must hold: the domain names an ``= False`` term on every path; the
    function creates, writes, unlinks and assigns no attribute; the search is
    bound once to one local that is never sliced or returned; every use of that
    local is ``len()`` or an iteration that folds each row into a collection the
    function returns or raises with.
    """
    if model != _PARTNER_MODEL or func is None or not paths or _UNKNOWN in paths:
        return False
    if not all(any(_is_false_equality(term) for term in path) for path in paths):
        return False
    if _writes(func):
        return False
    parents = _parent_map(func)
    stmt = parents.get(call)
    if not (
        isinstance(stmt, ast.Assign)
        and stmt.value is call
        and len(stmt.targets) == 1
        and isinstance(stmt.targets[0], ast.Name)
    ):
        return False
    name = stmt.targets[0].id
    if sum(1 for node in ast.walk(func) if _stores_name(node, name)) != 1 or _returns_name(func, name):
        return False
    folds = 0
    for node in ast.walk(func):
        if not (isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)):
            continue
        parent = parents.get(node)
        if (
            isinstance(parent, ast.Call)
            and isinstance(parent.func, ast.Name)
            and parent.func.id == "len"
            and len(parent.args) == 1
            and parent.args[0] is node
        ):
            continue
        if isinstance(parent, ast.For) and parent.iter is node and _loop_folds(parent, func):
            folds += 1
            continue
        if (
            isinstance(parent, ast.comprehension)
            and parent.iter is node
            and _comprehension_folds(parents, parent, func)
        ):
            folds += 1
            continue
        return False
    return folds > 0


def _is_false_equality(term):
    if not isinstance(term, (ast.List, ast.Tuple)) or len(term.elts) != 3:
        return False
    _field, operator, value = term.elts
    return (
        isinstance(operator, ast.Constant)
        and operator.value == "="
        and isinstance(value, ast.Constant)
        and value.value is False
    )


def _writes(func):
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _WRITE_METHODS:
            return True
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
            return True
    return False


def _loop_folds(loop, func):
    if loop.orelse or any(isinstance(node, (ast.Break, ast.Return)) for node in ast.walk(loop)):
        return False
    collections = set()
    for node in ast.walk(loop):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"append", "add"}
            and isinstance(node.func.value, ast.Name)
        ):
            collections.add(node.func.value.id)
    return bool(collections) and all(_flows_out(func, name) for name in collections)


def _comprehension_folds(parents, generator, func):
    comprehension = parents.get(generator)
    if not isinstance(comprehension, (ast.ListComp, ast.SetComp, ast.DictComp)):
        return False
    stmt = parents.get(comprehension)
    return (
        isinstance(stmt, ast.Assign)
        and stmt.value is comprehension
        and len(stmt.targets) == 1
        and isinstance(stmt.targets[0], ast.Name)
        and _flows_out(func, stmt.targets[0].id)
    )


def _flows_out(func, name):
    """``name`` is read by a returned value or by a raised exception."""
    for node in ast.walk(func):
        value = node.value if isinstance(node, ast.Return) else node.exc if isinstance(node, ast.Raise) else None
        if value is not None and any(
            isinstance(child, ast.Name) and child.id == name and isinstance(child.ctx, ast.Load)
            for child in ast.walk(value)
        ):
            return True
    return False


def _returns_name(func, name):
    for node in ast.walk(func):
        if isinstance(node, ast.Return) and node.value is not None:
            if any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node.value)):
                return True
    return False


def _rebinds(func, name):
    """Whether ``func`` may rebind or mutate ``name`` (dict reads are not mutation)."""
    for node in ast.walk(func):
        if _stores_name(node, name) or (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == name
            and isinstance(node.ctx, (ast.Store, ast.Del))
        ):
            return True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == name
            and node.func.attr not in _DICT_READS
        ):
            return True
        if isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names:
            return True
    return False


def _stores_name(node, name):
    return isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, (ast.Store, ast.Del))


# -- module helpers ---------------------------------------------------------


def _parent_map(root):
    parents = {}
    for node in ast.walk(root):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _parameters(func):
    args = func.args
    names = [arg.arg for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]]
    for extra in (args.vararg, args.kwarg):
        if extra is not None:
            names.append(extra.arg)
    return names


def _unique_function(module, name):
    if module is None:
        return None
    found = [
        node
        for node in ast.walk(module)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    return found[0] if len(found) == 1 else None


def _calls_function(call, name):
    func = call.func
    return (isinstance(func, ast.Attribute) and func.attr == name) or (isinstance(func, ast.Name) and func.id == name)


def _argument_for(call, function, param):
    """The expression ``call`` binds to ``param`` of ``function``, else ``None``."""
    if any(isinstance(arg, ast.Starred) for arg in call.args) or any(kw.arg is None for kw in call.keywords):
        return None
    for keyword in call.keywords:
        if keyword.arg == param:
            return keyword.value
    positional = [arg.arg for arg in [*function.args.posonlyargs, *function.args.args]]
    if param not in positional:
        return None
    offset = 1 if positional and positional[0] in {"self", "cls"} and isinstance(call.func, ast.Attribute) else 0
    position = positional.index(param) - offset
    return call.args[position] if 0 <= position < len(call.args) else None


def _module_string_constants(module):
    """Module-level names assigned exactly once, to a string literal."""
    if module is None:
        return {}
    assigned = {}
    for stmt in module.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    assigned.setdefault(target.id, []).append(stmt.value)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            assigned.setdefault(stmt.target.id, []).append(stmt.value)
    return {
        name: values[0].value
        for name, values in assigned.items()
        if len(values) == 1 and isinstance(values[0], ast.Constant) and isinstance(values[0].value, str)
    }


# -- limit ------------------------------------------------------------------


def _limit_verdict(call, func, module=None):
    """Whether the call's ``limit`` proves a positive bound.

    Odoo 19 ``search(domain, offset=0, limit=None, order=None)`` emits no
    LIMIT for None, False or 0, and PostgreSQL rejects a negative LIMIT, so
    only a provably positive integer bounds the result.
    """
    for keyword in call.keywords:
        if keyword.arg == "limit":
            return _positive_int(keyword.value, func, call, 0, module)
    if len(call.args) >= 3 and not any(isinstance(arg, ast.Starred) for arg in call.args[:3]):
        return _positive_int(call.args[2], func, call, 0, module)
    if any(keyword.arg is None for keyword in call.keywords) or any(isinstance(arg, ast.Starred) for arg in call.args):
        return _UNKNOWN
    return _UNBOUNDED


def _positive_int(node, func, anchor, depth, module=None):
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
                _UNKNOWN if state == _UNKNOWN else _positive_int(state[0], func, state[1], depth + 1, module)
                for state in _reaching(func, node.id, anchor, "value", depth + 1)
            ]
        )
    if isinstance(node, ast.IfExp):
        return _combine_paths(
            [
                _positive_int(node.body, func, anchor, depth + 1, module),
                _positive_int(node.orelse, func, anchor, depth + 1, module),
            ]
        )
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        # ``a or b`` returns the first truthy operand, so a falsy constant is
        # never the result; every other operand must be positive.
        operands = [value for value in node.values[:-1] if not (isinstance(value, ast.Constant) and not value.value)]
        return _combine_paths(
            [_positive_int(value, func, anchor, depth + 1, module) for value in [*operands, node.values[-1]]]
        )
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"max", "min"}
        and node.args
        and not node.keywords
        and not any(isinstance(arg, ast.Starred) for arg in node.args)
    ):
        verdicts = [_positive_int(arg, func, anchor, depth + 1, module) for arg in node.args]
        if node.func.id == "max":
            if _BOUNDED in verdicts:
                return _BOUNDED
            return _UNKNOWN if _UNKNOWN in verdicts else _UNBOUNDED
        return _combine_paths(verdicts)
    if isinstance(node, ast.Call):
        return _page_floor(node, module)
    return _UNKNOWN


def _page_floor(call, module):
    """One level: ``self.<helper>(...)`` where every return is ``max(<expr>, <param>)`` and ``<param>`` is a positive int."""
    func = call.func
    if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "self"):
        return _UNKNOWN
    helper = _unique_function(module, func.attr)
    param = _floor_parameter(helper) if helper is not None else None
    argument = _argument_for(call, helper, param) if param is not None else None
    if isinstance(argument, ast.Constant) and type(argument.value) is int and argument.value > 0:
        return _BOUNDED
    return _UNKNOWN


def _floor_parameter(helper):
    if not _terminates(helper.body):
        return None
    params = _parameters(helper)
    returns = [node for node in _own_nodes(helper) if isinstance(node, ast.Return)]
    chosen = set()
    for node in returns:
        value = node.value
        if not (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "max"
            and len(value.args) == 2
            and not value.keywords
            and not any(isinstance(arg, ast.Starred) for arg in value.args)
        ):
            return None
        floor = value.args[1]
        if not (isinstance(floor, ast.Name) and floor.id in params):
            return None
        chosen.add(floor.id)
    if len(chosen) != 1:
        return None
    param = chosen.pop()
    if any(_touches(stmt, param) for stmt in helper.body):
        return None
    return param


def _own_nodes(func):
    """Nodes of ``func`` outside nested function, lambda and class bodies."""
    stack = list(func.body)
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(node))


# -- domain -----------------------------------------------------------------


def _domain_expr(call):
    domain = None
    for keyword in call.keywords:
        if keyword.arg == "domain":
            domain = keyword.value
    if domain is None and call.args and not isinstance(call.args[0], ast.Starred):
        domain = call.args[0]
    return domain


def _domain_verdict(call, func, module=None):
    """Bound proven by the domain on every execution path, then by the receiver model."""
    domain = _domain_expr(call)
    if domain is None:
        return _UNKNOWN
    paths = _expr_paths(domain, func, call, 0)
    verdict = _combine_paths(
        [_UNKNOWN if path == _UNKNOWN else _elements_verdict(path, func, module) for path in paths]
    )
    if verdict == _BOUNDED:
        return verdict
    model = _receiver_model(call, func, module)
    if _catalog_read(model, paths, func, module) or _partner_mismatch_report(call, func, model, paths):
        return _BOUNDED
    return verdict


def _elements_verdict(elements, func=None, module=None):
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
        return _term_verdict(node, func, module)

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
    if isinstance(node, ast.Constant) and node.value in {"&", "|", "!"}:
        return node.value
    return None


def _term_verdict(term, func=None, module=None):
    if not isinstance(term, (ast.List, ast.Tuple)) or len(term.elts) != 3:
        return _UNKNOWN
    field, operator, value = term.elts
    if isinstance(field, ast.Constant):
        if not isinstance(field.value, str):
            return _UNBOUNDED
        identity = _is_identity_field(field.value)
    else:
        # A non-literal field is a key field only when every name it can take
        # is an identity field; otherwise its meaning is unknown.
        names = _field_names(field, func, module)
        if not names or not all(_is_identity_field(name) for name in names):
            return _UNKNOWN
        identity = True
    if not (isinstance(operator, ast.Constant) and isinstance(operator.value, str)):
        return _UNKNOWN
    if operator.value in _LIKE_OPERATORS:
        return _like_value(value)
    if operator.value not in {"=", "in"}:
        return _UNBOUNDED
    if identity:
        if operator.value == "=":
            return _identity_value(value)
        if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            return _any_of(*[_identity_value(elt) for elt in value.elts]) if value.elts else _BOUNDED
        return _identity_value(value)
    if operator.value == "=":
        return _key_value(value)
    return _key_collection(value)


def _is_identity_field(name):
    return name in {"id", "res_id"} or name.endswith("_id") or name.endswith("_ids")


def _identity_value(node):
    """A non-null record identity: a positive literal id or a dynamic value."""
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


def _key_value(node):
    """``field = value`` on a non-identity field.

    ``False``, ``None`` and booleans are not keys; a string literal is a
    category. Any other non-null value is a key. ``("state", "=", status)``
    with a parameter ``status`` is therefore a key: an accepted hole, because
    that AST is the shape of ``("name", "=", name)``.
    """
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return _BOUNDED
        return _UNBOUNDED
    if isinstance(node, (ast.Name, ast.Attribute, ast.Subscript, ast.Call, ast.JoinedStr, ast.BinOp)):
        return _BOUNDED
    return _UNKNOWN


def _key_collection(node):
    """``field in collection`` on a non-identity field.

    A collection built here (a literal of non-constant elements, or a
    comprehension) is a set of keys. A constant collection is a category. A
    bare name, or ``sorted``/``list``/``set`` around one, is not resolved.
    """
    if isinstance(node, ast.Constant):
        return _UNBOUNDED
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        if not node.elts:
            return _BOUNDED
        return _any_of(*[_key_element(elt) for elt in node.elts])
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        return _UNBOUNDED if isinstance(node.elt, ast.Constant) else _BOUNDED
    return _UNKNOWN


def _key_element(node):
    if isinstance(node, ast.Constant):
        return _UNBOUNDED
    if isinstance(node, ast.Starred):
        return _UNKNOWN
    return _BOUNDED


def _like_value(node):
    """``=like`` / ``=ilike``: a key only for constant strings without ``%`` or ``_``."""
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        if not node.elts:
            return _UNKNOWN
        return _any_of(*[_like_value(elt) for elt in node.elts])
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return _UNBOUNDED if any(mark in node.value for mark in _LIKE_WILDCARDS) else _BOUNDED
        return _UNBOUNDED
    if any(any(mark in part for mark in _LIKE_WILDCARDS) for part in _literal_parts(node)):
        # A visible wildcard is a pattern whatever the hidden part holds.
        return _UNBOUNDED
    return _UNKNOWN


def _literal_parts(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _literal_parts(node.left) + _literal_parts(node.right)
    if isinstance(node, ast.JoinedStr):
        return [part.value for part in node.values if isinstance(part, ast.Constant) and isinstance(part.value, str)]
    return []


# -- identity field names ---------------------------------------------------


def _field_names(node, func, module):
    """String literals a non-literal domain field can name, one level deep, else ``None``.

    Two shapes resolve: a parameter that is never rebound and that every
    same-file call passes as a string literal; and an attribute read from a
    module-level dict of same-file constructors (directly, through a local
    bound to a subscript of it, or through ``next(x.slot for x in D.values())``).
    """
    if func is None or module is None:
        return None
    if isinstance(node, ast.Name):
        if node.id in _parameters(func):
            return _call_site_literals(func, node.id, module)
        names = []
        for state in _reaching(func, node.id, node, "value", 1):
            found = None if state == _UNKNOWN else _slot_literals(state[0], func, state[1], module)
            if found is None:
                return None
            names.extend(found)
        return names or None
    return _slot_literals(node, func, node, module)


def _call_site_literals(func, param, module):
    if any(_touches(stmt, param) for stmt in func.body) or _unique_function(module, func.name) is not func:
        return None
    calls = [node for node in ast.walk(module) if isinstance(node, ast.Call) and _calls_function(node, func.name)]
    if not calls:
        return None
    names = []
    for call in calls:
        argument = _argument_for(call, func, param)
        if not (isinstance(argument, ast.Constant) and isinstance(argument.value, str)):
            return None
        names.append(argument.value)
    return names


def _slot_literals(expr, func, anchor, module):
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return [expr.value]
    if isinstance(expr, ast.Attribute):
        owner = expr.value
        if isinstance(owner, ast.Subscript) and isinstance(owner.value, ast.Name):
            return _dict_slot_literals(owner.value.id, expr.attr, func, module)
        if isinstance(owner, ast.Name) and owner.id not in _parameters(func):
            names = []
            for state in _reaching(func, owner.id, anchor, "value", 1):
                value = None if state == _UNKNOWN else state[0]
                if not (isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name)):
                    return None
                found = _dict_slot_literals(value.value.id, expr.attr, func, module)
                if found is None:
                    return None
                names.extend(found)
            return names or None
        return None
    if (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == "next"
        and len(expr.args) == 1
        and not expr.keywords
        and isinstance(expr.args[0], ast.GeneratorExp)
        and len(expr.args[0].generators) == 1
    ):
        generator = expr.args[0].generators[0]
        element = expr.args[0].elt
        source = generator.iter
        if (
            isinstance(generator.target, ast.Name)
            and isinstance(element, ast.Attribute)
            and isinstance(element.value, ast.Name)
            and element.value.id == generator.target.id
            and isinstance(source, ast.Call)
            and isinstance(source.func, ast.Attribute)
            and source.func.attr == "values"
            and isinstance(source.func.value, ast.Name)
            and not source.args
            and not source.keywords
        ):
            return _dict_slot_literals(source.func.value.id, element.attr, func, module)
    return None


def _dict_slot_literals(name, slot, func, module):
    """String literals in ``slot`` of every constructor in module-level dict ``name``."""
    if name in _parameters(func) or _rebinds(func, name):
        return None
    assigned = [
        stmt
        for stmt in module.body
        if isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in stmt.targets)
    ]
    if len(assigned) != 1 or not isinstance(assigned[0].value, ast.Dict):
        return None
    if any(_stores_name(node, name) for node in ast.walk(module) if node not in assigned[0].targets):
        return None
    classes = {stmt.name: stmt for stmt in module.body if isinstance(stmt, ast.ClassDef)}
    names = []
    for value in assigned[0].value.values:
        if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id in classes):
            return None
        fields = [
            stmt.target.id
            for stmt in classes[value.func.id].body
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
        ]
        if slot not in fields or any(isinstance(arg, ast.Starred) for arg in value.args):
            return None
        argument = next((kw.value for kw in value.keywords if kw.arg == slot), None)
        if argument is None and fields.index(slot) < len(value.args):
            argument = value.args[fields.index(slot)]
        if not (isinstance(argument, ast.Constant) and isinstance(argument.value, str)):
            return None
        names.append(argument.value)
    return names or None


# -- reaching definitions ---------------------------------------------------


def _expr_paths(expr, func, anchor, depth):
    """Possible element sequences of a domain expression at ``anchor``.

    Each path is a tuple of domain elements; ``_UNKNOWN`` marks a path whose
    elements cannot be resolved.
    """
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
