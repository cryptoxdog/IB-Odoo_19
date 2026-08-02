#!/usr/bin/env python3
"""
Gate a JSON audit report against a checked-in per-finding baseline.

Replaces raw CRITICAL/HIGH count comparisons (`ci/*` history) with a
fingerprint diff: only findings NOT already logged in the baseline file
fail the gate. See scripts/audit/baseline_utils.py for the rationale and
ci/baselines/README.md for how to add a new entry.

Usage:
    python3 scripts/audit/check_baseline.py <report.json> <baseline.json> \\
        --severities CRITICAL,HIGH --label "Comprehensive audit"

    # After reviewing new findings and confirming they're false positives /
    # accepted debt, print ready-to-paste baseline entries:
    python3 scripts/audit/check_baseline.py <report.json> <baseline.json> \\
        --severities CRITICAL,HIGH --dump-new
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from baseline_utils import baseline_entry, diff_findings, load_baseline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Audit report JSON (list of findings)")
    parser.add_argument("baseline", type=Path, help="Baseline allowlist JSON (ci/baselines/*.json)")
    parser.add_argument(
        "--severities",
        default="CRITICAL,HIGH",
        help="Comma-separated severities that gate CI (default: CRITICAL,HIGH)",
    )
    parser.add_argument("--label", default=None, help="Human-readable name for step summary output")
    parser.add_argument(
        "--dump-new",
        action="store_true",
        help="Print ready-to-paste baseline entries for new findings and exit 0",
    )
    parser.add_argument(
        "--summary-file",
        type=Path,
        default=None,
        help="Append a markdown summary block here (e.g. $GITHUB_STEP_SUMMARY)",
    )
    args = parser.parse_args()

    label = args.label or args.report.stem
    gated_severities = {s.strip().upper() for s in args.severities.split(",") if s.strip()}

    if not args.report.exists():
        print(f"⚠️  {args.report} not found — skipping ({label})")
        return 0

    all_findings = json.loads(args.report.read_text())
    gated_findings = [f for f in all_findings if f.get("severity") in gated_severities]

    baseline = load_baseline(args.baseline)
    known, new, stale = diff_findings(gated_findings, baseline)

    if args.dump_new:
        if not new:
            print(f"No new findings vs baseline for {label}.")
            return 0
        print(f"# {len(new)} new finding(s) for {label} — review, then paste into {args.baseline}")
        print(json.dumps([baseline_entry(f) for f in new], indent=2))
        return 0

    print(f"=== {label} vs baseline ({args.baseline.name}) ===")
    print(f"  Known (logged, suppressed): {len(known)}")
    print(f"  New (not in baseline):      {len(new)}")
    if stale:
        print(f"  Stale baseline entries (fixed, safe to prune): {len(stale)}")

    if args.summary_file:
        with args.summary_file.open("a") as f:
            f.write(f"### {label}\n")
            f.write(f"- Known (logged): {len(known)}\n")
            f.write(f"- New (regression): {len(new)}\n")
            if stale:
                f.write(f"- Stale baseline entries: {len(stale)}\n")

    if new:
        print(f"\n❌ {len(new)} new {'/'.join(sorted(gated_severities))} finding(s) not in {args.baseline}:")
        for finding in new:
            loc = f"{finding.get('file', '?')}:{finding.get('line', '?')}"
            print(f"  - [{finding.get('severity')}] {finding.get('type')} @ {loc}: {finding.get('message', '')}")
        print(
            f"\nFix the code, or if this is a confirmed false positive / accepted debt, "
            f"add it to {args.baseline} (see: python3 {__file__} {args.report} {args.baseline} "
            f"--severities {args.severities} --dump-new)"
        )
        return 1

    print(f"\n✅ No new {label} findings vs baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
