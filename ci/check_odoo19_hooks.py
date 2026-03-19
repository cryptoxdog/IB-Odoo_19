#!/usr/bin/env python3
"""
Odoo 19 Hook Pattern Checker
============================

Prevents common Odoo 19 hook errors that cause module load failures.

Patterns checked:
1. ORM write to res.users.groups_id in hooks (KeyError: 'groups_id')
2. ORM write to res.groups.users in hooks (KeyError: 'users')
3. pre_init_hook(cr) signature (Odoo 19 passes env, not cursor)

Correct patterns:
- Use direct SQL INSERT INTO res_groups_users_rel
- Use def pre_init_hook(env): with cr = env.cr

Usage:
    python3 ci/check_odoo19_hooks.py [--fix] [root_dir]

Exit codes:
    0 = No issues found
    1 = Issues found (blocks CI)
"""

import re
import subprocess
import sys
from pathlib import Path

AUTOFIX = "--fix" in sys.argv


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


def check_hook_patterns(root_dir: Path) -> tuple[list[dict], list[Path]]:
    """Find forbidden ORM patterns in hooks.py files.

    Returns:
        Tuple of (errors, files_to_fix) where files_to_fix have pre_init_hook(cr) signature.
    """
    errors = []
    files_to_fix = []

    # Only check git-tracked files
    hook_files = get_git_tracked_files("*/hooks.py")
    if not hook_files:
        # Fallback to glob if not in git repo
        hook_files = list(root_dir.glob("*/hooks.py"))

    # Also check __init__.py files that may have hooks
    init_files = get_git_tracked_files("*/__init__.py")
    if not init_files:
        init_files = list(root_dir.glob("*/__init__.py"))

    all_files = hook_files + init_files

    for hook_file in all_files:
        if "__pycache__" in str(hook_file):
            continue

        try:
            with open(hook_file, encoding="utf-8") as f:
                content = f.read()
                lines = content.splitlines()
        except Exception:
            continue

        # Pattern 1: write({"groups_id": ...}) on res.users
        for i, line in enumerate(lines, 1):
            if re.search(r'\.write\(\s*\{\s*["\']groups_id["\']', line):
                errors.append(
                    {
                        "file": str(hook_file),
                        "line": i,
                        "pattern": "groups_id write",
                        "message": (
                            "ORM write to groups_id forbidden in post_init_hook. "
                            "Use: env.cr.execute('INSERT INTO res_groups_users_rel ...')"
                        ),
                    }
                )

        # Pattern 2: write({"users": ...}) on res.groups
        for i, line in enumerate(lines, 1):
            if re.search(r'\.write\(\s*\{\s*["\']users["\']', line):
                errors.append(
                    {
                        "file": str(hook_file),
                        "line": i,
                        "pattern": "users write",
                        "message": (
                            "ORM write to res.groups.users forbidden in post_init_hook. "
                            "Use: env.cr.execute('INSERT INTO res_groups_users_rel ...')"
                        ),
                    }
                )

        # Pattern 3: pre_init_hook(cr) — Odoo 19 passes env, not cursor
        # Match: def pre_init_hook(cr): but NOT def pre_init_hook(env):
        for i, line in enumerate(lines, 1):
            match = re.search(r"def\s+pre_init_hook\s*\(\s*(\w+)\s*\)", line)
            if match:
                param_name = match.group(1)
                if param_name == "cr":
                    errors.append(
                        {
                            "file": str(hook_file),
                            "line": i,
                            "pattern": "pre_init_hook(cr)",
                            "message": (
                                "Odoo 19 passes env to pre_init_hook, not raw cursor. "
                                "Change to: def pre_init_hook(env): and add cr = env.cr"
                            ),
                            "fixable": True,
                        }
                    )
                    files_to_fix.append(hook_file)

    return errors, files_to_fix


