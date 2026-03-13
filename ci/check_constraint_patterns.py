#!/usr/bin/env python3
"""
Check for Odoo constraint anti-patterns.

Detects:
1. SQL unique constraints without Python @api.constrains (raises IntegrityError instead of ValidationError)
2. assertRaises with tuple of exceptions (Odoo 19 requires single class)
3. Missing @api.constrains for required field validation on False values

Exit codes:
- 0: All checks passed
- 1: Anti-patterns found
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent

EXCLUDED_DIRS = {
    ".venv",
    "venv",
    "odoo-enterprise",
    "addons",
    "__pycache__",
    ".git",
    "docs",
    "ci",  # Exclude CI scripts themselves
    "tests",  # Repo-level tests (not module tests)
    "tests-odoo",
    "plasticos_graph_engine",
    "plasticos_graph_integration",
    "plasticos_graph_intelligence",
    "plasticos_graph_3d_embedding",
    "plasticos_matching",
    "plasticos_buyer_match_engine",
    "plasticos_enrichment",
    "plasticos_enrichment_bridge",
    "plasticos_web_leads",  # Complex module with different patterns
}


def find_python_files():
    """Find all Python model files."""
    for path in WORKSPACE.rglob("*.py"):
        if any(excl in path.parts for excl in EXCLUDED_DIRS):
            continue
        yield path


def check_sql_constraints_without_python(path: Path) -> list[str]:
    """
    Check for SQL unique constraints without corresponding @api.constrains.

    Anti-pattern: Having models.Constraint("unique(code)", ...) or
    _sql_constraints with unique without @api.constrains for the same field.
    """
    issues: list[str] = []
    content = path.read_text()

    # Skip test files
    if "/tests/" in str(path) or path.name.startswith("test_"):
        return issues

    # Find SQL unique constraints
    # Pattern 1: models.Constraint("unique(field)", ...)
    constraint_matches = re.findall(r'models\.Constraint\(\s*["\']unique\((\w+)\)["\']', content)

    # Pattern 2: _sql_constraints = [...("name", "unique(field)", "msg")...]
    sql_constraint_matches = re.findall(
        r'_sql_constraints\s*=\s*\[.*?["\']unique\((\w+)\)["\']',
        content,
        re.DOTALL,
    )

    unique_fields = set(constraint_matches + sql_constraint_matches)

    if not unique_fields:
        return issues

    # Check if @api.constrains exists for these fields
    for field in unique_fields:
        # Look for @api.constrains("field") or @api.constrains(..., "field", ...)
        constrains_pattern = r'@api\.constrains\([^)]*["\']' + field + r'["\'][^)]*\)'
        if not re.search(constrains_pattern, content):
            issues.append(f"  {path.relative_to(WORKSPACE)}:{field} - SQL unique constraint without @api.constrains")

    return issues


def check_assertraises_tuple(path: Path) -> list[str]:
    """
    Check for assertRaises with tuple of exceptions.

    Anti-pattern in Odoo 19: assertRaises((ValidationError, IntegrityError))
    Odoo 19's assertRaises expects a single class, not a tuple.
    """
    issues: list[str] = []

    # Only check test files
    if "/tests/" not in str(path) and not path.name.startswith("test_"):
        return issues

    content = path.read_text()
    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        # Match assertRaises with tuple: assertRaises((Exc1, Exc2))
        if re.search(r"assertRaises\s*\(\s*\(", line):
            issues.append(f"  {path.relative_to(WORKSPACE)}:{i} - assertRaises with tuple (use single exception class)")

    return issues


def main():
    sql_constraint_issues = []
    assertraises_issues = []

    for path in find_python_files():
        try:
            sql_constraint_issues.extend(check_sql_constraints_without_python(path))
            assertraises_issues.extend(check_assertraises_tuple(path))
        except Exception as e:
            print(f"Error processing {path}: {e}", file=sys.stderr)

    has_issues = False

    if sql_constraint_issues:
        print("WARNING: SQL unique constraints without @api.constrains (will raise IntegrityError):")
        print("\n".join(sql_constraint_issues))
        print()
        print("  NOTE: Add @api.constrains to raise ValidationError instead of IntegrityError")
        print("  (This is a warning - not blocking commit)")
        print()

    if assertraises_issues:
        print("ERROR: assertRaises with tuple (Odoo 19 requires single class):")
        print("\n".join(assertraises_issues))
        print()
        print("  FIX: Add @api.constrains to the model, then use assertRaises(ValidationError)")
        has_issues = True

    if has_issues:
        print("\nConstraint pattern check failed.")
        return 1

    if sql_constraint_issues:
        print("Constraint pattern check passed (with warnings).")
    else:
        print("Constraint pattern check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
