#!/usr/bin/env python3
"""
Odoo Comprehensive Bug Audit
============================
Runs all checks and generates unified report.

Combines all audit categories:
1. Field Name Mismatches
2. Required Field Violations
3. Compute/Depends Errors
4. Security/Access Control Gaps
5. Constraint Violations
6. State Machine Errors
7. Onchange/API Errors

Usage:
    python3 scripts/audit/odoo_audit.py [root_dir]

Known False Positive Patterns (for code review agents)
------------------------------------------------------
1. INVALID_DEPENDS for inherited fields:
   - Fields like `document_ids` may be defined via `_inherit` in bridge modules
   - Example: `plasticos_documents/models/transaction_docs_bridge.py` adds
     `document_ids` to `plasticos.transaction` via inheritance
   - The audit now tracks `_inherit` files to reduce these false positives

2. MISSING_ACL for AbstractModel/TransientModel:
   - Service classes using `models.AbstractModel` don't create database tables
   - They don't need ir.model.access.csv entries
   - Examples: plasticos.graph.service, plasticos.compliance.service
   - The audit now skips AbstractModel and TransientModel classes

3. FIELD_NOT_FOUND attribution (view field check):
   - Only `<field>` elements inside the `arch` of an `ir.ui.view` record are
     view references. Fields of other records (`ir.actions.*`, `ir.cron`, ...)
     are that record's own data, not fields of the model a view displays.
   - A `<field>` that holds a subview (`<list>`, `<form>`, `<kanban>`, ...) or an
     `<xpath>` that targets one switches the context to the field's comodel.
     When the comodel cannot be resolved the subtree is reported as
     UNRESOLVED_VIEW_CONTEXT (HIGH, so the baseline gate fails closed on the
     coverage gap) instead of being charged to the parent. An unreadable view
     file is VIEW_PARSE_ERROR (HIGH) for the same reason.
   - A model's fields are the fields of every class that defines or extends it
     (`_name`, `_inherit` string or list) in the view's module and its manifest
     `depends` closure, plus prototype parents resolved the same way. Only the
     verified Odoo 19 `mail.thread` / `mail.activity.mixin` fields are known
     outside the repository; any other unresolved parent leaves its fields
     unknown, so references to them still fail.

4. Magic fields (create_date, write_date, etc.):
   - These exist on all Odoo models automatically
   - The audit excludes them from INVALID_DEPENDS checks
"""

import ast
import json
import re
import sys
import xml.parsers.expat
from collections import defaultdict
from pathlib import Path

from path_filters import skip_path


