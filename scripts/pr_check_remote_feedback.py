#!/usr/bin/env python3
"""pr-check remote gate — GitHub Actions logs + review comments via pr_autopilot.

Usage:
  python3 scripts/pr_check_remote_feedback.py
  python3 scripts/pr_check_remote_feedback.py --pr 100
  python3 scripts/pr_check_remote_feedback.py --pr https://github.com/cryptoxdog/IB-Odoo_19/pull/100

Environment:
  PR_REMOTE_REF — same as --pr (set by Makefile when URL is passed as a goal)
  PR_CHECK_SKIP_REMOTE=1 — skip this gate
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from pr_autopilot import (  # noqa: E402
    GH_TOKEN,
    Issue,
    current_branch,
    gather_all_signals,
    print_report,
    resolve_pr_ref,
)

_FAIL_CI = frozenset({"failure", "cancelled", "timed_out", "action_required"})


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remote PR feedback gate for make pr-check")
    parser.add_argument(
        "--pr",
        dest="pr_ref",
        default=os.environ.get("PR_REMOTE_REF", "").strip() or None,
        help="PR number or GitHub pull URL (overrides branch-based PR lookup)",
    )
    return parser.parse_args()


def _gate_decision(
    issues: list[Issue],
    ci_conclusion: str | None,
    pr_number: int | None,
) -> tuple[bool, list[str]]:
    """Return (should_fail, reasons)."""
    reasons: list[str] = []

    if ci_conclusion in _FAIL_CI:
        reasons.append(f"GitHub Actions CI Gate: {ci_conclusion}")

    real_bugs = [i for i in issues if i.kind == "REAL_BUG"]
    if real_bugs:
        reasons.append(f"{len(real_bugs)} REAL_BUG signal(s) from CI/Sonar/reviews")

    changes_requested = [
        i
        for i in issues
        if i.source == "github_review" and "CHANGES_REQUESTED" in (i.raw.get("state", "") if i.raw else "")
    ]
    if changes_requested:
        reasons.append(f"{len(changes_requested)} human review(s) with CHANGES_REQUESTED")

    if ci_conclusion in (None, "in_progress", "queued", "waiting", "pending") and pr_number:
        print("  ⚠️  CI Gate still running — local pr-check passed; remote may change after push")

    auto_fix = [i for i in issues if i.kind == "AUTO_FIX"]
    if auto_fix:
        print(f"  ⚠️  {len(auto_fix)} remote AUTO_FIX item(s) — run `make pr-fix` or fix locally")

    advisory = sum(1 for i in issues if i.kind == "ADVISORY")
    false_pos = sum(1 for i in issues if i.kind == "FALSE_POS")
    if advisory or false_pos:
        print(f"  ℹ️  {advisory} advisory, {false_pos} false-positive (informational)")

    return bool(reasons), reasons


def main() -> int:
    if os.environ.get("PR_CHECK_SKIP_REMOTE") == "1":
        print("→ Remote PR feedback skipped (PR_CHECK_SKIP_REMOTE=1)")
        return 0

    args = _parse_args()
    pr_ref = args.pr_ref

    print("→ Remote PR feedback (GitHub Actions + review comments)...")
    if pr_ref:
        print(f"  → Target PR: {pr_ref}")

    if not GH_TOKEN:
        print("  ⚠️  No GitHub token — run `gh auth login` or set GITHUB_TOKEN")
        print("  Skipping remote gate (local checks still ran). Set token to enforce CI/review sync.")
        return 0

    branch = current_branch()
    if pr_ref:
        try:
            _pr, branch_from_pr, pr_number_hint = resolve_pr_ref(pr_ref)
        except ValueError as exc:
            print(f"❌ {exc}")
            return 1
        branch = branch_from_pr or branch
        issues, pr_number, _pr, ci_conclusion = gather_all_signals(
            branch,
            pr_ref=pr_ref,
            verbose=True,
        )
    else:
        if not branch:
            print("❌ Cannot determine current git branch (use --pr URL or number)")
            return 1
        issues, pr_number, _pr, ci_conclusion = gather_all_signals(branch, verbose=True)

    if not pr_number and ci_conclusion is None:
        print("  → No PR and no CI Gate run — remote gate skipped")
        print("  Tip: make pr-check pr=https://github.com/cryptoxdog/IB-Odoo_19/pull/N")
        return 0

    print_report(issues, pr_number, branch or "(pr head)")

    should_fail, reasons = _gate_decision(issues, ci_conclusion, pr_number)
    if should_fail:
        print("\n❌ Remote PR gate FAILED:")
        for r in reasons:
            print(f"   - {r}")
        print("   Fix issues above, or run `make pr-fix pr=<n>` for auto-fixable CI findings.")
        print("   Bypass (not recommended): PR_CHECK_SKIP_REMOTE=1 make push")
        return 1

    print("\n✅ Remote PR feedback gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