def autofix_pre_init_hook(file_path: Path) -> bool:
    """Fix pre_init_hook(cr) → pre_init_hook(env) with cr = env.cr alias.

    Returns True if file was modified.
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return False

    # Pattern: def pre_init_hook(cr):
    # Replace with: def pre_init_hook(env):
    # And add cr = env.cr after the docstring or first line

    # Step 1: Replace signature
    new_content = re.sub(
        r"def\s+pre_init_hook\s*\(\s*cr\s*\)\s*:",
        "def pre_init_hook(env):",
        content,
    )

    if new_content == content:
        return False  # No change needed

    # Step 2: Add cr = env.cr after the function definition
    # Find the function and add cr = env.cr after docstring or first line
    def add_cr_alias(match):
        func_def = match.group(0)
        # Check if cr = env.cr already exists
        if "cr = env.cr" in func_def:
            return func_def

        # Find where to insert: after docstring or after def line
        lines = func_def.split("\n")
        result_lines = []
        inserted = False

        for i, line in enumerate(lines):
            result_lines.append(line)

            if inserted:
                continue

            # After def line, check for docstring
            if i == 0:  # def line
                continue

            # Skip docstring lines
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                # Single-line docstring
                if (stripped.count('"""') >= 2 or stripped.count("'''") >= 2) and len(stripped) > 6:
                    # Insert after this line
                    indent = len(line) - len(line.lstrip())
                    result_lines.append(" " * indent + "cr = env.cr")
                    inserted = True
                    continue
                # Multi-line docstring - wait for closing
                continue

            # Check if we're still in docstring
            if '"""' in stripped or "'''" in stripped:
                # End of docstring
                indent = len(line) - len(line.lstrip())
                result_lines.append(" " * indent + "cr = env.cr")
                inserted = True
                continue

            # If line is not empty and not a docstring, insert before it
            if stripped and not stripped.startswith("#"):
                # Get indentation from this line
                indent = len(line) - len(line.lstrip())
                # Insert cr = env.cr before this line
                result_lines.insert(-1, " " * indent + "cr = env.cr")
                inserted = True
                continue

        return "\n".join(result_lines)

    # Apply the cr alias insertion
    # Match the entire pre_init_hook function (greedy until next def or end)
    pattern = r"(def pre_init_hook\(env\):.*?)(?=\ndef |\Z)"
    new_content = re.sub(pattern, add_cr_alias, new_content, flags=re.DOTALL)

    # Write back
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    except Exception:
        return False


def main():
    # Parse args
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root_dir = Path(args[0] if args else ".")

    print("🔍 Checking Odoo 19 hook patterns...")
    errors, files_to_fix = check_hook_patterns(root_dir)

    # Autofix if requested
    if AUTOFIX and files_to_fix:
        print(f"\n🔧 Autofixing {len(files_to_fix)} files with pre_init_hook(cr)...")
        fixed_count = 0
        for file_path in set(files_to_fix):
            if autofix_pre_init_hook(file_path):
                print(f"   ✅ Fixed: {file_path}")
                fixed_count += 1
            else:
                print(f"   ⚠️  Could not autofix: {file_path}")

        if fixed_count > 0:
            # Re-check after fix
            print("\n🔄 Re-checking after autofix...")
            errors, _ = check_hook_patterns(root_dir)

    if errors:
        # Filter out fixable errors if we just fixed them
        remaining_errors = [e for e in errors if not (AUTOFIX and e.get("fixable"))]

        if remaining_errors:
            print(f"\n❌ Found {len(remaining_errors)} forbidden hook patterns:")
            for err in remaining_errors:
                print(f"   {err['file']}:{err['line']}")
                print(f"      {err['message']}")

            # Show fix instructions
            has_orm_errors = any(e["pattern"] in ("groups_id write", "users write") for e in remaining_errors)
            has_signature_errors = any(e["pattern"] == "pre_init_hook(cr)" for e in remaining_errors)

            if has_orm_errors:
                print("\n" + "=" * 60)
                print("FIX for ORM patterns: Replace with direct SQL:")
                print("""
    env.cr.execute(
        '''
        INSERT INTO res_groups_users_rel (gid, uid)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        ''',
        (group.id, user.id),
    )
""")

            if has_signature_errors:
                print("\n" + "=" * 60)
                print("FIX for pre_init_hook(cr): Odoo 19 passes env, not cursor.")
                print("Run with --fix to autofix, or manually change:")
                print("""
    # Before:
    def pre_init_hook(cr):
        cr.execute(...)

    # After:
    def pre_init_hook(env):
        cr = env.cr
        cr.execute(...)
""")
            print("=" * 60)
            sys.exit(1)

    print("✅ All hook patterns are Odoo 19 compliant!")
    sys.exit(0)


if __name__ == "__main__":
    main()
