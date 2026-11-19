#!/usr/bin/env python3
"""Classify a committed diff for the PR-fast non-marker lane.

The caller proves the diff (merge-base, rename, and delete records). This module
does not fetch git and does not treat a substring search as reachability. A test
module is selected only when it is the changed file, its AST imports the changed
module, or a string constant equals the repo-relative path or the dotted module.

Unknown classification is a blocker. It is not a silent success and it is not
permission to run ``pytest tests/`` on a pull request.
"""

from __future__ import annotations

import ast
from pathlib import Path

SCHEMA = "plasticos.pr-fast-scope.v1"
SELECTOR_ID = "ci.pr_fast_scope.v1"

REQUIRED_MARKER_MODULES = (
    "tests/test_ci_event_triggers.py",
    "tests/test_install_smoke_db_guard.py",
    "tests/test_install_smoke_evidence.py",
    "tests/test_make_pr_publication.py",
    "tests/test_pr_check_scope.py",
    "tests/test_pr_fast_scope.py",
)

COVERED_BY_MANDATORY = {
    ".github/workflows/ci.yml",
    ".github/workflows/nightly-full-python.yml",
    "ci/check_github_actions_kernel.sh",
    "ci/nightly_full_run.py",
    "ci/pr_fast_scope.py",
    "ci/run_pr_fast_tests.py",
    "tests/conftest.py",
}

CRITICAL_EXACT = {
    "constraints.txt",
    "pyproject.toml",
    "tests/__init__.py",
    "tests/common.py",
}

HARNESS_MEDIATORS = {"tests/__init__.py", "tests/common.py", "tests/conftest.py"}

_COLLECTION_NEEDLES = (
    "_collect_odoo_test_files",
    "_imports_odoo",
    "_line_names_odoo_module",
    "_odoo_available",
    "collect_ignore",
)

_DOC_SUFFIXES = {".md", ".mdc", ".rst"}
_INERT_SUFFIXES = {".gif", ".jpeg", ".jpg", ".pdf", ".png", ".svg", ".webp"}
_STATUS_CODES = {"A", "C", "D", "M", "R", "T"}


