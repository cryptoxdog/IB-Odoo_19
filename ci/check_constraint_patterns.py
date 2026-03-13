#!/usr/bin/env python3
"""
Check for Odoo constraint anti-patterns.

Detects:
1. @api.constrains for unique field checks (WRONG - runs after SQL INSERT)
2. SQL unique constraints without create()/write() override (raises IntegrityError)
3. assertRaises with tuple of exceptions (Odoo 19 requires single class)

The CORRECT pattern for unique constraints:
- Override create() with @api.model_create_multi
- Check for duplicates BEFORE calling super()
- This raises ValidationError before SQL constraint fires

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
    "scripts",  # Audit/export scripts that scan code, not Odoo modules
    "ci",  # Exclude CI scripts themselves
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

# Repo-root level folders to exclude (not module-level tests/)
EXCLUDED_ROOT_DIRS = {"tests", "tests-odoo"}


def find_python_files():
    """Find all Python model files."""
    for path in WORKSPACE.rglob("*.py"):
        # Exclude directories anywhere in path
        if any(excl in path.parts for excl in EXCLUDED_DIRS):
            continue
        # Exclude repo-root level folders only (not module tests/)
        rel_path = path.relative_to(WORKSPACE)
        if rel_path.parts and rel_path.parts[0] in EXCLUDED_ROOT_DIRS:
            continue
        yield path


def check_api_constrains_for_unique(path: Path) -> list[str]:
    """
    Check for @api.constrains used to check unique fields.

    ANTI-PATTERN: Using @api.constrains for unique constraint validation.
    @api.constrains runs AFTER the SQL INSERT, so the SQL unique constraint
    fires first (raising IntegrityError instead of ValidationError).

    CORRECT PATTERN:
    - Override create() with @api.model_create_multi
    - Check for duplicates BEFORE calling super()
    - Override write() if code can be changed
    """
    issues: list[str] = []
    content = path.read_text()

    # Skip test files
    if "/tests/" in str(path) or path.name.startswith("test_"):
        return issues

    # Find @api.constrains that check for unique-like patterns
    # Look for @api.constrains("field") followed by search for duplicates
    lines = content.split("\n")

    for i, line in enumerate(lines):
        # Check for @api.constrains decorator
        if "@api.constrains" in line:
            # Look at the next ~15 lines for duplicate checking patterns
            context = "\n".join(lines[i : i + 15])
            # Patterns that indicate this is a unique check:
            # 1. search([...("field", "=", ...)...]) with ("id", "!=", ...)
            # 2. "already exists" in error message
            # 3. checking for duplicate
            if re.search(r'search\s*\(\s*\[.*\("id"\s*,\s*"!="\s*,', context, re.DOTALL):
                if "already exists" in context or "duplicate" in context.lower() or "unique" in context.lower():
                    # Extract field name from @api.constrains
                    field_match = re.search(r'@api\.constrains\s*\(\s*["\'](\w+)["\']', line)
                    field = field_match.group(1) if field_match else "unknown"
                    issues.append(
                        f"  {path.relative_to(WORKSPACE)}:{i + 1} - @api.constrains('{field}') for unique check "
                        f"(use create()/write() override instead)"
                    )

    return issues


def check_sql_constraints_without_create_override(path: Path) -> list[str]:
    """
    Check for SQL unique constraints without create()/write() override.

    ANTI-PATTERN: Having models.Constraint("unique(field)") or _sql_constraints
    without overriding create() to check before SQL INSERT.
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

    # Check if create() is overridden with proper duplicate check
    has_create_override = bool(re.search(r"def create\s*\(", content))
    has_model_create_multi = bool(re.search(r"@api\.model_create_multi", content))

    # If there's a create override with @api.model_create_multi, check if it has duplicate check
    if has_create_override and has_model_create_multi:
        # Look for search() before super().create()
        create_block = re.search(
            r"@api\.model_create_multi\s*\n\s*def create\(.*?\n(.*?)return super\(\)",
            content,
            re.DOTALL,
        )
        if create_block:
            create_body = create_block.group(1)
            # Check if there's a search for duplicates before super()
            if re.search(r"self\.search\s*\(", create_body):
                return issues  # Properly implemented

    # No proper create() override - flag all unique fields
    for field in unique_fields:
        issues.append(f"  {path.relative_to(WORKSPACE)}:{field} - SQL unique constraint without create() pre-check")

    return issues


def check_assertraises_tuple(path: Path) -> list[str]:
    """
    Check for assertRaises with tuple of exceptions in UNIQUE constraint tests.

    ONLY flag assertRaises((ValidationError, IntegrityError)) when:
    - Test is clearly for a UNIQUE constraint (has "unique" in test name or comment)

    DO NOT flag for:
    - Required field tests (NOT NULL → IntegrityError is correct)
    - CHECK constraint tests (price > 0 → IntegrityError is correct)
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
            # Look at surrounding context (test name, comments) to determine if unique test
            context_start = max(0, i - 10)
            context = "\n".join(lines[context_start:i])

            # Only flag if context suggests this is a UNIQUE constraint test
            is_unique_test = any(
                keyword in context.lower()
                for keyword in ["unique", "duplicate", "already exists", "same partner", "same code"]
            )

            if is_unique_test:
                issues.append(
                    f"  {path.relative_to(WORKSPACE)}:{i} - assertRaises with tuple for unique constraint "
                    "(model has create() pre-check, use ValidationError only)"
                )

    return issues


def main():
    api_constrains_issues: list[str] = []
    sql_constraint_issues: list[str] = []
    assertraises_issues: list[str] = []

    for path in find_python_files():
        try:
            api_constrains_issues.extend(check_api_constrains_for_unique(path))
            sql_constraint_issues.extend(check_sql_constraints_without_create_override(path))
            assertraises_issues.extend(check_assertraises_tuple(path))
        except Exception as e:
            print(f"Error processing {path}: {e}", file=sys.stderr)

    has_errors = False

    if api_constrains_issues:
        print("ERROR: @api.constrains used for unique checks (runs AFTER SQL, too late!):")
        print("\n".join(api_constrains_issues))
        print()
        print("  FIX: Override create() with @api.model_create_multi and check BEFORE super().create()")
        print("  Example:")
        print("    @api.model_create_multi")
        print("    def create(self, vals_list):")
        print("        for vals in vals_list:")
        print('            if vals.get("code") and self.search([("code", "=", vals["code"])], limit=1):')
        print('                raise ValidationError(f"Code already exists.")')
        print("        return super().create(vals_list)")
        print()
        has_errors = True

    if sql_constraint_issues:
        print("WARNING: SQL unique constraints without create() pre-check:")
        print("\n".join(sql_constraint_issues))
        print()
        print("  NOTE: Add create()/write() override to check before SQL INSERT")
        print("  (This is a warning - IntegrityError may fire instead of ValidationError)")
        print()

    if assertraises_issues:
        print("ERROR: assertRaises with tuple (Odoo 19 requires single class):")
        print("\n".join(assertraises_issues))
        print()
        print("  FIX: Use assertRaises(ValidationError) after adding create() pre-check to model")
        has_errors = True

    if has_errors:
        print("\nConstraint pattern check failed.")
        return 1

    if sql_constraint_issues:
        print("Constraint pattern check passed (with warnings).")
    else:
        print("Constraint pattern check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
