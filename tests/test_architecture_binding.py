"""Every test must bind to architecture that currently exists.

Zero Odoo runtime — pure AST over the addon tree and the test tree.

Why this exists
---------------
39 of the test modules in ``tests/`` import Odoo. ``tests/conftest.py``
collect-ignores all of them under a pure-Python pytest run (CI Tier 3), and
``tests/__manifest__.py`` is ``installable: False``, so they do not run under
``odoo --test-enable`` either. Roughly 570 test cases therefore execute nowhere
in CI, and drifted silently for as long as that was true. The 2026-08
reconciliation found, among others:

  * ``plasticos.transaction.claim`` — a join model that never existed; the bridge
    is fields on ``plasticos.transaction``.
  * ``plasticos.graph.service`` / ``plasticos.graph.sync.log`` — mothballed
    (scripts/migrations/mothball_local_intelligence.py DISCARDABLE_CATALOG).
  * ``plasticos.offer.buyer_partner_id`` / ``total_lbs`` — renamed to ``buyer_id``
    / ``quantity_lbs``.
  * ``plasticos.load.origin_partner_id`` / ``destination_partner_id`` — renamed to
    ``pickup_partner_id`` / ``delivery_partner_id``.
  * ``plasticos.claim.case_type = "quality"`` — not in the Selection.

None of those could fail a build, because nothing ran them. This module closes
that gap: it is pure-Python, so it runs on every push, and it fails when a test
names a plasticos model, field, or Selection value that the addons do not define.

It complements ``test_phantom_enum_values.py``, which scans only directories
named ``plasticos_*`` and so has never been able to see the test tree at all.

Scope: ``plasticos.*`` models only. Core Odoo models (``res.partner``,
``account.move``, …) are defined outside this repository, so their fields cannot
be resolved here and are not checked.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"

# Fields every Odoo model inherits from the ORM or from common mixins
# (mail.thread / mail.activity.mixin), which are not declared in this repo.
INHERITED_FIELDS = frozenset(
    {
        "id",
        "display_name",
        "create_date",
        "create_uid",
        "write_date",
        "write_uid",
        "message_ids",
        "message_follower_ids",
        "message_partner_ids",
        "message_main_attachment_id",
        "activity_ids",
        "activity_state",
        "activity_user_id",
    }
)


# ═════════════════════════════════════════════════════════════════════════
# Registry: models, fields, and Selection values declared by plasticos_* addons
# ═════════════════════════════════════════════════════════════════════════


def _addon_python_files():
    for entry in sorted(REPO_ROOT.iterdir()):
        if not (entry.name.startswith("plasticos_") and (entry / "__manifest__.py").is_file()):
            continue
        for path in sorted(entry.rglob("*.py")):
            if "__pycache__" not in path.parts:
                yield path


def _class_model_names(cls: ast.ClassDef) -> list[str]:
    """Model names this class contributes to, via _name or _inherit."""
    names: list[str] = []
    for stmt in cls.body:
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1):
            continue
        target = stmt.targets[0]
        if not (isinstance(target, ast.Name) and target.id in ("_name", "_inherit")):
            continue
        value = stmt.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            names.append(value.value)
        elif isinstance(value, ast.List | ast.Tuple):
            names.extend(e.value for e in value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str))
    return names


def _selection_values(call: ast.Call) -> set[str] | None:
    """Literal keys of a fields.Selection(...) declaration, if statically known."""
    arg: ast.expr | None = call.args[0] if call.args else None
    if arg is None:
        arg = next((kw.value for kw in call.keywords if kw.arg == "selection"), None)
    if not isinstance(arg, ast.List | ast.Tuple):
        return None
    values = set()
    for element in arg.elts:
        if isinstance(element, ast.Tuple) and element.elts and isinstance(element.elts[0], ast.Constant):
            values.add(element.elts[0].value)
        else:
            # A non-literal entry means the list is not fully static; don't gate on it.
            return None
    return values


def _build_registry() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return (model -> field names, "model.field" -> selection values)."""
    fields_by_model: dict[str, set[str]] = {}
    selections: dict[str, set[str]] = {}

    for path in _addon_python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            models = [m for m in _class_model_names(cls) if m]
            if not models:
                continue
            for model in models:
                fields_by_model.setdefault(model, set())
            for stmt in cls.body:
                if not (
                    isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Call)
                    and isinstance(stmt.value.func, ast.Attribute)
                    and isinstance(stmt.value.func.value, ast.Name)
                    and stmt.value.func.value.id == "fields"
                ):
                    continue
                fname = stmt.targets[0].id
                for model in models:
                    fields_by_model[model].add(fname)
                if stmt.value.func.attr == "Selection":
                    values = _selection_values(stmt.value)
                    if values:
                        for model in models:
                            selections.setdefault(f"{model}.{fname}", set()).update(values)

    return fields_by_model, selections


MODEL_FIELDS, SELECTION_VALUES = _build_registry()


# ═════════════════════════════════════════════════════════════════════════
# Test-tree analysis
# ═════════════════════════════════════════════════════════════════════════


def _test_files() -> list[Path]:
    return sorted(p for p in TESTS_DIR.rglob("test_*.py") if "__pycache__" not in p.parts)


def _env_lookup_model(node: ast.expr) -> str | None:
    """Model name for an ``<something>.env["model.name"]`` subscript."""
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "env"
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
    ):
        return node.slice.value
    return None


