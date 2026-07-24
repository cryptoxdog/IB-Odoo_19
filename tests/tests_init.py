"""Test suite structure validation for PlastOS tests folder.

This module validates that:
1. All test files in tests/ are syntactically valid Python
2. Test files follow naming conventions (test_*.py)
3. Pure Python tests are properly categorized
4. Odoo-dependent tests are properly categorized
5. No orphaned test files exist

Run: pytest tests/tests_init.py -v
"""

import ast
from pathlib import Path

TESTS_DIR = Path(__file__).parent

# Test modules that require Odoo runtime
ODOO_TEST_MODULES = [
    "test_action_methods",
    "test_bridge_models",
    "test_constraints_material_profile",
    "test_constraints_onchanges",
    "test_cron_batch_normalize",
    "test_cron_plasticos_base",
    "test_cron_runtime",
    "test_depends_transaction_claims_bridge",
    "test_error_handling",
    "test_gate_enrichment_fallback",
    "test_gate_matcher_fallback",
    "test_golden_flows",
    "test_integration_flows",
    "test_onchange_purchase_order_line_plasticos",
    "test_onchange_sale_order_line_plasticos",
    "test_performance",
    "test_security_acl",
    "test_state_machines",
]

# Pure Python tests (no Odoo dependency)
PURE_PYTHON_MODULES = [
    "test_cron_invariants",
    "test_cypher_schema_alignment",
    "test_gate_match_contract",
    "test_odoo19_compat",
    "test_odoo_test_setup_validity",
    "test_phantom_enum_values",
    "test_process_enum_alignment",
    "test_repo_dependency_integrity",
]

# Files that are not test modules
NON_TEST_FILES = [
    "__init__.py",
    "__manifest__.py",
    "tests_init.py",
    "README.md",
]


class TestSuiteStructure:
    """Validate the test suite structure and organization."""

    def test_all_test_files_parse(self):
        """Every test_*.py file must be syntactically valid Python."""
        errors = []
        for py_file in TESTS_DIR.glob("test_*.py"):
            try:
                source = py_file.read_text()
                ast.parse(source, filename=str(py_file))
            except SyntaxError as e:
                errors.append(f"{py_file.name}: {e}")

        assert not errors, "Syntax errors in test files:\n" + "\n".join(errors)

    def test_no_orphaned_test_files(self):
        """All test_*.py files should be in either ODOO or PURE_PYTHON category."""
        all_test_files = {f.stem for f in TESTS_DIR.glob("test_*.py")}
        categorized = set(ODOO_TEST_MODULES) | set(PURE_PYTHON_MODULES)
        orphaned = all_test_files - categorized

        assert not orphaned, (
            f"Orphaned test files not categorized:\n  {orphaned}\n"
            "Add them to ODOO_TEST_MODULES or PURE_PYTHON_MODULES in tests_init.py"
        )

    def test_categorized_files_exist(self):
        """All categorized test modules should have corresponding files."""
        missing = []
        for module in ODOO_TEST_MODULES + PURE_PYTHON_MODULES:
            path = TESTS_DIR / f"{module}.py"
            if not path.exists():
                missing.append(module)

        assert not missing, f"Missing test files for categorized modules:\n  {missing}"

    def test_pure_python_tests_no_odoo_import(self):
        """Pure Python tests should not import odoo at module level."""
        violations = []
        for module in PURE_PYTHON_MODULES:
            path = TESTS_DIR / f"{module}.py"
            if not path.exists():
                continue

            source = path.read_text()
            # Check for direct odoo imports (not in try/except)
            lines = source.split("\n")
            in_try_block = False
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("try:"):
                    in_try_block = True
                elif stripped.startswith("except"):
                    in_try_block = False
                elif not in_try_block:
                    if stripped.startswith("from odoo") or stripped.startswith("import odoo"):
                        violations.append(f"{module}.py:{i}: {stripped}")

        assert not violations, "Pure Python tests should not import odoo at module level:\n  " + "\n  ".join(violations)

    def test_odoo_tests_have_transaction_case(self):
        """Odoo-dependent tests should inherit from TransactionCase or similar."""
        missing_base = []
        for module in ODOO_TEST_MODULES:
            path = TESTS_DIR / f"{module}.py"
            if not path.exists():
                continue

            source = path.read_text()
            if "TransactionCase" not in source and "HttpCase" not in source:
                missing_base.append(module)

        assert not missing_base, f"Odoo tests missing TransactionCase/HttpCase base:\n  {missing_base}"

    def test_test_files_have_docstrings(self):
        """Test files should have module-level docstrings."""
        missing_docs = []
        for py_file in TESTS_DIR.glob("test_*.py"):
            source = py_file.read_text()
            try:
                tree = ast.parse(source)
                docstring = ast.get_docstring(tree)
                if not docstring:
                    missing_docs.append(py_file.name)
            except SyntaxError:
                pass  # Already caught by test_all_test_files_parse

        # Soft warning - don't fail, just report
        if missing_docs:
            import warnings

            warnings.warn(
                f"Test files without docstrings: {missing_docs}",
                stacklevel=1,
            )

    def test_no_duplicate_test_class_names(self):
        """Test class names should be unique across the test suite."""
        class_locations = {}
        duplicates = []

        for py_file in TESTS_DIR.glob("test_*.py"):
            try:
                source = py_file.read_text()
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                        if node.name in class_locations:
                            duplicates.append(f"{node.name}: {class_locations[node.name]} and {py_file.name}")
                        else:
                            class_locations[node.name] = py_file.name
            except SyntaxError:
                pass

        assert not duplicates, "Duplicate test class names found:\n  " + "\n  ".join(duplicates)


