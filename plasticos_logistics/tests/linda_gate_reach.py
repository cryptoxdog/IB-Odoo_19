"""Static witness (S11, C12-SCOPE-2/SCOPE-3): no declared automated entry point reaches a Linda-gated command.

Pure Python, no Odoo import, so it also runs outside the Odoo test runner
(``python3 -I linda_gate_reach.py <repository root>``).

What it covers: every ``ir.cron``, ``base.automation`` and ``ir.actions.server``
``<record>`` in the XML data of the PlasticOS addons, followed through a
name-based call graph of all their Python except ``tests/``, ``migrations/`` and
the operator shell ``scripts/`` (no addon module imports those). A ``self`` or
``cls`` call is followed only to that name on the same class, or, for a
function that is not in a class, to that name in the same module. A bare call,
and an attribute call on any other receiver, is followed only when exactly one
definition of that name exists. ``getattr(obj, "prefix…")`` and
``getattr(obj, f"prefix{…}")`` are followed conservatively: the call reaches
every function and gated command whose name starts with that literal prefix.
An entry point that runs as
``plasticos_logistics.user_linda`` is allowed (the gate then holds its edge
cases); none does today.

What it does not cover, so a clean result is not proof about these:

* implicit ORM dispatch (``create``/``write`` overrides, computed fields,
  onchanges, ``_inherit`` chains reached through framework code) beyond the
  names the graph links by call;
* ``getattr`` with a fully computed name (no literal prefix);
* entry points stored only in the database (crons or server actions created at
  runtime) or declared by non-PlasticOS addons;
* entries declared in CSV data or through ``<function>`` tags;
* calls over RPC, controllers and the mail gateway, which run as their caller
  rather than as a scheduled user.

A ``self.write(...)`` is followed to the ``write`` defined on that same class
or module, builtin-looking names included (C12 round 2, R4). It is not followed
to every other ``write`` in the tree.
"""

import ast
import re
from pathlib import Path
from xml.etree import ElementTree

GATED_COMMANDS = frozenset(
    {
        "action_correct_fact",
        "action_propose_shipment_event",
        "action_accept",
        "action_record_gate_in",
        "action_record_departure",
        "action_record_regulatory_parties",
        "action_record_container_tare",
        "action_record_verified_gross_mass",
        "_record_kind",
        "_correct",
        "action_confirm_ready",
        "action_record_actual_event",
    }
)
ENTRY_MODELS = ("ir.cron", "base.automation", "ir.actions.server")
LINDA_REFS = ("plasticos_logistics.user_linda", "user_linda")
_CALL = re.compile(r"\.\s*(\w+)\s*\(")


def addon_dirs(root):
    return sorted(path for path in Path(root).glob("plasticos_*") if (path / "__manifest__.py").is_file())


def entry_points(root):
    """``[(addon, xml_id, model, user_ref, called_names)]`` for every automated entry record."""
    found = []
    for addon in addon_dirs(root):
        for xml_file in sorted(addon.rglob("*.xml")):
            if "tests" in xml_file.parts:
                continue
            try:
                tree = ElementTree.parse(xml_file)
            except ElementTree.ParseError:
                continue
            for record in tree.iter("record"):
                model = record.get("model")
                if model not in ENTRY_MODELS:
                    continue
                code, user_ref = "", None
                for field in record.iter("field"):
                    if field.get("name") == "code":
                        code += field.text or ""
                    if field.get("name") == "user_id":
                        user_ref = field.get("ref")
                found.append((addon.name, record.get("id"), model, user_ref, set(_CALL.findall(code))))
    return found


def call_graph(root):
    """``{(receiver, name): {calls}}`` over the addons' non-test Python.

    ``receiver`` is the class, qualified by file, or the module itself when the
    function is not inside a class. A call is ``("self", name)``, ``("name", name)``
    or ``("prefix", text)``.
    """
    graph = {}
    for addon in addon_dirs(root):
        for py_file in sorted(addon.rglob("*.py")):
            # scripts/ are piped into ``odoo-bin shell`` by an operator; no addon module imports them.
            if {"tests", "migrations", "scripts"} & set(py_file.relative_to(addon).parts):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for receiver, node in _functions(tree, f"{py_file}"):
                calls = graph.setdefault((receiver, node.name), set())
                calls.update(_calls(node))
    return graph


