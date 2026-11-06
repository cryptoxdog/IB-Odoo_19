"""Structural validation of the PlastOS test suite itself.

Architecture note (2026-08 reconciliation): this module used to be named
``tests_init.py``. pytest collects ``test_*.py`` / ``*_test.py`` only, so under
that name **none of these checks ever ran** — the suite's own structure validator
was a silent orphan, and its two hand-maintained registries drifted unnoticed
(24 of 47 root modules listed, plus a ``test_gate_matcher_fallback`` entry whose
file no longer exists). Both registries are now derived from the filesystem, so
they cannot drift again, and the file name makes the checks actually execute.

What is validated:
1. Every test file in tests/ is syntactically valid Python.
2. Every test file is named so pytest will collect it (the defect above).
3. Test files follow the ``test_*.py`` convention.
4. Modules classified pure-Python really do avoid module-level ``odoo`` imports,
   matching the contract tests/conftest.py relies on for collect_ignore.
5. Odoo-backed modules declare a recognised Odoo test base.
6. Test class names are unique across the suite.

Run: pytest tests/test_suite_structure.py -v
"""

import ast
from pathlib import Path

TESTS_DIR = Path(__file__).parent

# Files in tests/ that are deliberately not test modules.
NON_TEST_FILES = frozenset(
    {
        "__init__.py",
        "__manifest__.py",
        "conftest.py",
        "common.py",
        "README.md",
        # tests/runtime_gates/ — launch gates that need a live Odoo registry and
        # a live PostgreSQL server (see that directory's README). They are named
        # run_*.py precisely so pytest does not collect them: under
        # TransactionCase there is one cursor and one snapshot, so collecting
        # them would turn a real proof into a vacuous pass.
        "run_c1_c2_c4_c5.py",
        "run_web_lead_concurrent_admission.py",
        "run_c3_failure_writer_lock.py",
        "run_c6_replay_checkpoint.py",
        "run_c7_c8_enrichment_failures.py",
        "run_c9_c10_matching_failures.py",
        "run_f1_f3_full_import.py",
        "f1_guarded_shell.py",
        "run_erp_import.py",
        "run_s1_s3_pristine_seams.py",
        "_runtime_env.py",
        # Disposable-database lifecycle imported by run_erp_import.py. Not a test.
        "scratch_db.py",
        # Odoo-free cron registry imported by the XML lock. Not a test module.
        "cron_contract.py",
        # Promotion-rehearsal note. run.sh does not execute it, and it is not a test module.
        "crm_100.py",
    }
)

# Bases that mark a module as Odoo-runtime backed. PlasticosTestCase
# (plasticos_base/test_common.py) is the canonical shared base: it resolves to
# TransactionCase under --test-enable and to unittest.TestCase otherwise.
ODOO_TEST_BASES = ("PlasticosTestCase", "TransactionCase", "HttpCase", "SavepointCase")


def _test_files() -> list[Path]:
    """Every test module in the suite, including contracts/ and integration/."""
    return sorted(p for p in TESTS_DIR.rglob("test_*.py") if "__pycache__" not in p.parts)


def _line_names_odoo_module(line: str) -> bool:
    """Same token rule as tests/conftest.py: ``odoo`` only, not ``odools_...``."""
    stripped = line.lstrip()
    for keyword in ("import ", "from "):
        if not stripped.startswith(keyword):
            continue
        rest = stripped[len(keyword) :].lstrip()
        token = rest.split(" ", 1)[0].split(".", 1)[0].rstrip(",")
        return token == "odoo"
    return False


def _imports_odoo_at_module_level(source: str) -> bool:
    """True when the module imports odoo outside a try/except guard.

    Mirrors tests/conftest.py's collect-ignore heuristic, which is what actually
    decides whether a module runs under a pure-Python pytest invocation.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in tree.body:
        if isinstance(node, ast.Import):
            if any(a.name == "odoo" or a.name.startswith("odoo.") for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "odoo" or mod.startswith("odoo."):
                return True
    return False


# Calls that fail or skip. Other ``self.assert*`` calls are matched by prefix.
_ASSERTING_CALLS = frozenset({"pytest.fail", "pytest.skip", "self.skipTest"})


def _dotted_name(node: ast.expr) -> str | None:
    """``a.b.c`` for a Name/Attribute chain, otherwise None."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


# Calls that only assert when entered as a context manager or given a callable:
# a bare ``pytest.raises(ValueError)`` builds a context manager and checks nothing.
_CONTEXT_ASSERTING_CALLS = frozenset({"pytest.raises", "pytest.warns", "pytest.deprecated_call"})
_CONTEXT_ASSERTING_PREFIXES = ("self.assertRaises", "self.assertWarns", "self.assertLogs", "self.assertNoLogs")


