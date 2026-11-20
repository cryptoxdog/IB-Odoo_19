#!/usr/bin/env python3
"""Classify a committed diff for the PR-fast non-marker lane.

The caller proves the diff (merge-base, rename, and delete records). This module
does not fetch git and does not treat a substring search as reachability. A test
module is selected only when it is the changed file, its AST imports the changed
module, or a string constant equals the repo-relative path or the dotted module.

Unknown classification is a blocker. It is not a silent success and it is not
permission to run ``pytest tests/`` on a pull request. Scanner configuration
and scanner fixtures are their own class: the two Sonar property files at the
repository root, and every path under ``.semgrep/``. No pure-Python suite
executes them. A path outside that class stays unknown.

Dependency manifests (``requirements*.txt``, ``constraints.txt``), workflow
files other than the two CI-owned ones, and ``pyproject.toml`` changes outside
pytest's own configuration are routed like any other path: the test modules
that reference them run, and any remaining behavioral regression stays on the
nightly Odoo-free suite. A ``pyproject.toml`` change inside ``[tool.pytest]`` or
a ``[tool.pytest.*]`` table, or one whose diff is unavailable, changes how every
module is collected and stays unknown. ``tests/__init__.py`` and
``tests/common.py`` stay unknown.
"""

from __future__ import annotations

import ast
import tomllib
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
    "tests/__init__.py",
    "tests/common.py",
}

PYPROJECT = "pyproject.toml"
PATCHED_PATHS = ("tests/conftest.py", PYPROJECT)
_CONTENT_JUDGED = frozenset({PYPROJECT, *CRITICAL_EXACT})

HARNESS_MEDIATORS = {"tests/__init__.py", "tests/common.py", "tests/conftest.py"}

_COLLECTION_NEEDLES = (
    "_collect_odoo_test_files",
    "_imports_odoo",
    "_line_names_odoo_module",
    "_odoo_available",
    "collect_ignore",
)

_DOC_SUFFIXES = {".md", ".mdc", ".rst"}
# Suffix-less documentation files, by exact repository-root path. No pure-Python suite executes them.
_DOC_ROOT_FILES = frozenset({"LICENSE"})
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
        self.scanner: list[str] = []
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
    if code in {"D", "R", "C"} and {path, current} & _CONTENT_JUDGED:
        acc.unknown.append(f"{path}: deleting, renaming or copying a shared harness or pytest configuration input")
        return
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
    if current in CRITICAL_EXACT:
        acc.unknown.append(f"{current}: shared harness input has no proven bounded pure-Python set")
        return
    if current == PYPROJECT:
        _route_pyproject(acc, root, index, patches)
        return
    if _is_dependency_manifest(current):
        _add_structural(acc, index, current)
        return
    if current in COVERED_BY_MANDATORY:
        _cover_mandatory(acc, current, patches)
        return
    if _is_workflow(current):
        _add_structural(acc, index, current)
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
    if _is_scanner_input(current):
        acc.scanner.append(current)
        return
    if _is_doc(current) or _is_inert(current):
        acc.docs.append(current)
        return
    if current.endswith(".py") or _is_addon_resource(current):
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


def _route_pyproject(acc: _Acc, root: Path, index: list[tuple[str, ast.AST]], patches: dict[str, str]) -> None:
    patch = patches.get(PYPROJECT)
    if patch is None or not patch.strip():
        acc.unknown.append(f"{PYPROJECT}: diff is unavailable")
        return
    try:
        text = (root / PYPROJECT).read_text(encoding="utf-8")
    except OSError:
        acc.unknown.append(f"{PYPROJECT}: changed file is not in the tree")
        return
    if pyproject_pytest_changed(patch, text):
        acc.unknown.append(f"{PYPROJECT}: pytest configuration change is not a bounded fast scope")
        return
    _add_structural(acc, index, PYPROJECT)


def pyproject_pytest_changed(patch: str, text: str) -> bool:
    """True when a ``-U0`` pyproject diff changes pytest's configuration, or cannot be proven not to.

    The base file is rebuilt from the checked-out file and the patch, both are
    parsed as TOML, and the ``tool.pytest`` values are compared. That covers
    ``[tool.pytest]`` and every ``[tool.pytest.*]`` table however the keys are
    spelled (quoted, spaced, dotted assignment). A patch that does not apply
    exactly, or a file that does not parse, counts as a change: fail closed.
    """
    base = _reverse_apply(patch, text)
    if base is None:
        return True
    try:
        before = tomllib.loads(base)
        after = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return True
    return _pytest_config(before) != _pytest_config(after)


def _pytest_config(doc: dict) -> object:
    tool = doc.get("tool")
    return tool.get("pytest") if isinstance(tool, dict) else None


def _reverse_apply(patch: str, text: str) -> str | None:
    """Rebuild the base file from the head file and a single-file ``-U0`` patch; ``None`` when unproven."""
    hunks: list[dict] = []
    for line in patch.splitlines():
        if not hunks and not line.startswith("@@"):
            continue  # file headers precede the first hunk
        if line.startswith("@@"):
            spans = _hunk_spans(line)
            if spans is None:
                return None
            old_count, new_start, new_count = spans
            hunks.append({"old": old_count, "start": new_start, "count": new_count, "minus": [], "plus": []})
        elif line.startswith("-"):
            hunks[-1]["minus"].append(line[1:])
        elif line.startswith("+"):
            hunks[-1]["plus"].append(line[1:])
        elif not line.startswith("\\"):
            return None  # a -U0 patch carries no context lines
    if not hunks:
        return None
    lines = text.splitlines()
    for hunk in sorted(hunks, key=lambda h: h["start"], reverse=True):
        if len(hunk["minus"]) != hunk["old"] or len(hunk["plus"]) != hunk["count"]:
            return None
        low = hunk["start"] if hunk["count"] == 0 else hunk["start"] - 1
        if lines[low : low + hunk["count"]] != hunk["plus"]:
            return None
        lines[low : low + hunk["count"]] = hunk["minus"]
    return "\n".join(lines) + "\n"


