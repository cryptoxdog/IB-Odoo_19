#!/usr/bin/env python3
"""
Odoo env.get() Anti-Pattern Checker
====================================

Prevents use of self.env .get("model.name") which is NOT a valid Odoo API.

The Odoo Environment object does NOT have a .get() method for model access.
This pattern silently returns None instead of the model, causing bugs.

Correct patterns:
- self.env["model.name"]           # Access model (raises KeyError if not found)
- "model.name" in self.env         # Check if model exists
- self.env.ref("xml.id", raise_if_not_found=False)  # Get record by XML ID

Usage:
    python3 ci/check_env_get.py [--fix] [root_dir]

Options:
    --fix    Auto-fix simple cases (direct access without None check)

Exit codes:
    0 = No issues found (or all fixed with --fix)
    1 = Issues found (blocks CI)
"""

import re
import subprocess
import sys
from pathlib import Path

EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "odoo-enterprise",
    "docs",
}


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


def should_skip_file(filepath: Path) -> bool:
    """Check if file should be skipped."""
    parts = filepath.parts
    return any(excl in parts for excl in EXCLUDE_DIRS)


def check_env_get_pattern(root_dir: Path, fix: bool = False) -> list[dict]:
    """Find forbidden self.env.get() patterns in Python files."""
    errors = []
    fixed_count = 0

    py_files = get_git_tracked_files("*.py")
    if not py_files:
        py_files = list(root_dir.rglob("*.py"))

    # Pattern: self.env .get("model.name") or self.env .get('model.name')
    # Captures: the full .env .get("model.name") and the model name
    env_get_pattern = re.compile(r'\.env\.get\s*\(\s*(["\'])([a-z_]+\.[a-z_.]+)\1\s*\)')

    for py_file in py_files:
        if should_skip_file(py_file):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            lines = content.splitlines()
        except Exception:
            continue

        file_modified = False
        new_lines = []

        for i, line in enumerate(lines, 1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#"):
                new_lines.append(line)
                continue

            match = env_get_pattern.search(line)
            if match:
                quote_char = match.group(1)
                model_name = match.group(2)

                if fix:
                    # Auto-fix: Replace .env.get("model") with .env["model"]
                    # This is safe for direct access patterns
                    fixed_line = env_get_pattern.sub(f".env[{quote_char}{model_name}{quote_char}]", line)
                    new_lines.append(fixed_line)
                    file_modified = True
                    fixed_count += 1
                    print(f"   Fixed: {py_file}:{i}")
                    print(f"      Was:  {line.strip()}")
                    print(f"      Now:  {fixed_line.strip()}")
                else:
                    new_lines.append(line)
                    errors.append(
                        {
                            "file": str(py_file),
                            "line": i,
                            "code": line.strip(),
                            "message": (
                                "self.env.get() is NOT a valid Odoo API for model access. "
                                f'Use self.env["{model_name}"] instead.'
                            ),
                        }
                    )
            else:
                new_lines.append(line)

        if fix and file_modified:
            py_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    if fix and fixed_count > 0:
        print(f"\n✅ Auto-fixed {fixed_count} env.get() violations")
        print("⚠️  Review changes - some may need manual adjustment for None checks")

    return errors


def main():
    fix_mode = "--fix" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--fix"]
    root_dir = Path(args[0] if args else ".")

    if fix_mode:
        print("🔧 Auto-fixing env.get() anti-patterns...")
    else:
        print("🔍 Checking for env.get() anti-pattern...")

    errors = check_env_get_pattern(root_dir, fix=fix_mode)

    if errors:
        print(f"\n❌ Found {len(errors)} env.get() violations:")
        for err in errors:
            print(f"   {err['file']}:{err['line']}")
            print(f"      Code: {err['code']}")
            print(f"      Fix:  {err['message']}")
            print()
        print("=" * 70)
        print("WHY THIS IS WRONG:")
        print("  self.env .get('model.name') returns None (env has no .get() method)")
        print("  This causes silent failures when the code expects a model.")
        print()
        print("CORRECT PATTERNS:")
        print('  self.env["model.name"]                    # Access model directly')
        print('  "model.name" in self.env                  # Check if model exists')
        print('  self.env.ref("xml.id", raise_if_not_found=False)  # Get by XML ID')
        print()
        print("AUTO-FIX:")
        print("  Run with --fix flag: python3 ci/check_env_get.py --fix")
        print("=" * 70)
        sys.exit(1)
    else:
        print("✅ No env.get() anti-patterns found!")
        sys.exit(0)


if __name__ == "__main__":
    main()