def _asserts_directly(node: ast.AST) -> bool:
    """True when ``node`` contains an assert, ``raise AssertionError``, or an asserting call.

    A context-manager assertion (``pytest.raises``, ``self.assertRaises`` ...) counts only
    as a ``with`` item or when called with a callable argument.
    """
    with_items = {id(item.context_expr) for sub in ast.walk(node) if isinstance(sub, ast.With) for item in sub.items}
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assert):
            return True
        if isinstance(sub, ast.Raise) and sub.exc is not None:
            exc = sub.exc.func if isinstance(sub.exc, ast.Call) else sub.exc
            if isinstance(exc, ast.Name) and exc.id == "AssertionError":
                return True
        if isinstance(sub, ast.Call):
            name = _dotted_name(sub.func)
            if name is None:
                continue
            if name in _CONTEXT_ASSERTING_CALLS or name.startswith(_CONTEXT_ASSERTING_PREFIXES):
                if id(sub) in with_items or len(sub.args) >= 2:
                    return True
                continue
            if name in _ASSERTING_CALLS or name.startswith("self.assert"):
                return True
    return False


def _is_skipped(node: ast.FunctionDef) -> bool:
    return any(
        isinstance(d, ast.Attribute) and d.attr in ("skip", "xfail")
        for d in ast.walk(ast.Module(body=node.decorator_list, type_ignores=[]))
    )


def _unasserted_test_names(tree: ast.Module) -> list[str]:
    """Names of ``test_*`` functions in ``tree`` that make no claim.

    A test makes a claim when its own body asserts directly, or when it calls,
    by bare name, a function defined at the top level of the same module whose
    own body asserts directly. Helpers are followed one level only, and
    ``self.method(...)`` is never followed.
    """
    module_functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    unasserted = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")):
            continue
        if _is_skipped(node) or _asserts_directly(node):
            continue
        helpers = {
            sub.func.id
            for sub in ast.walk(node)
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id in module_functions
        }
        if any(_asserts_directly(module_functions[name]) for name in helpers):
            continue
        unasserted.append(node.name)
    return unasserted


class TestSuiteStructure:
    """Validate the test suite's structure and organization."""

    def test_all_test_files_parse(self):
        """Every test_*.py file must be syntactically valid Python."""
        errors = []
        for py_file in _test_files():
            try:
                ast.parse(py_file.read_text(), filename=str(py_file))
            except SyntaxError as e:
                errors.append(f"{py_file.relative_to(TESTS_DIR)}: {e}")

        assert not errors, "Syntax errors in test files:\n" + "\n".join(errors)

    def test_every_test_module_is_collectable_by_pytest(self):
        """No module may define tests under a name pytest will not collect.

        This is the regression guard for the defect that hid this very file:
        a validator named tests_init.py that pytest silently never ran.
        """
        uncollectable = []
        for py_file in TESTS_DIR.rglob("*.py"):
            if "__pycache__" in py_file.parts or py_file.name in NON_TEST_FILES:
                continue
            if py_file.name.startswith("test_") or py_file.name.endswith("_test.py"):
                continue
            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue
            defines_tests = any(
                (isinstance(n, ast.ClassDef) and n.name.startswith("Test"))
                or (isinstance(n, ast.FunctionDef) and n.name.startswith("test_"))
                for n in ast.walk(tree)
            )
            if defines_tests:
                uncollectable.append(str(py_file.relative_to(TESTS_DIR)))

        assert not uncollectable, (
            "These files define tests but pytest will never collect them "
            "(name must match test_*.py or *_test.py):\n  " + "\n  ".join(uncollectable)
        )

    def test_pure_python_tests_have_no_module_level_odoo_import(self):
        """Modules pytest collects must not import odoo at module level.

        tests/conftest.py collect-ignores anything importing odoo, so any module
        that survives collection is by definition pure-Python. This asserts the
        classification is consistent rather than re-deriving it from a stale list.
        """
        violations = []
        for py_file in _test_files():
            source = py_file.read_text()
            imports_odoo = _imports_odoo_at_module_level(source)
            conftest_would_ignore = any(_line_names_odoo_module(line) for line in source.splitlines())
            if imports_odoo != conftest_would_ignore:
                violations.append(
                    f"{py_file.relative_to(TESTS_DIR)}: AST says odoo-import={imports_odoo} "
                    f"but conftest heuristic says {conftest_would_ignore}"
                )

        assert not violations, (
            "conftest.py's collect-ignore heuristic disagrees with the module's real "
            "imports; the wrong set of tests will run:\n  " + "\n  ".join(violations)
        )

    def test_odoo_tests_declare_a_recognised_base(self):
        """Odoo-backed tests must use PlasticosTestCase/TransactionCase/HttpCase."""
        missing_base = []
        for py_file in _test_files():
            source = py_file.read_text()
            if not _imports_odoo_at_module_level(source):
                continue
            if not any(base in source for base in ODOO_TEST_BASES):
                missing_base.append(str(py_file.relative_to(TESTS_DIR)))

        assert not missing_base, f"Odoo tests missing a recognised base {ODOO_TEST_BASES}:\n  " + "\n  ".join(
            missing_base
        )

    def test_no_duplicate_test_class_names(self):
        """Test class names must be unique across the suite."""
        class_locations: dict[str, str] = {}
        duplicates = []

        for py_file in _test_files():
            rel = str(py_file.relative_to(TESTS_DIR))
            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                    if node.name in class_locations:
                        duplicates.append(f"{node.name}: {class_locations[node.name]} and {rel}")
                    else:
                        class_locations[node.name] = rel

        assert not duplicates, "Duplicate test class names found:\n  " + "\n  ".join(duplicates)