def _hunk_spans(header: str) -> tuple[int, int, int] | None:
    """``@@ -a[,b] +c[,d] @@`` → ``(b, c, d)``; counts default to 1."""
    parts = header.split(" ")
    if len(parts) < 4 or not parts[1].startswith("-") or not parts[2].startswith("+"):
        return None
    try:
        _old_start, old_count = _span(parts[1][1:])
        new_start, new_count = _span(parts[2][1:])
    except ValueError:
        return None
    return old_count, new_start, new_count


def _span(text: str) -> tuple[int, int]:
    start, sep, count = text.partition(",")
    return int(start), int(count) if sep else 1


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
        "scanner_inputs": acc.scanner,
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
    if acc.scanner:
        return (
            "scanner configuration and fixtures have no pure-Python execution; "
            "scoped non-marker pytest is not applicable"
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
        "scanner_inputs": [],
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
    is_addon_xml = _is_addon_resource(rel) and rel.endswith(".xml")
    is_addon_manifest = rel.startswith("plasticos_") and rel.endswith("/__manifest__.py")
    for owner, tree in index:
        # Existing tests may discover XML via manifest iteration or glob rather
        # than naming the resource as a literal. Those consumers still matter.
        if _is_test_module(owner) and (is_addon_xml or is_addon_manifest):
            if _scans_manifest_xml(tree) or (is_addon_xml and _globs_xml(tree)):
                hits.add(owner)
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
        if _joined_path_suffix(node) == rel:
            return True
        for imported in _imported_modules(node):
            if not dotted:
                continue
            if imported == dotted or imported.startswith(dotted + "."):
                return True
            if "." in imported and dotted.endswith("." + imported):
                return True
    return False


def _joined_path_suffix(node: ast.AST) -> str | None:
    """Recognize a complete repo-relative path assembled with pathlib `/`.

    Ignore the dynamic root expression, but require all of the subsequent
    segments to be static, individual safe path components. A partial filename
    or substring mention is not enough to establish a test dependency.
    """
    if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
        return None
    parts: list[str] = []
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        right = node.right
        if not isinstance(right, ast.Constant) or not isinstance(right.value, str):
            return None
        parts.append(right.value)
        node = node.left
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        parts.append(node.value)
    if len(parts) < 2 or any(not p or p in {".", ".."} or "/" in p or "\\" in p for p in parts):
        return None
    return "/".join(reversed(parts))


def _xml_scan_calls(tree: ast.AST) -> tuple[bool, bool, bool]:
    """Identify test-side dynamic XML ownership without a hardcoded module list."""
    manifest_glob = xml_glob = xml_parse = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", None)
        if name is None and isinstance(node.func, ast.Name):
            name = node.func.id
        if name in {"glob", "rglob"}:
            literals = (
                item.value
                for arg in node.args
                for item in ast.walk(arg)
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            )
            for literal in literals:
                manifest_glob |= "__manifest__.py" in literal
                xml_glob |= "*.xml" in literal
        if name in {"parse", "iterparse"}:
            xml_parse = True
    return manifest_glob, xml_glob, xml_parse


def _scans_manifest_xml(tree: ast.AST) -> bool:
    manifest_glob, _xml_glob, xml_parse = _xml_scan_calls(tree)
    return manifest_glob and xml_parse


def _globs_xml(tree: ast.AST) -> bool:
    _manifest_glob, xml_glob, _xml_parse = _xml_scan_calls(tree)
    return xml_glob


def _imported_modules(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        found = [node.module]
        for alias in node.names:
            if alias.name and alias.name != "*":
                found.append(f"{node.module}.{alias.name}")
        return found
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


def _is_dependency_manifest(path: str) -> bool:
    """Root-level pip manifests. Their consumers are the tests that read them."""
    return "/" not in path and (_is_requirements(path) or path == "constraints.txt")


def _is_workflow(path: str) -> bool:
    return path.startswith(".github/workflows/") and Path(path).suffix in {".yml", ".yaml"}


def _is_gate(path: str) -> bool:
    return path.startswith("plasticos_gate/") or path == "ci/with_github_read_token.py"


_ADDON_RESOURCE_SUFFIXES = {".css", ".csv", ".js", ".po", ".pot", ".scss", ".xml", ".yaml", ".yml"}


_SCANNER_ROOT_FILES = frozenset({".sonarcloud.properties", "sonar-project.properties"})


def _is_scanner_input(path: str) -> bool:
    """Sonar property files and Semgrep rules or fixtures. No pure-Python suite executes them."""
    return path in _SCANNER_ROOT_FILES or path.startswith(".semgrep/")


def _is_addon_resource(path: str) -> bool:
    """A non-Python file inside a PlasticOS addon. No pure-Python suite can execute it."""
    return path.startswith("plasticos_") and "/" in path and Path(path).suffix.lower() in _ADDON_RESOURCE_SUFFIXES


def _is_doc(path: str) -> bool:
    return path in _DOC_ROOT_FILES or Path(path).suffix.lower() in _DOC_SUFFIXES


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