class TestTestFileNaming:
    """Validate test file naming conventions."""

    def test_test_files_start_with_test(self):
        """All Python test files should start with 'test_'."""
        bad_names = []
        for py_file in TESTS_DIR.glob("*.py"):
            if py_file.name in NON_TEST_FILES:
                continue
            if not py_file.name.startswith("test_"):
                bad_names.append(py_file.name)

        assert not bad_names, f"Test files not following test_*.py convention:\n  {bad_names}"

    def test_no_test_prefix_in_non_test_files(self):
        """Non-test files should not start with 'test_'."""
        for name in NON_TEST_FILES:
            assert not name.startswith("test_"), f"Non-test file '{name}' should not start with 'test_'"


class TestTestContent:
    """Validate test file content patterns."""

    def test_no_print_statements_in_tests(self):
        """Tests should use assertions, not print statements for output."""
        print_usage = []
        for py_file in TESTS_DIR.glob("test_*.py"):
            source = py_file.read_text()
            lines = source.split("\n")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                # Skip comments and strings
                if stripped.startswith("#"):
                    continue
                # Check for bare print() calls (not in capsys context)
                if "print(" in stripped and "capsys" not in source[: source.find(stripped)]:
                    # Allow print in test_print_* methods (intentional output tests)
                    if "def test_print" not in source[max(0, source.find(stripped) - 200) : source.find(stripped)]:
                        print_usage.append(f"{py_file.name}:{i}")

        # Soft check - warn but don't fail
        if print_usage and len(print_usage) > 5:
            import warnings

            warnings.warn(
                f"Tests with print() statements (consider using assertions): {len(print_usage)} occurrences",
                stacklevel=1,
            )

    def test_tests_have_assertions(self):
        """Test methods should contain assertions."""
        methods_without_assertions = []

        for py_file in TESTS_DIR.glob("test_*.py"):
            try:
                source = py_file.read_text()
                tree = ast.parse(source)

                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                        # Check if method has assert, self.assert*, or pytest.fail
                        method_source = ast.unparse(node)
                        has_assertion = (
                            "assert" in method_source
                            or "self.assert" in method_source
                            or "pytest.fail" in method_source
                            or "pytest.skip" in method_source
                            or "self.skipTest" in method_source
                        )
                        if not has_assertion:
                            methods_without_assertions.append(f"{py_file.name}::{node.name}")
            except SyntaxError:
                pass

        # Allow some methods without explicit assertions (setup/teardown patterns)
        if len(methods_without_assertions) > 10:
            import warnings

            warnings.warn(
                f"Test methods without assertions: {len(methods_without_assertions)}",
                stacklevel=1,
            )
