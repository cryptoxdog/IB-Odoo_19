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
    parser.add_argument(
        "--scanner-rc",
        type=int,
        default=None,
        help="Exit status of the scanner invocation that must have just produced the report",
    )
    parser.add_argument(
        "--newer-than",
        type=Path,
        default=None,
        help="Stamp file touched before that scanner invocation; the report must be newer",
    )
    args = parser.parse_args()

    label = args.label or args.report.stem
    gated_severities = {s.strip().upper() for s in args.severities.split(",") if s.strip()}

    def fail(message: str) -> int:
        print(f"❌ {label}: {message}", file=sys.stderr)
        return 1

    if not args.dump_new and (args.scanner_rc is None or args.newer_than is None):
        return fail("report is not bound to a scanner invocation (--scanner-rc and --newer-than are required)")

    if not args.report.is_file():
        return fail(f"{args.report} is missing; refusing to treat a missing report as zero findings")

    try:
        payload = json.loads(args.report.read_text())
    except json.JSONDecodeError as exc:
        return fail(f"{args.report} is not parseable JSON ({exc})")

    if not isinstance(payload, list):
        return fail(f"{args.report} must be a JSON list of findings")
    for index, item in enumerate(payload):
        if not isinstance(item, dict) or not isinstance(item.get("type"), str) or not item.get("type"):
            return fail(f"{args.report} finding {index} is missing a string type")
        if not isinstance(item.get("severity"), str) or not item.get("severity"):
            return fail(f"{args.report} finding {index} is missing a string severity")
    all_findings: list[dict] = payload

    if not args.dump_new and args.scanner_rc not in (0, 1):
        return fail(f"scanner execution failed (exit {args.scanner_rc}); a non-finding exit is not a baseline pass")

    if not args.dump_new:
        stamp = args.newer_than
        if not stamp.is_file():
            return fail(f"freshness stamp {stamp} is missing")
        if args.report.stat().st_mtime_ns <= stamp.stat().st_mtime_ns:
            return fail(f"{args.report} is not newer than this run; refusing a preexisting report")

    if not args.baseline.is_file():
        return fail(f"baseline {args.baseline} is missing")

    if args.scanner_rc == 1:
        print(f"scanner exit 1 is classified findings for {label}; the baseline comparison is the verdict")

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
