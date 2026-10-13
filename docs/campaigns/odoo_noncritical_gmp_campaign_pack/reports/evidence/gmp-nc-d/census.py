"""Print the UNBOUNDED_SEARCH census for a scanner revision over a source tree.

python3 census.py <performance_audit.py> <repo-root>
"""

import importlib.util
import sys


def main() -> int:
    scanner, root = sys.argv[1], sys.argv[2]
    sys.path.insert(0, root + "/scripts/audit")
    spec = importlib.util.spec_from_file_location("performance_audit_census", scanner)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    findings = module.PerformanceAudit(root).check_unbounded_searches()
    for finding in sorted(findings, key=lambda f: (f["file"], f["line"])):
        print(f"{finding.get('bound', 'unbounded'):9} {finding['file']}:{finding['line']}  {finding['code']}")
    print("TOTAL", len(findings), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
