"""Static witness (S11, C12-SCOPE-2): no scheduled or automated entry point reaches a Linda-gated command.

Pure Python, no Odoo import, so it also runs outside the Odoo test runner.

Entry points are every ``ir.cron``, ``base.automation`` and ``ir.actions.server``
record declared in the XML data of the PlasticOS addons: the method names their
``code`` calls. The call graph is name-based over every non-test Python file of
those addons (a function name stands for every definition with that name), so it
over-approximates reach: a path it does not find does not exist by name. An
entry point that runs as ``plasticos_logistics.user_linda`` would be allowed
(the gate then holds its edge cases); none does today.
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
            if {"tests", "migrations"} & set(py_file.parts):
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
    return graph


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
            queue.extend((callee, (*chain, callee)) for callee in sorted(graph.get(name, ())) if callee not in seen)
    return hits