def _model_bindings(tree: ast.AST) -> dict[str, str]:
    """Map local/class attribute names to the model they were bound to.

    Recognises ``cls.Offer = cls.env["plasticos.offer"]`` and the local-variable
    form, which is how every Odoo test in this tree reaches a model.
    """
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        model = _env_lookup_model(node.value)
        if model is None:
            continue
        for target in node.targets:
            if isinstance(target, ast.Attribute):
                bindings[target.attr] = model
            elif isinstance(target, ast.Name):
                bindings[target.id] = model
    return bindings


def _resolve_receiver(node: ast.expr, bindings: dict[str, str]) -> str | None:
    """Model behind the receiver of a ``.create(...)`` / ``.write(...)`` call."""
    direct = _env_lookup_model(node)
    if direct is not None:
        return direct
    if isinstance(node, ast.Attribute):
        return bindings.get(node.attr)
    if isinstance(node, ast.Name):
        return bindings.get(node.id)
    return None


def _value_dicts(call: ast.Call) -> list[ast.Dict]:
    if not call.args:
        return []
    arg = call.args[0]
    if isinstance(arg, ast.Dict):
        return [arg]
    if isinstance(arg, ast.List | ast.Tuple):
        return [e for e in arg.elts if isinstance(e, ast.Dict)]
    return []


def _iter_write_calls(tree: ast.AST, bindings: dict[str, str]):
    """Yield (model, values_dict) for every create()/write() on a known model."""
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("create", "write")
        ):
            continue
        model = _resolve_receiver(node.func.value, bindings)
        if model is None:
            continue
        for values in _value_dicts(node):
            yield model, values


# ═════════════════════════════════════════════════════════════════════════
# Guards
# ═════════════════════════════════════════════════════════════════════════


def test_registry_is_populated():
    """Guardrail: an empty registry would make every check below vacuous."""
    plasticos_models = [m for m in MODEL_FIELDS if m.startswith("plasticos.")]
    assert len(plasticos_models) >= 50, f"Only {len(plasticos_models)} plasticos.* models found — parsing is broken"
    assert SELECTION_VALUES, "No Selection fields found — parsing is broken"


def test_no_test_references_a_nonexistent_plasticos_model():
    """``self.env["plasticos.x"]`` must name a model some addon declares."""
    violations = []
    for path in _test_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            model = _env_lookup_model(node)
            if model is None or not model.startswith("plasticos."):
                continue
            if model not in MODEL_FIELDS:
                violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: {model}")

    assert not violations, (
        "Tests reference plasticos models that no addon declares. Either the model was "
        "renamed/retired (retarget the test) or the addon is missing:\n  " + "\n  ".join(violations)
    )


def test_no_test_writes_a_nonexistent_plasticos_field():
    """create()/write() keys on a plasticos model must be real fields."""
    violations = []
    for path in _test_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        bindings = _model_bindings(tree)
        for model, values in _iter_write_calls(tree, bindings):
            if not model.startswith("plasticos.") or model not in MODEL_FIELDS:
                continue
            known = MODEL_FIELDS[model] | INHERITED_FIELDS
            for key in values.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str) and key.value not in known:
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{key.lineno}: {model}.{key.value}")

    assert not violations, (
        "Tests write fields that do not exist on the target model — these raise at "
        "runtime and prove nothing until then:\n  " + "\n  ".join(violations)
    )


def test_no_test_writes_a_phantom_selection_value():
    """Literal values written to a Selection field must be in its option list."""
    violations = []
    for path in _test_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        bindings = _model_bindings(tree)
        for model, values in _iter_write_calls(tree, bindings):
            for key, value in zip(values.keys, values.values, strict=False):
                if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                    continue
                if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
                    continue
                options = SELECTION_VALUES.get(f"{model}.{key.value}")
                if options is not None and value.value not in options:
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}:{value.lineno}: "
                        f"{model}.{key.value}={value.value!r} (valid: {sorted(options)})"
                    )

    assert not violations, "Tests set Selection values that are not in the field's option list:\n  " + "\n  ".join(
        violations
    )


def test_no_test_imports_a_retired_addon():
    """No test may import from a module retired in M7 / TASK-051."""
    retired = ("plasticos_buyer_match_engine", "plasticos_inference_engine")
    violations = []
    for path in _test_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                if any(mod in name for mod in retired):
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: {name}")

    assert not violations, "Tests importing M7-retired modules:\n  " + "\n  ".join(violations)


def test_no_test_binds_to_a_mothballed_model():
    """Models in the mothball DISCARDABLE_CATALOG must not be reachable from tests.

    The catalog is read from scripts/migrations/mothball_local_intelligence.py so
    this guard tracks the migration rather than duplicating its list.
    """
    migration = REPO_ROOT / "scripts/migrations/mothball_local_intelligence.py"
    tree = ast.parse(migration.read_text(encoding="utf-8"))
    catalog: set[str] = set()
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "DISCARDABLE_CATALOG"
            and isinstance(node.value, ast.Dict)
        ):
            catalog = {k.value for k in node.value.keys if isinstance(k, ast.Constant)}

    assert catalog, "Could not read DISCARDABLE_CATALOG from the mothball migration"

    # plasticos.enrichment.service is catalogued but still present in-tree
    # (fail-closed shell retained until physical uninstall), so tests may touch it.
    live = set(MODEL_FIELDS)
    retired_models = {m for m in catalog if m not in live}

    violations = []
    for path in _test_files():
        try:
            file_tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(file_tree):
            model = _env_lookup_model(node)
            if model in retired_models:
                violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: {model}")

    assert not violations, (
        "Tests binding to mothballed local-intelligence models (CEG/Gate owns these "
        "now — see docs/adr/ADR-003-single-external-intelligence-authority.md):\n  " + "\n  ".join(violations)
    )
