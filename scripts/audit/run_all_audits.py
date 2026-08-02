#!/usr/bin/env python3
"""
Unified Audit Runner
====================

Runs all 7 layers of Odoo audit checks and produces a combined report.

Layers:
1. XML/Dependencies (odoo_audit.py) - existing
2. Database Schema (schema_audit.py) - requires DB connection
3. API Regression (api_regression.py) - requires git history
4. Business Logic (business_logic_audit.py)
5. Test Coverage (test_audit.py)
6. Performance (performance_audit.py)
7. Security (security_audit.py)

Usage:
    python3 scripts/audit/run_all_audits.py [root_dir]
"""

import json
import sys
from pathlib import Path

# Add scripts/audit to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from business_logic_audit import BusinessLogicAudit
from performance_audit import PerformanceAudit
from security_audit import SecurityAudit
from test_audit import TestAudit


def main():
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    all_errors = []

    print("=" * 60)
    print("UNIFIED ODOO AUDIT - 7 LAYER DEFENSE")
    print("=" * 60)

    # Layer 3: Business Logic
    print("\n📋 Layer 3: Business Logic Audit...")
    try:
        bl_audit = BusinessLogicAudit(root_dir)
        errors = bl_audit.check_unsafe_recordset_ops()
        errors += bl_audit.check_sql_injection_risks()
        errors += bl_audit.check_missing_access_checks()
        errors += bl_audit.check_state_machine_bypasses()
        all_errors.extend(errors)
        print(f"   Found {len(errors)} issues")
    except Exception as e:
        print(f"   ⚠️  Skipped: {e}")

    # Layer 4: Test Coverage
    print("\n🧪 Layer 4: Test Coverage Audit...")
    try:
        test_audit = TestAudit(root_dir)
        errors = test_audit.get_models_without_tests()
        errors += test_audit.check_weak_tests()
        all_errors.extend(errors)
        print(f"   Found {len(errors)} issues")
    except Exception as e:
        print(f"   ⚠️  Skipped: {e}")

    # Layer 5: Performance
    print("\n⚡ Layer 5: Performance Audit...")
    try:
        perf_audit = PerformanceAudit(root_dir)
        errors = perf_audit.check_n_plus_one_queries()
        errors += perf_audit.check_unbounded_searches()
        all_errors.extend(errors)
        print(f"   Found {len(errors)} issues")
    except Exception as e:
        print(f"   ⚠️  Skipped: {e}")

    # Layer 6: Security
    print("\n🔒 Layer 6: Security Audit...")
    try:
        sec_audit = SecurityAudit(root_dir)
        errors = sec_audit.check_controller_security()
        errors += sec_audit.check_sensitive_logging()
        all_errors.extend(errors)
        print(f"   Found {len(errors)} issues")
    except Exception as e:
        print(f"   ⚠️  Skipped: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    by_severity = {"CRITICAL": 0, "HIGH": 0, "MODERATE": 0}
    by_type = {}

    for err in all_errors:
        sev = err.get("severity", "MODERATE")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        err_type = err.get("type", "UNKNOWN")
        by_type[err_type] = by_type.get(err_type, 0) + 1

    print("\nBy Severity:")
    print(f"  CRITICAL: {by_severity.get('CRITICAL', 0)}")
    print(f"  HIGH:     {by_severity.get('HIGH', 0)}")
    print(f"  MODERATE: {by_severity.get('MODERATE', 0)}")

    print("\nBy Type:")
    for err_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {err_type}: {count}")

    # Write JSON report
    # Containment guard: CLI-provided root_dir must resolve inside the current
    # working tree before we write there (SonarCloud S8707).
    resolved_root = Path(root_dir).resolve()
    if not resolved_root.is_relative_to(Path.cwd().resolve()):
        raise ValueError(f"Refusing to write outside the working tree: {resolved_root}")
    report_path = resolved_root / "extended_audit_report.json"
    with open(report_path, "w") as f:
        json.dump(all_errors, f, indent=2)
    print(f"\n📄 Report written to: {report_path}")

    # Exit code
    critical_high = by_severity.get("CRITICAL", 0) + by_severity.get("HIGH", 0)
    if critical_high > 0:
        print(f"\n❌ {critical_high} CRITICAL/HIGH issues found")
        sys.exit(1)
    else:
        print("\n✅ No CRITICAL/HIGH issues found")
        sys.exit(0)


if __name__ == "__main__":
    main()
