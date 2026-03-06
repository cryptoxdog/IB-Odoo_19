#!/usr/bin/env python3
"""
Audit Python files for syntax and import errors.

Catches SyntaxError, IndentationError before runtime.
"""

import ast
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def main():
    print("=" * 70)
    print("AUDIT: Python Syntax Check")
    print("=" * 70)

    errors = []
    files_checked = 0

    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules", ".venv", ".cursor"}]

        for f in files:
            if not f.endswith(".py"):
                continue

            path = Path(root) / f
            rel_path = path.relative_to(REPO_ROOT)
            files_checked += 1

            try:
                content = path.read_text(encoding="utf-8")
                ast.parse(content)
            except SyntaxError as e:
                errors.append((str(rel_path), f"SyntaxError: {e.msg} (line {e.lineno})"))
            except Exception as e:
                errors.append((str(rel_path), str(e)))

    print(f"\nFiles checked: {files_checked}")

    if errors:
        print("\n" + "!" * 70)
        print("🚨 SYNTAX ERRORS FOUND:")
        print("!" * 70)

        for path, err in errors:
            print(f"\n  {path}")
            print(f"    → {err}")

        print("\n" + "!" * 70)
        print(f"TOTAL ERRORS: {len(errors)}")
        print("!" * 70)
        return 1
    else:
        print("\n✅ All Python files have valid syntax.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
