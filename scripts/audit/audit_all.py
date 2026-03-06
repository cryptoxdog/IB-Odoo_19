#!/usr/bin/env python3
"""
Run all test audits and report results.

Usage:
    python scripts/audit/audit_all.py
"""

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def run_audit(name, script):
    """Run an audit script and return success status."""
    print("\n" + "=" * 70)
    print(f"Running: {name}")
    print("=" * 70)

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=False,
    )
    return result.returncode == 0


def main():
    print("=" * 70)
    print("PLASTICOS TEST AUDIT SUITE")
    print("=" * 70)

    audits = [
        ("Syntax Check", SCRIPT_DIR / "audit_imports.py"),
        ("Model References", SCRIPT_DIR / "audit_test_models.py"),
        ("Module Dependencies", SCRIPT_DIR / "audit_test_dependencies.py"),
    ]

    results = {}
    for name, script in audits:
        if script.exists():
            results[name] = run_audit(name, script)
        else:
            print(f"\n⚠️  Script not found: {script}")
            results[name] = False

    print("\n" + "=" * 70)
    print("AUDIT SUMMARY")
    print("=" * 70)

    all_passed = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {name}")
        if not passed:
            all_passed = False

    print("=" * 70)

    if all_passed:
        print("\n✅ All audits passed. Safe to deploy.")
        return 0
    else:
        print("\n❌ Some audits failed. Fix issues before deploying.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
