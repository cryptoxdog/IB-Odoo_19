"""No inheriting class may relax a field its defining module declares ``required=True``.

Why this exists: ``plasticos_material_profile`` and ``plasticos_facility_profile``
declared ``partner_id`` ``required=True`` and ``plasticos_crm_bridge`` relaxed it with
``partner_id = fields.Many2one(required=False)`` so lead-owned rows could exist.
During ``-u`` Odoo sets up the defining module's column first, before the
relaxing override is loaded, and tries ``ALTER ... SET NOT NULL``. With
lead-owned rows present it logs::

    column "partner_id" of relation "plasticos_material_profile" contains null values

and every Odoo.sh build of that database ends yellow. The defining module had
claimed a stronger invariant than the composed system holds.

The fix pattern: the defining module does not set ``required`` and enforces its
owner rule through an extensible check (``_plasticos_owner_fields``); an
inheriting module extends that check instead of relaxing ``required``.
"""

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _str_values(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple)):
        return [elt.value for elt in node.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)]
    return []


def _required_kw(call):
    """Return True/False when ``required=`` is a literal bool, else None."""
    for kw in call.keywords:
        if kw.arg == "required" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, bool):
            return kw.value.value
    return None


def _is_fields_call(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "fields"
    )


def _scan(repo):
    """Yield (path, lineno, model_names, name, inherited, field, required) per literal ``required=``."""
    for path in sorted(repo.glob("plasticos_*/**/*.py")):
        if "/tests/" in path.as_posix() or "/migrations/" in path.as_posix():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            name, inherits = None, []
            for stmt in cls.body:
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                    target = stmt.targets[0].id
                    if target == "_name":
                        values = _str_values(stmt.value)
                        name = values[0] if values else None
                    elif target == "_inherit":
                        inherits = _str_values(stmt.value)
            for stmt in cls.body:
                if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1):
                    continue
                target = stmt.targets[0]
                if not isinstance(target, ast.Name) or not _is_fields_call(stmt.value):
                    continue
                required = _required_kw(stmt.value)
                if required is None:
                    continue
                yield path, stmt.lineno, name, inherits, target.id, required


def find_relaxations(repo=REPO):
    declared_required = {}
    relaxing = []
    for path, lineno, name, inherits, field, required in _scan(repo):
        if name and required:
            declared_required.setdefault((name, field), f"{path.relative_to(repo)}:{lineno}")
        if required is False:
            extended = [model for model in inherits if model == name or name is None]
            for model in extended:
                relaxing.append((model, field, f"{path.relative_to(repo)}:{lineno}"))
    return [
        f"{where} relaxes {model}.{field}, declared required=True at {declared_required[(model, field)]}"
        for model, field, where in relaxing
        if (model, field) in declared_required
    ]


def test_no_inherited_required_field_is_relaxed():
    problems = find_relaxations()
    assert not problems, (
        "An inheriting class relaxes a field its defining module declares required=True. "
        "Odoo tries SET NOT NULL before the override loads and warns on every upgrade. "
        "Drop required=True in the defining module and enforce the rule with an extensible "
        "check instead:\n" + "\n".join(problems)
    )


def test_guard_detects_the_pattern(tmp_path):
    """The scanner flags the exact crm_bridge pattern that caused the NOT NULL warning."""
    base = tmp_path / "plasticos_demo_base" / "models"
    ext = tmp_path / "plasticos_demo_ext" / "models"
    base.mkdir(parents=True)
    ext.mkdir(parents=True)
    (base / "profile.py").write_text(
        "class P(models.Model):\n"
        "    _name = 'plasticos.demo'\n"
        "    partner_id = fields.Many2one('res.partner', required=True)\n",
        encoding="utf-8",
    )
    (ext / "profile.py").write_text(
        "class E(models.Model):\n    _inherit = 'plasticos.demo'\n    partner_id = fields.Many2one(required=False)\n",
        encoding="utf-8",
    )
    problems = find_relaxations(tmp_path)
    assert len(problems) == 1
    assert "plasticos.demo.partner_id" in problems[0]
