#!/usr/bin/env python3
"""
Safe GitHub API push — always runs make pr-check first.

Usage:
    python3 scripts/api_push.py

This script MUST be run before using the GitHub API to push code.
It enforces the same validation pipeline as `make push`.

Why this exists:
- When git push fails (Dropbox mmap timeout), the GitHub API is a last resort
- API pushes bypass git hooks entirely
- This script enforces validation before allowing API pushes
"""

import subprocess
import sys
from pathlib import Path


def main():
    # Ensure we're in repo root
    repo_root = Path(__file__).parent.parent

    print("=" * 70)
    print("GitHub API Push Pre-Flight Check")
    print("=" * 70)
    print()
    print("Running full validation pipeline (make pr-check)...")
    print("This ensures the same checks run regardless of push method.")
    print()
    print("-" * 70)

    # Run make pr-check in repo root
    result = subprocess.run(["make", "pr-check"], cwd=repo_root, capture_output=False, text=True)

    print()
    print("-" * 70)

    if result.returncode != 0:
        print()
        print("❌ VALIDATION FAILED — cannot push via API")
        print()
        print("Fix the issues above before pushing to GitHub.")
        print("The same checks would have run via git hooks if git push worked.")
        print()
        sys.exit(1)

    print()
    print("✅ VALIDATION PASSED — safe to push via API")
    print()
    print("Next steps:")
    print("  1. Read: .cursor/rules/70-github-api-commit.mdc")
    print("  2. Use the Python API helper to push your commits")
    print("  3. Verify the push succeeded on GitHub")
    print()
    print("Remember: The API is a LAST RESORT only when git push is broken.")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