class OdooAudit:
    """Comprehensive Odoo codebase auditor.

    Limitations:
    - The view field check resolves ``_inherit`` extensions per class (see
      ``scan_model_index``). The depends / constraint / onchange checks still
      use the first ``_name`` per file and do not see extension fields.
    - Does not track fields from Odoo core models (res.partner, etc.); views of
      models no repo class defines are not checked.
    """

    MAGIC_FIELDS = frozenset(
        {
            "id",
            "create_uid",
            "create_date",
            "write_uid",
            "write_date",
            "display_name",
            "__last_update",
            "active",
            "name",
        }
    )

    # Verified against odoo/odoo@19.0 addons/mail/models/mail_thread.py and
    # mail_activity_mixin.py. These are the only framework parents whose fields
    # the view check knows; every other parent outside the repo stays unresolved.
    FRAMEWORK_MIXIN_FIELDS = {
        "mail.thread": frozenset(
            {
                "message_is_follower",
                "message_follower_ids",
                "message_partner_ids",
                "message_ids",
                "has_message",
                "message_needaction",
                "message_needaction_counter",
                "message_has_error",
                "message_has_error_counter",
                "message_attachment_count",
            }
        ),
        "mail.activity.mixin": frozenset(
            {
                "activity_ids",
                "activity_state",
                "activity_user_id",
                "activity_type_id",
                "activity_type_icon",
                "activity_date_deadline",
                "my_activity_date_deadline",
                "activity_summary",
                "activity_exception_decoration",
                "activity_exception_icon",
            }
        ),
    }

    RELATIONAL_TYPES = frozenset({"Many2one", "One2many", "Many2many"})
    SUBVIEW_TAGS = frozenset({"list", "tree", "form", "kanban", "graph", "pivot", "calendar", "activity"})

    ODOO_CORE_MODELS = frozenset(
        {
            "res.partner",
            "res.users",
            "res.company",
            "res.country",
            "res.currency",
            "crm.lead",
            "sale.order",
            "purchase.order",
            "account.move",
            "stock.picking",
            "product.product",
            "product.template",
        }
    )

    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)
        self.model_fields = defaultdict(dict)  # model_name -> {field: type}
        self.inherited_fields = defaultdict(dict)  # model_name -> {field: type} (from _inherit)
        self.field_refs = defaultdict(list)  # (model, field) -> [(file, line)]
        self.all_models = set()  # (model_name, py_file, is_abstract)
        self.state_models = {}  # model_name -> {field, values}
        self.model_classes = []  # one entry per model class: {model, module, parents, fields, defines}
        self.defined_models = set()  # models created by a class in the repo (``_name`` not an extension)
        self.unresolved_view_contexts = []  # subviews whose comodel could not be resolved
        self.view_parse_errors = []  # view files the field check could not read
        self._depends_cache = {}
        self._fields_cache = {}

    def scan_model_fields(self):
        """Extract all field definitions from Python models."""
        for py_file in self.root_dir.rglob("*/models/*.py"):
            if skip_path(py_file):
                continue
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            model_match = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', content)
            inherit_match = re.search(r'_inherit\s*=\s*["\']([^"\']+)["\']', content)

            if inherit_match and not model_match:
                inherited_model = inherit_match.group(1)
                for match in re.finditer(
                    r"(\w+)\s*=\s*fields\.(Char|Integer|Float|Boolean|Date|Datetime|"
                    r"Many2one|One2many|Many2many|Selection|Text|Html|Binary|Json|Monetary|Reference|Image)",
                    content,
                ):
                    field_name = match.group(1)
                    field_type = match.group(2)
                    self.inherited_fields[inherited_model][field_name] = {"type": field_type}
                continue

            if not model_match:
                continue

            model_name = model_match.group(1)
            is_abstract = "AbstractModel" in content or "TransientModel" in content
            if not model_name.startswith("_"):
                self.all_models.add((model_name, str(py_file), is_abstract))

            for match in re.finditer(
                r"(\w+)\s*=\s*fields\.(Char|Integer|Float|Boolean|Date|Datetime|"
                r"Many2one|One2many|Many2many|Selection|Text|Html|Binary|Json|Monetary|Reference|Image)",
                content,
            ):
                field_name = match.group(1)
                field_type = match.group(2)
                self.model_fields[model_name][field_name] = {"type": field_type}

                if "required=True" in content[match.end() : match.end() + 200]:
                    self.model_fields[model_name][field_name]["required"] = True

            state_match = re.search(
                r"(state|status)\s*=\s*fields\.Selection\(\s*\[(.*?)\]",
                content,
                re.DOTALL,
            )
            if state_match:
                field_name = state_match.group(1)
                values_text = state_match.group(2)
                states = re.findall(r'["\']([^"\']+)["\']', values_text)
                self.state_models[model_name] = {
                    "field": field_name,
                    "values": set(states[::2]) if states else set(),
                }

    # ── Model index (view field check) ─────────────────────────────────────

    @staticmethod
    def _module_of(path):
        """Addon directory of a ``<addon>/models/*.py`` or ``<addon>/views/*.xml`` file."""
        return str(Path(path).parent.parent)

    @staticmethod
    def _string_value(node, constants):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return constants.get(node.id)
        return None

    def _string_list(self, node, constants):
        if isinstance(node, (ast.List, ast.Tuple)):
            values = [self._string_value(item, constants) for item in node.elts]
            return [value for value in values if value]
        value = self._string_value(node, constants)
        return [value] if value else []

    def _field_comodel(self, call, field_type, constants):
        if field_type not in self.RELATIONAL_TYPES:
            return None
        for keyword in call.keywords:
            if keyword.arg == "comodel_name":
                return self._string_value(keyword.value, constants)
        if call.args:
            return self._string_value(call.args[0], constants)
        return None

    def scan_model_index(self):
        """Index every model class: resolved model name, module, parents and fields."""
        for py_file in sorted(self.root_dir.rglob("*/models/*.py")):
            if skip_path(py_file):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            constants = {}
            for node in tree.body:
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    value = self._string_value(node.value, {})
                    if value:
                        constants[node.targets[0].id] = value
            module = self._module_of(py_file)
            for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
                name = None
                parents = []
                fields = {}
                for stmt in cls.body:
                    if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1):
                        continue
                    target = stmt.targets[0]
                    if not isinstance(target, ast.Name):
                        continue
                    if target.id == "_name":
                        name = self._string_value(stmt.value, constants)
                    elif target.id == "_inherit":
                        parents = self._string_list(stmt.value, constants)
                    elif (
                        isinstance(stmt.value, ast.Call)
                        and isinstance(stmt.value.func, ast.Attribute)
                        and isinstance(stmt.value.func.value, ast.Name)
                        and stmt.value.func.value.id == "fields"
                    ):
                        field_type = stmt.value.func.attr
                        fields[target.id] = self._field_comodel(stmt.value, field_type, constants)
                model = name or (parents[0] if len(parents) == 1 else None)
                if not model:
                    continue
                defines = bool(name) and name not in parents
                self.model_classes.append(
                    {
                        "model": model,
                        "module": module,
                        "parents": [parent for parent in parents if parent != model],
                        "fields": fields,
                        "defines": defines,
                    }
                )
                if defines:
                    self.defined_models.add(model)

    def _depends_closure(self, module):
        """The module plus every module reachable through manifest ``depends``.

        ``module`` is an addon path as ``rglob`` under ``root_dir`` yields it, so it
        already carries the root; it is never joined to ``root_dir`` again.
        """
        if module in self._depends_cache:
            return self._depends_cache[module]
        closure = set()
        pending = [module]
        while pending:
            current = pending.pop()
            if current in closure:
                continue
            closure.add(current)
            try:
                data = ast.literal_eval((Path(current) / "__manifest__.py").read_text(encoding="utf-8"))
            except (OSError, SyntaxError, ValueError):
                continue
            depends = data.get("depends", []) if isinstance(data, dict) else []
            parent_dir = Path(current).parent
            pending.extend(str(parent_dir / dep) for dep in depends if isinstance(dep, str))
        self._depends_cache[module] = closure
        return closure

    def _visible_fields(self, model, module, _seen=None):
        """Fields of ``model`` visible from ``module``: ``{field: comodel_or_None}``."""
        key = (model, module)
        if _seen is None and key in self._fields_cache:
            return self._fields_cache[key]
        seen = set() if _seen is None else _seen
        if model in seen:
            return {}
        seen.add(model)
        closure = self._depends_closure(module)
        fields = dict.fromkeys(self.FRAMEWORK_MIXIN_FIELDS.get(model, ()))
        for cls in self.model_classes:
            if cls["model"] != model or cls["module"] not in closure:
                continue
            for parent in cls["parents"]:
                for field, comodel in self._visible_fields(parent, module, seen).items():
                    fields.setdefault(field, comodel)
            for field, comodel in cls["fields"].items():
                if comodel or field not in fields:
                    fields[field] = comodel
        if _seen is None:
            self._fields_cache[key] = fields
        return fields

    # ── View field references ──────────────────────────────────────────────

    @staticmethod
    def _parse_xml(xml_file):
        """Parse to ``{"tag", "attrs", "line", "text", "children"}`` nodes, keeping line numbers."""
        root = {"tag": None, "attrs": {}, "line": 0, "text": "", "children": []}
        stack = [root]
        parser = xml.parsers.expat.ParserCreate()

        def start(tag, attrs):
            node = {"tag": tag, "attrs": attrs, "line": parser.CurrentLineNumber, "text": "", "children": []}
            stack[-1]["children"].append(node)
            stack.append(node)

        def end(_tag):
            stack.pop()

        def text(data):
            stack[-1]["text"] += data

        parser.StartElementHandler = start
        parser.EndElementHandler = end
        parser.CharacterDataHandler = text
        parser.Parse(Path(xml_file).read_bytes(), True)
        return root

    @staticmethod
    def _iter_records(node):
        for child in node["children"]:
            if child["tag"] == "record":
                yield child
            else:
                yield from OdooAudit._iter_records(child)

    def _xpath_context(self, expr, model, module):
        """``(model, target_field)`` an ``<xpath>`` body is evaluated against.

        A subview step (``/list``, ``/form``, ...) after a field step switches to
        that field's comodel. A subview word that is not a location step (an axis
        such as ``ancestor::form``, or text such as ``hasclass('form-group')``)
        does not. ``target_field`` is set only when the expression ends on a field
        step: a subview inserted directly into it is evaluated on that field's
        comodel.
        """
        context = model
        pending_field = None
        field_end = None
        steps = r"field\[@name=['\"]([\w.]+)['\"]\]|(?:(?<=/)|^)(" + "|".join(self.SUBVIEW_TAGS) + r")(?![\w:\-])"
        for match in re.finditer(steps, expr):
            if match.group(1):
                pending_field = match.group(1)
                field_end = match.end()
            elif pending_field:
                context = self._comodel(context, pending_field, module)
                pending_field = None
                if context is None:
                    return None, None
        if pending_field and expr[field_end:].strip() == "":
            return context, pending_field
        return context, None

    def _comodel(self, model, field, module):
        if model is None:
            return None
        return self._visible_fields(model, module).get(field)

    def _walk_field_body(self, node, model, field, module, xml_file):
        """Walk the children of ``field`` on ``model``: a subview child is evaluated on the field's comodel."""
        for child in node["children"]:
            if child["tag"] in self.SUBVIEW_TAGS:
                comodel = self._comodel(model, field, module)
                if comodel is None and model in self.defined_models:
                    self.unresolved_view_contexts.append(
                        {"model": model, "field": field, "file": str(xml_file), "line": child["line"]}
                    )
                self._walk_arch({"children": [child]}, comodel, module, xml_file)
            else:
                self._walk_arch({"children": [child]}, model, module, xml_file)

    def _walk_arch(self, node, model, module, xml_file):
        for child in node["children"]:
            tag = child["tag"]
            if tag == "field" and child["attrs"].get("name"):
                field = child["attrs"]["name"]
                if model is not None:
                    self.field_refs[(model, field)].append(
                        {"file": str(xml_file), "line": child["line"], "module": module}
                    )
                self._walk_field_body(child, model, field, module, xml_file)
            elif tag == "xpath":
                expr = child["attrs"].get("expr", "")
                context, target_field = self._xpath_context(expr, model, module)
                if context is None and model in self.defined_models:
                    self.unresolved_view_contexts.append(
                        {"model": model, "field": expr, "file": str(xml_file), "line": child["line"]}
                    )
                if target_field and context is not None:
                    self._walk_field_body(child, context, target_field, module, xml_file)
                else:
                    self._walk_arch(child, context, module, xml_file)
            else:
                self._walk_arch(child, model, module, xml_file)

    def scan_view_field_refs(self):
        """Find every ``<field name="...">`` in ``ir.ui.view`` arch, attributed to the model it is evaluated on."""
        views = {}
        pending = []
        for xml_file in sorted(self.root_dir.rglob("*/views/*.xml")):
            if skip_path(xml_file):
                continue
            try:
                root = self._parse_xml(xml_file)
            except (OSError, xml.parsers.expat.ExpatError) as exc:
                self.view_parse_errors.append({"file": str(xml_file), "error": str(exc)})
                continue
            module = self._module_of(xml_file)
            module_name = Path(module).name
            for record in self._iter_records(root):
                if record["attrs"].get("model") != "ir.ui.view":
                    continue
                fields = {child["attrs"].get("name"): child for child in record["children"] if child["tag"] == "field"}
                xmlid = record["attrs"].get("id", "")
                if xmlid and "." not in xmlid:
                    xmlid = f"{module_name}.{xmlid}"
                model = fields["model"]["text"].strip() if "model" in fields else None
                inherit = fields["inherit_id"]["attrs"].get("ref") if "inherit_id" in fields else None
                if inherit and "." not in inherit:
                    inherit = f"{module_name}.{inherit}"
                views[xmlid] = {"model": model, "inherit": inherit}
                if "arch" in fields:
                    pending.append((xmlid, fields["arch"], module, xml_file))

        def resolve(xmlid, seen=()):
            view = views.get(xmlid)
            if view is None or xmlid in seen:
                return None
            return view["model"] or resolve(view["inherit"], (*seen, xmlid))

        for xmlid, arch, module, xml_file in pending:
            self._walk_arch(arch, resolve(xmlid), module, xml_file)

    def check_field_mismatches(self):
        """Find view field references that no visible class of the model defines."""
        errors = []
        for (model, field), refs in self.field_refs.items():
            if model not in self.defined_models:
                continue
            if field in self.MAGIC_FIELDS:
                continue
            for ref in refs:
                fields = self._visible_fields(model, ref["module"])
                if field in fields:
                    continue
                suggestions = []
                if f"{field}_id" in fields:
                    suggestions.append(f"{field}_id")
                if field.endswith("_id") and field[:-3] in fields:
                    suggestions.append(field[:-3])
                errors.append(
                    {
                        "type": "FIELD_NOT_FOUND",
                        "severity": "CRITICAL",
                        "model": model,
                        "field": field,
                        "file": ref["file"],
                        "line": ref["line"],
                        "message": f"Field '{field}' not defined on model '{model}'",
                        "suggestions": suggestions or "No obvious match found",
                    }
                )
        return errors

    def check_unresolved_view_contexts(self):
        """Subviews whose comodel could not be resolved, and unreadable view files: their fields are not checked."""
        return [
            {
                "type": "UNRESOLVED_VIEW_CONTEXT",
                "severity": "HIGH",
                "model": item["model"],
                "field": item["field"],
                "file": item["file"],
                "line": item["line"],
                "message": f"Subview of '{item['field']}' on '{item['model']}' has no resolvable comodel; "
                "its fields are not checked",
            }
            for item in self.unresolved_view_contexts
        ] + [
            {
                "type": "VIEW_PARSE_ERROR",
                "severity": "HIGH",
                "file": item["file"],
                "message": f"View file not parsed; its fields are not checked: {item['error']}",
            }
            for item in self.view_parse_errors
        ]

    def check_compute_depends(self):
        """Validate @api.depends() field references."""
        errors = []
        for py_file in self.root_dir.rglob("*/models/*.py"):
            if skip_path(py_file):
                continue
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            model_match = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', content)
            if not model_match:
                continue
            model_name = model_match.group(1)

            for match in re.finditer(r"@api\.depends\(([^)]+)\)\s+def\s+(\w+)", content, re.MULTILINE):
                depends_args = match.group(1)
                compute_method = match.group(2)
                field_names = re.findall(r'["\']([^"\']+)["\']', depends_args)

                for field_path in field_names:
                    base_field = field_path.split(".")[0]
                    if base_field in self.MAGIC_FIELDS:
                        continue
                    if base_field in self.model_fields.get(model_name, {}):
                        continue
                    if base_field in self.inherited_fields.get(model_name, {}):
                        continue
                    line_num = content[: match.start()].count("\n") + 1
                    errors.append(
                        {
                            "type": "INVALID_DEPENDS",
                            "severity": "HIGH",
                            "model": model_name,
                            "compute_method": compute_method,
                            "field": base_field,
                            "file": str(py_file),
                            "line": line_num,
                            "message": f"@api.depends references non-existent field '{base_field}'",
                            "note": "May be inherited from another module (_inherit)",
                        }
                    )
        return errors

    def check_security_rules(self):
        """Find models without ACL definitions."""
        errors = []
        secured_models = set()

        for csv_file in self.root_dir.rglob("*/security/*.csv"):
            if skip_path(csv_file):
                continue
            try:
                with open(csv_file, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue
            for match in re.finditer(r"model_([a-z_0-9]+)", content):
                model_name = match.group(1).replace("_", ".")
                secured_models.add(model_name)

        for model_name, py_file, is_abstract in self.all_models:
            if model_name in secured_models:
                continue
            if is_abstract:
                continue
            if model_name in self.ODOO_CORE_MODELS:
                continue
            errors.append(
                {
                    "type": "MISSING_ACL",
                    "severity": "HIGH",
                    "model": model_name,
                    "file": py_file,
                    "message": f"Model '{model_name}' has no ir.model.access.csv entry",
                    "fix": "Add ACL rules in security/ir.model.access.csv",
                }
            )
        return errors

    def check_constraints(self):
        """Validate constraint decorators and SQL constraints."""
        errors = []
        for py_file in self.root_dir.rglob("*/models/*.py"):
            if skip_path(py_file):
                continue
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            model_match = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', content)
            if not model_match:
                continue
            model_name = model_match.group(1)

            for match in re.finditer(r"@api\.constrains\(([^)]+)\)", content):
                constraint_fields = re.findall(r'["\']([^"\']+)["\']', match.group(1))
                for field in constraint_fields:
                    if field not in self.model_fields.get(model_name, {}):
                        line_num = content[: match.start()].count("\n") + 1
                        errors.append(
                            {
                                "type": "INVALID_CONSTRAINT_FIELD",
                                "severity": "HIGH",
                                "model": model_name,
                                "field": field,
                                "file": str(py_file),
                                "line": line_num,
                                "message": f"@api.constrains references non-existent field '{field}'",
                            }
                        )
        return errors

    def check_onchange_methods(self):
        """Validate @api.onchange decorators."""
        errors = []
        for py_file in self.root_dir.rglob("*/models/*.py"):
            if skip_path(py_file):
                continue
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            model_match = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', content)
            if not model_match:
                continue
            model_name = model_match.group(1)

            for match in re.finditer(r"@api\.onchange\(([^)]+)\)\s+def\s+(\w+)", content):
                onchange_fields = re.findall(r'["\']([^"\']+)["\']', match.group(1))
                method_name = match.group(2)

                for field in onchange_fields:
                    if field not in self.model_fields.get(model_name, {}):
                        line_num = content[: match.start()].count("\n") + 1
                        errors.append(
                            {
                                "type": "INVALID_ONCHANGE_FIELD",
                                "severity": "HIGH",
                                "model": model_name,
                                "method": method_name,
                                "field": field,
                                "file": str(py_file),
                                "line": line_num,
                                "message": f"@api.onchange references non-existent field '{field}'",
                            }
                        )
        return errors

    def check_state_machine(self):
        """Validate state field and button visibility."""
        errors = []
        for xml_file in self.root_dir.rglob("*/views/*.xml"):
            if skip_path(xml_file):
                continue
            try:
                with open(xml_file, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            current_model = None
            for line_num, line in enumerate(content.split("\n"), 1):
                model_match = re.search(r'<field name="model">([^<]+)</field>', line)
                if model_match:
                    current_model = model_match.group(1)
                    continue

                if "<button" in line and "invisible=" in line:
                    inv_match = re.search(r'invisible="([^"]+)"', line)
                    if inv_match and current_model and current_model in self.state_models:
                        condition = inv_match.group(1)
                        valid_states = self.state_models[current_model]["values"]
                        for state in re.findall(r"'(\w+)'", condition):
                            if state not in valid_states and valid_states:
                                errors.append(
                                    {
                                        "type": "INVALID_STATE_VALUE",
                                        "severity": "MODERATE",
                                        "model": current_model,
                                        "invalid_state": state,
                                        "file": str(xml_file),
                                        "line": line_num,
                                        "message": f"Button condition references invalid state '{state}'",
                                        "valid_states": list(valid_states),
                                    }
                                )
        return errors

    def run_all_checks(self):
        """Run all audit checks."""
        print("🔍 Scanning model fields...")
        self.scan_model_fields()
        print(f"   Found {len(self.model_fields)} models with {sum(len(f) for f in self.model_fields.values())} fields")

        print("🔍 Indexing model classes...")
        self.scan_model_index()
        print(f"   Found {len(self.model_classes)} model classes for {len(self.defined_models)} defined models")

        print("🔍 Scanning view field references...")
        self.scan_view_field_refs()
        print(f"   Found {len(self.field_refs)} field references")

        all_errors = []
        checks = [
            ("Field Mismatches", self.check_field_mismatches),
            ("Unresolved View Contexts", self.check_unresolved_view_contexts),
            ("Compute Depends", self.check_compute_depends),
            ("Security Rules", self.check_security_rules),
            ("Constraints", self.check_constraints),
            ("Onchange Methods", self.check_onchange_methods),
            ("State Machines", self.check_state_machine),
        ]

        for check_name, check_func in checks:
            print(f"🔍 Running: {check_name}...")
            errors = check_func()
            all_errors.extend(errors)
            print(f"   Found {len(errors)} issues")

        return all_errors


def main():
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    auditor = OdooAudit(root_dir)
    errors = auditor.run_all_checks()

    critical = [e for e in errors if e["severity"] == "CRITICAL"]
    high = [e for e in errors if e["severity"] == "HIGH"]
    moderate = [e for e in errors if e["severity"] == "MODERATE"]

    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    print(f"Total Issues: {len(errors)}")
    print(f"  CRITICAL: {len(critical)}")
    print(f"  HIGH: {len(high)}")
    print(f"  MODERATE: {len(moderate)}")

    with open("odoo_audit_report.json", "w") as f:
        json.dump(errors, f, indent=2)
    print("\n📄 JSON report saved to odoo_audit_report.json")

    with open("AUDIT_REPORT.md", "w") as f:
        f.write("# Odoo Codebase Audit Report\n\n")
        f.write(f"**Total Issues:** {len(errors)}\n")
        f.write(f"- CRITICAL: {len(critical)}\n")
        f.write(f"- HIGH: {len(high)}\n")
        f.write(f"- MODERATE: {len(moderate)}\n\n")

        for severity in ["CRITICAL", "HIGH", "MODERATE"]:
            severity_errors = [e for e in errors if e["severity"] == severity]
            if severity_errors:
                f.write(f"## {severity} Issues\n\n")
                for error in severity_errors:
                    f.write(f"### {error['type']}\n")
                    f.write(f"- **Model:** {error.get('model', 'N/A')}\n")
                    f.write(f"- **Message:** {error['message']}\n")
                    f.write(f"- **File:** `{error['file']}:{error.get('line', 'N/A')}`\n")
                    if "fix" in error:
                        f.write(f"- **Fix:** {error['fix']}\n")
                    if "suggestions" in error and error["suggestions"]:
                        f.write(f"- **Suggestions:** {error['suggestions']}\n")
                    f.write("\n")

    print("📄 Markdown report saved to AUDIT_REPORT.md")

    if critical:
        print(f"\n❌ {len(critical)} CRITICAL issues found!")
        sys.exit(1)
    elif high:
        print(f"\n⚠️  {len(high)} HIGH issues found (no critical)")
        sys.exit(0)
    else:
        print("\n✅ No critical or high issues found!")
        sys.exit(0)


if __name__ == "__main__":
    main()
