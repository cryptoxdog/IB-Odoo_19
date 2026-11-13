"""Static witness (S11, C12-SCOPE-2/SCOPE-3): no declared automated entry point reaches a Linda-gated command.

Pure Python, no Odoo import, so it also runs outside the Odoo test runner
(``python3 -I linda_gate_reach.py <repository root>``).

What it covers: every ``ir.cron``, ``base.automation`` and ``ir.actions.server``
``<record>`` in the XML data of the PlasticOS addons, followed through a
name-based call graph of all their Python except ``tests/``, ``migrations/`` and
the operator shell ``scripts/`` (no addon module imports those). A function
name stands for every definition with that name, so it over-approximates.
``getattr(obj, "prefix…")`` and ``getattr(obj, f"prefix{…}")`` are followed
conservatively: the call reaches every function and gated command whose name
starts with that literal prefix. An entry point that runs as
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

Every call is followed by name, builtin-looking ones included (``write``, ``get``,
``append``…), so a ``self.write(...)`` reaching a PlasticOS ``write`` override is
followed (C12 round 2, R4).
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
    """``{function name: {called attribute or function names}}`` over the addons' non-test Python."""
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
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                calls = graph.setdefault(node.name, set())
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Call):
                        func = inner.func
                        if isinstance(func, ast.Attribute):
                            calls.add(func.attr)
                        elif isinstance(func, ast.Name):
                            calls.add(func.id)
                            prefix = _getattr_prefix(inner) if func.id == "getattr" else None
                            if prefix is not None:
                                calls.add(PREFIX_MARK + prefix)
    return graph


PREFIX_MARK = "getattr-prefix:"


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


def _callees(graph, name):
    """Who ``name`` calls; a getattr prefix reaches every function and gated command it can name."""
    if name.startswith(PREFIX_MARK):
        prefix = name[len(PREFIX_MARK) :]
        return sorted({candidate for candidate in (*graph, *GATED_COMMANDS) if candidate.startswith(prefix)})
    return sorted(graph.get(name, ()))


def gated_paths(root):
    """``[(entry xml id, gated command, call chain)]`` for every non-Linda entry that reaches a gated command."""
    graph = call_graph(root)
    hits = []
    for _addon, xml_id, _model, user_ref, names in entry_points(root):
        if user_ref in LINDA_REFS:
            continue
        seen = {}
        queue = [(name, (name,)) for name in sorted(names)]
        while queue:
            name, chain = queue.pop(0)
            if name in seen:
                continue
            seen[name] = chain
            if name in GATED_COMMANDS:
                hits.append((xml_id, name, chain))
                continue
            queue.extend((callee, (*chain, callee)) for callee in _callees(graph, name) if callee not in seen)
    return hits


if __name__ == "__main__":
    import sys

    repository = sys.argv[1] if len(sys.argv) > 1 else "."
    found = gated_paths(repository)
    print(f"{len(entry_points(repository))} entry points, {len(found)} gated paths")
    for hit in found:
        print(hit)
    sys.exit(1 if found else 0)
