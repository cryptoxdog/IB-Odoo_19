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
        "run_c3_failure_writer_lock.py",
        "run_c6_replay_checkpoint.py",
        "run_c7_c8_enrichment_failures.py",
    }
)

# Bases that mark a module as Odoo-runtime backed. PlasticosTestCase
# (plasticos_base/test_common.py) is the canonical shared base: it resolves to
# TransactionCase under --test-enable and to unittest.TestCase otherwise.
ODOO_TEST_BASES = ("PlasticosTestCase", "TransactionCase", "HttpCase", "SavepointCase")


def _test_files() -> list[Path]:
    """Every test module in the suite, including contracts/ and integration/."""
    return sorted(p for p in TESTS_DIR.rglob("test_*.py") if "__pycache__" not in p.parts)


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
            conftest_would_ignore = any(
                line.lstrip().startswith(("import odoo", "from odoo")) for line in source.splitlines()
            )
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
        """Report test methods with no visible assertion, failure, or skip.

        ADVISORY (warns, does not fail) — deliberately, and unchanged from this
        check's original intent. The detector is syntactic: a method whose
        assertion lives in a helper that raises (``self._run_cron_safely(...)``,
        ``validate_canonical_projection(...)``) is indistinguishable here from one
        that asserts nothing. Escalating this to a hard gate needs the ~40 current
        hits triaged one by one, which is a separate change.
        """
        without_assertions = []

        for py_file in _test_files():
            rel = str(py_file.relative_to(TESTS_DIR))
            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")):
                    continue
                if any(
                    isinstance(d, ast.Attribute) and d.attr in ("skip", "xfail")
                    for d in ast.walk(ast.Module(body=node.decorator_list, type_ignores=[]))
                ):
                    continue
                body = ast.unparse(node)
                if not any(
                    token in body for token in ("assert", "self.assert", "pytest.fail", "pytest.skip", "self.skipTest")
                ):
                    without_assertions.append(f"{rel}::{node.name}")

        if without_assertions:
            import warnings

            warnings.warn(
                f"{len(without_assertions)} test methods have no syntactically visible "
                f"assertion (may assert via a raising helper): {without_assertions[:10]}",
                stacklevel=1,
            )
