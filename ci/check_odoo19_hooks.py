#!/usr/bin/env python3
"""
Odoo 19 Hook Pattern Checker
============================

Prevents common Odoo 19 post_init_hook errors that cause module load failures.

Patterns checked:
1. ORM write to res.users.groups_id in hooks (KeyError: 'groups_id')
2. ORM write to res.groups.users in hooks (KeyError: 'users')

Correct pattern: Use direct SQL INSERT INTO res_groups_users_rel

Usage:
    python3 ci/check_odoo19_hooks.py [root_dir]

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


def check_hook_patterns(root_dir: Path) -> list[dict]:
    """Find forbidden ORM patterns in hooks.py files."""
    errors = []

    # Only check git-tracked files
    hook_files = get_git_tracked_files("*/hooks.py")
    if not hook_files:
        # Fallback to glob if not in git repo
        hook_files = list(root_dir.glob("*/hooks.py"))

    for hook_file in hook_files:
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

    return errors


def main():
    root_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")

    print("🔍 Checking Odoo 19 hook patterns...")
    errors = check_hook_patterns(root_dir)

    if errors:
        print(f"\n❌ Found {len(errors)} forbidden hook patterns:")
        for err in errors:
            print(f"   {err['file']}:{err['line']}")
            print(f"      {err['message']}")
        print("\n" + "=" * 60)
        print("FIX: Replace ORM write with direct SQL:")
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
        print("=" * 60)
        sys.exit(1)
    else:
        print("✅ All hook patterns are Odoo 19 compliant!")
        sys.exit(0)


if __name__ == "__main__":
    main()
