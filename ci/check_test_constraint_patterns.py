#!/usr/bin/env python3
"""
Check and fix test constraint patterns.

Detects tests that incorrectly expect ValidationError for SQL-level constraints:
- NOT NULL (required=True) → raises IntegrityError
- CHECK constraints (price > 0) → raises IntegrityError
- UNIQUE constraints WITHOUT create() pre-check → raises IntegrityError

CORRECT patterns:
- Required field tests: assertRaises((ValidationError, IntegrityError))
- CHECK constraint tests: assertRaises((ValidationError, IntegrityError))
- Unique tests WITH create() pre-check: assertRaises(ValidationError) only

Exit codes:
- 0: All tests correct (or --fix applied)
- 1: Issues found (no --fix)
"""

import argparse
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
    "scripts",
}

# Keywords that indicate SQL-level constraints (need IntegrityError)
SQL_CONSTRAINT_KEYWORDS = {
    "required",  # NOT NULL
    "positive",  # CHECK > 0
    "negative",  # CHECK < 0
    "not_null",
    "notnull",
}

# Keywords that indicate Python-level unique checks (ValidationError only)
PYTHON_UNIQUE_KEYWORDS = {
    "unique",
    "duplicate",
}

INTEGRITY_IMPORT = """try:
    from psycopg.errors import IntegrityError
except ImportError:
    from psycopg2 import IntegrityError

"""


def find_test_files() -> list[Path]:
    """Find all test files in module tests/ directories."""
    test_files = []
    for path in WORKSPACE.rglob("test_*.py"):
        if any(excl in path.parts for excl in EXCLUDED_DIRS):
            continue
        # Only module-level tests (inside plasticos_*/tests/)
        if "/tests/" in str(path) or "\\tests\\" in str(path):
            test_files.append(path)
    return sorted(test_files)


def has_integrity_import(content: str) -> bool:
    """Check if file imports IntegrityError."""
    return bool(re.search(r"from psycopg[2]?\.errors import IntegrityError", content))


def analyze_test_file(path: Path) -> dict:
    """Analyze a test file for constraint pattern issues."""
    content = path.read_text()
    lines = content.split("\n")
    issues = []

    for i, line in enumerate(lines, 1):
        # Find assertRaises(ValidationError) - single class, not tuple
        if re.search(r"assertRaises\s*\(\s*ValidationError\s*\)", line):
            # Look at context to determine constraint type
            context_start = max(0, i - 15)
            context = "\n".join(lines[context_start : i + 3]).lower()

            # Check for SQL-level constraint keywords
            is_sql_constraint = any(kw in context for kw in SQL_CONSTRAINT_KEYWORDS)

            # Check for unique constraint (might be Python-level)
            is_unique_test = any(kw in context for kw in PYTHON_UNIQUE_KEYWORDS)

            if is_sql_constraint and not is_unique_test:
                issues.append(
                    {
                        "line": i,
                        "type": "sql_constraint",
                        "text": line.strip(),
                        "reason": "Required/CHECK constraint test should accept IntegrityError",
                    }
                )

    return {
        "path": path,
        "has_integrity_import": has_integrity_import(content),
        "issues": issues,
    }


def fix_test_file(path: Path, dry_run: bool = False) -> bool:
    """Fix constraint patterns in a test file."""
    content = path.read_text()
    lines = content.split("\n")
    fixed_lines = []
    changes_made = False

    for i, line in enumerate(lines):
        line_num = i + 1
        new_line = line

        # Find assertRaises(ValidationError) - single class
        if re.search(r"assertRaises\s*\(\s*ValidationError\s*\)", line):
            # Look at context
            context_start = max(0, i - 15)
            context = "\n".join(lines[context_start : i + 3]).lower()

            # SQL-level constraints need IntegrityError tuple
            is_sql_constraint = any(kw in context for kw in SQL_CONSTRAINT_KEYWORDS)
            is_unique_test = any(kw in context for kw in PYTHON_UNIQUE_KEYWORDS)

            if is_sql_constraint and not is_unique_test:
                new_line = re.sub(
                    r"assertRaises\s*\(\s*ValidationError\s*\)",
                    "assertRaises((ValidationError, IntegrityError))",
                    line,
                )
                if new_line != line:
                    changes_made = True
                    print(f"  L{line_num}: {line.strip()}")
                    print(f"       → {new_line.strip()}")

        fixed_lines.append(new_line)

    fixed_content = "\n".join(fixed_lines)

    # Add IntegrityError import if needed and not present
    if changes_made and not has_integrity_import(fixed_content):
        # Find insertion point (after existing imports)
        import_section_end = 0
        for i, line in enumerate(fixed_lines):
            if line.startswith("import ") or line.startswith("from "):
                import_section_end = i + 1
            elif line.strip() and not line.startswith("#") and import_section_end > 0:
                break

        # Insert IntegrityError import
        fixed_lines.insert(import_section_end, "")
        fixed_lines.insert(import_section_end + 1, "try:")
        fixed_lines.insert(import_section_end + 2, "    from psycopg.errors import IntegrityError")
        fixed_lines.insert(import_section_end + 3, "except ImportError:")
        fixed_lines.insert(import_section_end + 4, "    from psycopg2 import IntegrityError")
        print("  + Added IntegrityError import")
        fixed_content = "\n".join(fixed_lines)

    if changes_made and not dry_run:
        path.write_text(fixed_content)
        return True

    return changes_made


def main():
    parser = argparse.ArgumentParser(description="Check/fix test constraint patterns")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues")
    parser.add_argument("--dry-run", action="store_true", help="Show fixes without applying")
    args = parser.parse_args()

    test_files = find_test_files()
    print(f"Scanning {len(test_files)} test files...")

    all_issues: list[dict] = []
    files_with_issues: list[Path] = []

    for path in test_files:
        result = analyze_test_file(path)
        if result["issues"]:
            all_issues.extend(result["issues"])
            files_with_issues.append(path)

    if not all_issues:
        print("All test constraint patterns are correct.")
        return 0

    print(f"\nFound {len(all_issues)} issues in {len(files_with_issues)} files:\n")

    for path in files_with_issues:
        result = analyze_test_file(path)
        rel_path = path.relative_to(WORKSPACE)
        print(f"📁 {rel_path}")
        for issue in result["issues"]:
            print(f"   L{issue['line']}: {issue['reason']}")
            print(f"          {issue['text']}")
        print()

    if args.fix or args.dry_run:
        print("=" * 60)
        print("FIXING:" if args.fix else "DRY RUN (no changes):")
        print("=" * 60)

        fixed_count = 0
        for path in files_with_issues:
            rel_path = path.relative_to(WORKSPACE)
            print(f"\n📝 {rel_path}")
            if fix_test_file(path, dry_run=args.dry_run):
                fixed_count += 1

        if args.fix:
            print(f"\n✅ Fixed {fixed_count} files")
            return 0
        else:
            print(f"\n⚠️  Would fix {fixed_count} files (use --fix to apply)")
            return 1

    print("Run with --fix to auto-correct these issues.")
    print("Run with --dry-run to preview fixes.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