class TestTestFileNaming:
    """Validate test file naming conventions."""

    def test_test_files_start_with_test(self):
        """Python modules in tests/ must be test_*.py or a declared non-test file."""
        bad_names = []
        for py_file in TESTS_DIR.rglob("*.py"):
            if "__pycache__" in py_file.parts or py_file.name in NON_TEST_FILES:
                continue
            if not py_file.name.startswith("test_"):
                bad_names.append(str(py_file.relative_to(TESTS_DIR)))

        assert not bad_names, f"Test files not following test_*.py convention:\n  {bad_names}"

    def test_non_test_files_are_not_test_named(self):
        """The NON_TEST_FILES exemption list must not shadow real test modules."""
        for name in NON_TEST_FILES:
            assert not name.startswith("test_"), f"Non-test file '{name}' should not start with 'test_'"


class TestTestContent:
    """Validate test file content patterns."""

    def test_test_methods_contain_assertions(self):
        """Every collected test function makes a claim, fails, or skips.

        Read from the AST, never from source text: ``assert``, ``raise
        AssertionError``, ``pytest.raises`` / ``pytest.fail`` / ``pytest.skip``,
        ``self.skipTest``, ``self.assert*``, or a one-level call to a same-module
        function that does one of those. ``skip`` / ``xfail`` decorated tests are
        excluded. Any other raise does not count.
        """
        without_assertions = []

        for py_file in _test_files():
            rel = str(py_file.relative_to(TESTS_DIR))
            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue
            without_assertions.extend(f"{rel}::{name}" for name in _unasserted_test_names(tree))

        assert not without_assertions, f"{len(without_assertions)} test methods make no claim: {without_assertions}"


class TestAssertionDetector:
    """Negative cases for ``_unasserted_test_names``: each must fail on a governed break."""

    @staticmethod
    def _unasserted(source: str) -> list[str]:
        return _unasserted_test_names(ast.parse(source))

    def test_empty_test_is_reported(self):
        assert self._unasserted("def test_empty():\n    pass\n") == ["test_empty"]

    def test_plain_assert_is_a_claim(self):
        assert self._unasserted("def test_ok():\n    assert 1\n") == []

    def test_pytest_raises_is_a_claim(self):
        src = "import pytest\ndef test_raises():\n    with pytest.raises(ValueError):\n        int('x')\n"
        assert self._unasserted(src) == []

    def test_bare_pytest_raises_is_reported(self):
        src = "import pytest\ndef test_bare():\n    pytest.raises(ValueError)\n    int('x')\n"
        assert self._unasserted(src) == ["test_bare"]

    def test_pytest_raises_with_callable_is_a_claim(self):
        src = "import pytest\ndef test_callable():\n    pytest.raises(ValueError, int, 'x')\n"
        assert self._unasserted(src) == []

    def test_bare_assert_raises_is_reported(self):
        src = "class TestX:\n    def test_bare(self):\n        self.assertRaises(ValueError)\n"
        assert self._unasserted(src) == ["test_bare"]

    def test_raise_assertion_error_is_a_claim(self):
        assert self._unasserted("def test_assertion_error():\n    raise AssertionError('x')\n") == []

    def test_other_raise_is_reported(self):
        src = "def test_other_raise():\n    raise RuntimeError('x')\n"
        assert self._unasserted(src) == ["test_other_raise"]

    def test_same_module_asserting_helper_is_a_claim(self):
        src = "def _check():\n    assert 1\n\ndef test_helper():\n    _check()\n"
        assert self._unasserted(src) == []

    def test_same_module_non_asserting_helper_is_reported(self):
        src = "def _check():\n    return 1\n\ndef test_helper():\n    _check()\n"
        assert self._unasserted(src) == ["test_helper"]

    def test_self_method_is_not_followed(self):
        src = (
            "def _helper():\n    assert 1\n\n"
            "class TestX:\n"
            "    def _helper(self):\n        assert 1\n\n"
            "    def test_self_call(self):\n        self._helper()\n"
        )
        assert self._unasserted(src) == ["test_self_call"]