def _functions(tree, module_key):
    """``[(receiver, function node)]`` without descending into a nested function's body twice."""
    found = []

    def visit(node, receiver):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, f"{module_key}:{child.name}")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.append((receiver, child))
                visit(child, f"{receiver}:{child.name}:{child.lineno}")
            else:
                visit(child, receiver)

    visit(tree, f"{module_key}:<module>")
    return found


def _calls(func_node):
    """Calls in this function, excluding the bodies of functions it defines."""
    calls = set()

    def walk(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(child, ast.Call):
                calls.update(_call_marks(child))
            walk(child)

    walk(func_node)
    return calls


def _call_marks(call):
    func = call.func
    if isinstance(func, ast.Attribute):
        kind = "self" if isinstance(func.value, ast.Name) and func.value.id in {"self", "cls"} else "name"
        return {(kind, func.attr)}
    if isinstance(func, ast.Name):
        marks = {("name", func.id)}
        prefix = _getattr_prefix(call) if func.id == "getattr" else None
        if prefix is not None:
            marks.add(("prefix", prefix))
        return marks
    return set()


def _getattr_prefix(call):
    """The literal leading text of ``getattr``'s name argument, or None when there is none."""
    if len(call.args) < 2:
        return None
    name = call.args[1]
    if isinstance(name, ast.Constant) and isinstance(name.value, str):
        return name.value
    if isinstance(name, ast.JoinedStr) and name.values:
        head = name.values[0]
        if isinstance(head, ast.Constant) and isinstance(head.value, str):
            return head.value
        return ""
    return None


def _by_name(graph):
    found = {}
    for _receiver, name in graph:
        found.setdefault(name, []).append(_receiver)
    return found


def _targets(graph, by_name, receiver, kind, target):
    """Definitions a call may enter, and names that are themselves the next hop."""
    if kind == "prefix":
        hops = [(found, name) for (found, name) in graph if name.startswith(target)]
        defined = {name for (_found, name) in hops}
        missing = [
            command for command in sorted(GATED_COMMANDS) if command.startswith(target) and command not in defined
        ]
        hops.extend((None, command) for command in missing)
        return hops
    if kind == "self":
        return [(receiver, target)]
    receivers = by_name.get(target, [])
    if len(receivers) == 1:
        return [(receivers[0], target)]
    if target in GATED_COMMANDS:
        return [(None, target)]
    return []


def gated_paths(root):
    """``[(entry xml id, gated command, call chain)]`` for every non-Linda entry that reaches a gated command."""
    graph = call_graph(root)
    by_name = _by_name(graph)
    hits = []
    for _addon, xml_id, _model, user_ref, names in entry_points(root):
        if user_ref in LINDA_REFS:
            continue
        seen = set()
        queue = []
        for name in sorted(names):
            if name in GATED_COMMANDS:
                hits.append((xml_id, name, (name,)))
                continue
            queue.extend((found, name, (name,)) for found in by_name.get(name, []))
        while queue:
            receiver, name, chain = queue.pop(0)
            hop = (receiver, name)
            if hop in seen:
                continue
            seen.add(hop)
            if name in GATED_COMMANDS:
                hits.append((xml_id, name, chain))
                continue
            for kind, target in sorted(graph.get(hop, ())):
                for next_receiver, next_name in _targets(graph, by_name, receiver, kind, target):
                    if next_name in GATED_COMMANDS:
                        hit = (xml_id, next_name, (*chain, next_name))
                        if hit not in hits:
                            hits.append(hit)
                        continue
                    if (next_receiver, next_name) not in seen:
                        queue.append((next_receiver, next_name, (*chain, next_name)))
    return hits


if __name__ == "__main__":
    import sys

    repository = sys.argv[1] if len(sys.argv) > 1 else "."
    found = gated_paths(repository)
    print(f"{len(entry_points(repository))} entry points, {len(found)} gated paths")
    for hit in found:
        print(hit)
    sys.exit(1 if found else 0)