def parse_name_status(text: str) -> list[tuple[str, str, str | None]] | None:
    """Parse ``git diff --name-status -M`` output. ``None`` means the diff is not trustworthy."""
    rows: list[tuple[str, str, str | None]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        code = parts[0][:1]
        if code not in _STATUS_CODES or parts[0] in {"U", "X", "B"}:
            return None
        if code in {"R", "C"}:
            if len(parts) != 3 or not _safe(parts[1]) or not _safe(parts[2]):
                return None
            rows.append((code, parts[1], parts[2]))
            continue
        if len(parts) != 2 or not _safe(parts[1]):
            return None
        rows.append((code, parts[1], None))
    return rows


def module_marker_is_adversarial(path: Path) -> bool:
    """True when the module assigns ``pytestmark`` to the adversarial contract marker."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False
    for node in tree.body:
        value = _pytestmark_value(node)
        if value is not None:
            return _expr_is_adversarial(value)
    return False


def missing_mandatory_markers(root: Path) -> list[str]:
    """Required safety modules that are missing or no longer carry the contract marker."""
    missing = []
    for rel in REQUIRED_MARKER_MODULES:
        path = root / rel
        if not path.is_file() or not module_marker_is_adversarial(path):
            missing.append(rel)
    return missing


def conftest_collection_changed(patch: str) -> bool:
    """True when a conftest diff touches Odoo collection, which selects every pure-Python module."""
    for line in patch.splitlines():
        if not line.startswith(("+", "-")) or line.startswith(("+++", "---")):
            continue
        if any(needle in line for needle in _COLLECTION_NEEDLES):
            return True
    return False


def classify(
    entries: list[tuple[str, str, str | None]] | None,
    root: Path,
    *,
    patches: dict[str, str] | None = None,
    base_sha: str = "",
    declared_head: str = "",
    observed_head: str = "",
) -> dict:
    """Return a scope receipt. ``entries is None`` is an unresolvable diff."""
    if declared_head and observed_head and declared_head != observed_head:
        return _receipt("unknown", "declared head does not match the tested checkout")
    if entries is None:
        return _receipt("unknown", "diff is unavailable", base_sha=base_sha, head_sha=observed_head)
    acc = _Acc()
    index = _index_tests(root)
    for code, path, new_path in entries:
        _apply(acc, root, index, patches or {}, code, path, new_path)
    return _finish(acc, root, base_sha, observed_head or declared_head)


class _Acc:
    def __init__(self) -> None:
        self.changed: list[str] = []
        self.selected: set[str] = set()
        self.deleted: list[str] = []
        self.renames: list[dict[str, str]] = []
        self.covered: list[str] = []
        self.docs: list[str] = []
        self.absence: list[str] = []
        self.gate: list[str] = []
        self.unknown: list[str] = []


def _apply(
    acc: _Acc,
    root: Path,
    index: list[tuple[str, ast.AST]],
    patches: dict[str, str],
    code: str,
    path: str,
    new_path: str | None,
) -> None:
    current = new_path or path
    acc.changed.append(current if code != "D" else path)
    if code in {"R", "C"}:
        acc.renames.append({"old": path, "new": current})
        if not _is_test_module(path) and not _is_test_module(current):
            _add_structural(acc, index, path)
    if _is_test_module(path) and code == "D":
        acc.deleted.append(path)
        return
    if _is_test_module(current) and code != "D":
        if not (root / current).is_file():
            acc.unknown.append(f"{current}: changed test is not in the tree")
            return
        acc.selected.add(current)
        return
    if code == "D":
        acc.deleted.append(path)
        _add_structural(acc, index, path)
        return
    if _is_requirements(current) or current in CRITICAL_EXACT:
        acc.unknown.append(f"{current}: shared harness or dependency input has no proven bounded pure-Python set")
        return
    if current in COVERED_BY_MANDATORY:
        _cover_mandatory(acc, current, patches)
        return
    if current.startswith("docs/") and current.endswith(".py"):
        acc.unknown.append(f"{current}: executable documentation is not a docs-only path")
        return
    if _is_gate(current):
        acc.gate.append(current)
        _add_structural(acc, index, current)
        return
    hits, harness = _structural(index, current)
    if harness:
        acc.unknown.append(f"{current}: impact is mediated by the shared test harness")
        return
    if hits:
        acc.selected.update(hits)
        return
    if _is_doc(current) or _is_inert(current):
        acc.docs.append(current)
        return
    if current.endswith(".py"):
        acc.absence.append(current)
        return
    acc.unknown.append(f"{current}: unclassified path")


def _cover_mandatory(acc: _Acc, path: str, patches: dict[str, str]) -> None:
    if path == "tests/conftest.py":
        patch = patches.get(path)
        if patch is None or not patch.strip():
            acc.unknown.append("tests/conftest.py: collection diff is unavailable")
            return
        if conftest_collection_changed(patch):
            acc.unknown.append("tests/conftest.py: Odoo collection change is not a bounded fast scope")
            return
    acc.covered.append(path)


def _add_structural(acc: _Acc, index: list[tuple[str, ast.AST]], path: str) -> None:
    hits, harness = _structural(index, path)
    if harness:
        acc.unknown.append(f"{path}: impact is mediated by the shared test harness")
        return
    if hits:
        acc.selected.update(hits)
        return
    if not _is_gate(path):
        acc.absence.append(path)


def _finish(acc: _Acc, root: Path, base_sha: str, head_sha: str) -> dict:
    scoped, mandatory, odoo = _split_selected(acc.selected, root)
    if acc.unknown:
        reason = "unclassified or unproven scope: " + "; ".join(acc.unknown)
        status = "unknown"
    elif acc.selected or acc.covered or acc.gate or acc.deleted or acc.renames:
        reason = _applicable_reason(acc, mandatory)
        status = "applicable"
    else:
        reason = _absent_reason(acc)
        status = "not_applicable"
    return {
        "schema": SCHEMA,
        "selector": SELECTOR_ID,
        "status": status,
        "reason": reason,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "changed": acc.changed,
        "selected_tests": sorted(acc.selected),
        "scoped_nonmarker_tests": scoped,
        "mandatory_modules": mandatory,
        "odoo_runtime_tests": odoo,
        "deleted": acc.deleted,
        "renames": acc.renames,
        "covered_by_mandatory": acc.covered,
        "documentation": acc.docs,
        "structural_absence": acc.absence,
        "gate_sdk_paths": acc.gate,
        "gate_sdk_job": "required",
        "unknown_paths": acc.unknown,
    }


def _applicable_reason(acc: _Acc, mandatory: list[str]) -> str:
    parts = []
    if acc.covered or mandatory:
        parts.append("mandatory adversarial contracts cover the CI-owned paths")
    if acc.gate:
        parts.append("Gate SDK bridge job stays required")
    if acc.deleted:
        parts.append("deleted paths are recorded and are not treated as an empty success")
    if not parts:
        parts.append("selected pure-Python modules are the proven structural set")
    return "; ".join(parts)


def _absent_reason(acc: _Acc) -> str:
    if acc.absence:
        return (
            "no pure-Python test imports these paths or quotes them; "
            "behavioral regression stays on the nightly Odoo-free suite"
        )
    if acc.docs or not acc.changed:
        return "documentation-only or empty diff; scoped non-marker pytest is not applicable"
    return "no additional pure-Python module was proven"


def _split_selected(selected: set[str], root: Path) -> tuple[list[str], list[str], list[str]]:
    scoped: list[str] = []
    mandatory: list[str] = []
    odoo: list[str] = []
    for rel in sorted(selected):
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            odoo.append(rel)
            continue
        if _imports_odoo_source(text):
            odoo.append(rel)
        elif module_marker_is_adversarial(path):
            mandatory.append(rel)
        else:
            scoped.append(rel)
    return scoped, mandatory, odoo


def _receipt(status: str, reason: str, base_sha: str = "", head_sha: str = "") -> dict:
    return {
        "schema": SCHEMA,
        "selector": SELECTOR_ID,
        "status": status,
        "reason": reason,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "changed": [],
        "selected_tests": [],
        "scoped_nonmarker_tests": [],
        "mandatory_modules": [],
        "odoo_runtime_tests": [],
        "deleted": [],
        "renames": [],
        "covered_by_mandatory": [],
        "documentation": [],
        "structural_absence": [],
        "gate_sdk_paths": [],
        "gate_sdk_job": "required",
        "unknown_paths": [reason],
    }


def _index_tests(root: Path) -> list[tuple[str, ast.AST]]:
    index: list[tuple[str, ast.AST]] = []
    tests = root / "tests"
    if not tests.is_dir():
        return index
    for path in sorted(tests.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        try:
            index.append((rel, ast.parse(path.read_text(encoding="utf-8"))))
        except (OSError, SyntaxError):
            continue
    return index


def _structural(index: list[tuple[str, ast.AST]], rel: str) -> tuple[set[str], bool]:
    dotted = _dotted(rel)
    hits: set[str] = set()
    harness = False
    for owner, tree in index:
        if not _references(tree, rel, dotted):
            continue
        if _is_test_module(owner):
            hits.add(owner)
        elif owner in HARNESS_MEDIATORS:
            harness = True
    return hits, harness


def _references(tree: ast.AST, rel: str, dotted: str | None) -> bool:
    targets = {rel}
    if dotted:
        targets.add(dotted)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in targets:
            return True
        for imported in _imported_modules(node):
            if dotted and (imported == dotted or imported.startswith(dotted + ".")):
                return True
    return False


def _imported_modules(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        return [node.module]
    return []


def _pytestmark_value(node: ast.AST) -> ast.AST | None:
    if isinstance(node, ast.Assign):
        targets = node.targets
        value = node.value
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
        value = node.value
    else:
        return None
    if value is not None and any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in targets):
        return value
    return None


def _expr_is_adversarial(expr: ast.AST) -> bool:
    if isinstance(expr, ast.Attribute) and expr.attr == "adversarial_contract":
        return True
    if isinstance(expr, (ast.List, ast.Tuple)):
        return any(_expr_is_adversarial(elt) for elt in expr.elts)
    if isinstance(expr, ast.Call):
        return _expr_is_adversarial(expr.func)
    return False


def _imports_odoo_source(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.lstrip()
        for keyword in ("import ", "from "):
            if not stripped.startswith(keyword):
                continue
            rest = stripped[len(keyword) :].lstrip()
            token = rest.split(" ", 1)[0].split(".", 1)[0].rstrip(",")
            if token == "odoo":
                return True
    return False


def _is_test_module(path: str) -> bool:
    name = Path(path).name
    return path.startswith("tests/") and name.startswith("test_") and name.endswith(".py")


def _is_requirements(path: str) -> bool:
    name = Path(path).name
    return name.startswith("requirements") and name.endswith(".txt")


def _is_gate(path: str) -> bool:
    return path.startswith("plasticos_gate/") or path == "ci/with_github_read_token.py"


def _is_doc(path: str) -> bool:
    return Path(path).suffix.lower() in _DOC_SUFFIXES


def _is_inert(path: str) -> bool:
    return Path(path).suffix.lower() in _INERT_SUFFIXES


def _dotted(path: str) -> str | None:
    file = Path(path)
    if file.suffix != ".py":
        return None
    parts = list(file.parts)
    parts[-1] = file.stem
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _safe(path: str) -> bool:
    if not path or path.startswith(("/", "\\")) or path.startswith("-"):
        return False
    return ".." not in Path(path).parts
