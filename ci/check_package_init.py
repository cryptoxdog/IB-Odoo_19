#!/usr/bin/env python3
"""
Check that critical Odoo Python packages have valid __init__.py files.

Catches:
1. models/ directories with .py files but no __init__.py
2. services/ directories with .py files but empty __init__.py
3. wizards/ directories with .py files but no __init__.py
4. Stray init.py files (typo without underscores)

Excludes:
- migrations/ (Odoo doesn't require __init__.py)
- tests/ (pytest doesn't require __init__.py)
- docs/ (not Python packages)
- scripts/ (standalone scripts)
- ci/ (standalone scripts)

Run:
    python3 ci/check_package_init.py
    python3 ci/check_package_init.py /path/to/repo
"""

import os
import sys
from pathlib import Path

# Directories that MUST have proper __init__.py
CRITICAL_DIRS = {"models", "services", "wizards", "wizard", "controllers", "report"}

# Directories to skip entirely
SKIP_DIRS = {"migrations", "tests", "docs", "scripts", "ci", ".venv", "venv", "__pycache__"}


def find_critical_packages(root: Path) -> list[Path]:
    """Find Odoo package directories that need __init__.py."""
    packages = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden dirs and excluded dirs
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS]

        path = Path(dirpath)

        # Only check plasticos_* modules
        parts = path.relative_to(root).parts
        if not parts or not parts[0].startswith("plasticos_"):
            continue

        # Only check critical directories
        if path.name not in CRITICAL_DIRS:
            continue

        # Check if directory has .py files (excluding __init__.py)
        py_files = [f for f in filenames if f.endswith(".py") and f != "__init__.py"]
        if py_files:
            packages.append(path)

    return packages


def find_stray_init_files(root: Path) -> list[Path]:
    """Find init.py files (typo without underscores)."""
    stray = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS]

        path = Path(dirpath)
        parts = path.relative_to(root).parts
        if not parts or not parts[0].startswith("plasticos_"):
            continue

        if "init.py" in filenames:
            stray.append(path / "init.py")

    return stray


def check_package(pkg_path: Path) -> list[str]:
    """Check a single package for issues."""
    issues = []

    init_file = pkg_path / "__init__.py"

    # Issue 1: Missing __init__.py
    if not init_file.exists():
        issues.append(f"MISSING: {init_file}")
        return issues

    # Issue 2: Empty __init__.py in service directories
    # services/ typically need to import their submodules for Odoo to find them
    if init_file.stat().st_size == 0:
        if pkg_path.name in ("services",):
            py_files = [f for f in pkg_path.iterdir() if f.suffix == ".py" and f.name != "__init__.py"]
            if py_files:
                modules = ", ".join(f.stem for f in py_files[:3])
                issues.append(f"EMPTY: {init_file} (needs imports: {modules}...)")

    return issues


def main(root_dir: str = ".") -> int:
    """Main entry point."""
    root = Path(root_dir).resolve()

    if not root.exists():
        print(f"ERROR: Directory not found: {root}")
        return 1

    all_issues = []

    # Check for stray init.py files
    stray_files = find_stray_init_files(root)
    for stray in stray_files:
        all_issues.append(f"STRAY: {stray} (should be __init__.py)")

    # Check critical packages
    packages = find_critical_packages(root)
    for pkg in packages:
        issues = check_package(pkg)
        all_issues.extend(issues)

    if all_issues:
        print(f"❌ Found {len(all_issues)} package __init__.py issues:\n")
        for issue in sorted(all_issues):
            print(f"  {issue}")
        print("\nFix these issues before committing.")
        return 1

    print(f"✅ All {len(packages)} critical Odoo packages have valid __init__.py files")
    return 0


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    sys.exit(main(root))
