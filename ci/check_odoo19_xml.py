#!/usr/bin/env python3
"""
Odoo 19 XML Pattern Checker
===========================

Prevents common Odoo 19 XML view errors that cause module load failures.

Patterns checked:
1. <tree> instead of <list> (ParseError: Invalid view type)
2. alert-* classes without role attribute (accessibility warning/error)
3. active_id in context (doesn't exist on model, use id)
4. view_mode with 'tree' instead of 'list'

Usage:
    python3 ci/check_odoo19_xml.py [root_dir]

Exit codes:
    0 = No issues found
    1 = Issues found (blocks CI)
"""

import re
import subprocess
import sys
from pathlib import Path


def get_git_tracked_files(pattern: str) -> list[Path]:
    """Get git-tracked files matching pattern."""
    try:
        result = subprocess.run(
            ["git", "ls-files", pattern],
            capture_output=True,
            text=True,
            check=True,
        )
        return [Path(f) for f in result.stdout.strip().split("\n") if f]
    except subprocess.CalledProcessError:
        return []


def _check_view_xml_file(xml_file: Path) -> list[dict]:
    """Check a single view XML file for all Odoo 19 forbidden patterns."""
    errors = []
    try:
        with open(xml_file, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception:
        return errors

    for i, line in enumerate(lines, 1):
        # Pattern 1: <tree> tag (should be <list>)
        if re.search(r"<tree\b", line) and not re.search(r"tree\.txt", line):
            errors.append(
                {
                    "file": str(xml_file),
                    "line": i,
                    "pattern": "<tree>",
                    "message": "Use <list> instead of <tree> (Odoo 19)",
                }
            )

        # Pattern 2: alert-* class without role attribute
        if re.search(r'class="[^"]*alert[^"]*"', line) and not re.search(r"role=", line):
            context = "\n".join(lines[max(0, i - 1) : min(len(lines), i + 2)])
            if not re.search(r"role=", context):
                errors.append(
                    {
                        "file": str(xml_file),
                        "line": i,
                        "pattern": "alert without role",
                        "message": (
                            "Elements with alert-* class must have role attribute. " 'Add role="alert" or role="status"'
                        ),
                    }
                )

        # Pattern 3: active_id in context (should be id)
        if re.search(r"context=.*active_id", line):
            errors.append(
                {
                    "file": str(xml_file),
                    "line": i,
                    "pattern": "active_id in context",
                    "message": ("active_id is a client-side variable, not a field. Use 'id' instead in view context"),
                }
            )

        # Pattern 4: view_mode with 'tree' (should be 'list')
        if re.search(r'name="view_mode"[^>]*>.*tree', line):
            errors.append(
                {
                    "file": str(xml_file),
                    "line": i,
                    "pattern": "view_mode tree",
                    "message": "Use 'list' instead of 'tree' in view_mode (Odoo 19)",
                }
            )

    return errors


def _check_data_xml_file(xml_file: Path) -> list[dict]:
    """Check a single data XML file for view_mode tree usage."""
    errors = []
    try:
        with open(xml_file, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception:
        return errors

    for i, line in enumerate(lines, 1):
        if re.search(r'name="view_mode"[^>]*>.*tree', line):
            errors.append(
                {
                    "file": str(xml_file),
                    "line": i,
                    "pattern": "view_mode tree",
                    "message": "Use 'list' instead of 'tree' in view_mode (Odoo 19)",
                }
            )

    return errors


def check_xml_patterns(root_dir: Path) -> list[dict]:
    """Find forbidden XML patterns in view files."""
    errors = []

    # Only check git-tracked files
    view_files = get_git_tracked_files("*/views/*.xml")
    if not view_files:
        view_files = list(root_dir.glob("*/views/*.xml"))

    for xml_file in view_files:
        if "__pycache__" in str(xml_file):
            continue
        errors.extend(_check_view_xml_file(xml_file))

    # Also check data XML files for view_mode
    data_files = get_git_tracked_files("*/data/*.xml")
    if not data_files:
        data_files = list(root_dir.glob("*/data/*.xml"))

    for xml_file in data_files:
        errors.extend(_check_data_xml_file(xml_file))

    return errors


def main():
    root_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")

    print("🔍 Checking Odoo 19 XML patterns...")
    errors = check_xml_patterns(root_dir)

    if errors:
        print(f"\n❌ Found {len(errors)} Odoo 19 XML issues:")
        for err in errors:
            print(f"   {err['file']}:{err['line']} [{err['pattern']}]")
            print(f"      {err['message']}")
        print("\n" + "=" * 60)
        print("These patterns will cause Odoo 19 to fail at startup.")
        print("=" * 60)
        sys.exit(1)
    else:
        print("✅ All XML patterns are Odoo 19 compliant!")
        sys.exit(0)


if __name__ == "__main__":
    main()
