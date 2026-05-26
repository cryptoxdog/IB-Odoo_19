#!/usr/bin/env python3
"""
PR Autopilot — gather all PR signals, classify issues, apply safe auto-fixes.

Usage:
    python3 scripts/pr_autopilot.py          # report only (no changes)
    python3 scripts/pr_autopilot.py --fix    # report + apply safe auto-fixes + push

Sources polled:
  - GitHub Actions CI job logs (latest run on current branch)
  - SonarCloud issues API (PR-scoped analysis)
  - CodeRabbit review comments (PR comments from coderabbitai[bot])
  - GitHub PR review comments (all reviewers)

Issue classification:
  AUTO_FIX   — safe to fix automatically (ruff lint/format, import sort)
  REAL_BUG   — genuine code issue, flagged for manual fix
  FALSE_POS  — scanner/test false positive (documented pattern)
  ADVISORY   — informational, no action required
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import ssl
import subprocess

try:
    import certifi  # type: ignore[import-untyped]

    _SSL_CAFILE = certifi.where()
except ImportError:
    _SSL_CAFILE = None
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Config ───────────────────────────────────────────────────────────────────

REPO = "cryptoxdog/IB-Odoo_19"
REPO_ROOT = Path(__file__).parent.parent

# Load credentials from .env.local
_env = {}
env_file = REPO_ROOT / ".env.local"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            _env[k.strip()] = v.strip()

SONAR_TOKEN = _env.get("SONARCLOUD_API_KEY", "")
SONAR_PROJECT = "cryptoxdog_IB-Odoo_19"
CODERABBIT_TOKEN = _env.get("CODERABBIT_API_KEY", "")


# GitHub token from git credential store
def _get_gh_token() -> str:
    try:
        result = subprocess.run(
            ["git", "credential", "fill"],
            input="url=https://github.com\n",
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        for line in result.stdout.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1]
    except Exception:
        pass
    return os.environ.get("GH_TOKEN", "")


GH_TOKEN = _get_gh_token()

# ── HTTP helpers ──────────────────────────────────────────────────────────────


def _make_ssl_ctx() -> ssl.SSLContext:
    """Build a secure SSL context using certifi if available, else system defaults."""
    ctx = ssl.create_default_context(cafile=_SSL_CAFILE)
    return ctx


def _http(method: str, url: str, token: str = "", data: dict | None = None) -> dict | list | str:
    req = urllib.request.Request(url, method=method)
    if token:
        req.add_header("Authorization", f"token {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/vnd.github+json")
    if data:
        req.data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, context=_make_ssl_ctx()) as r:
            body = r.read().decode()
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return body
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_msg": str(e)}


def gh(path: str, method: str = "GET", data: dict | None = None) -> Any:
    return _http(method, f"https://api.github.com{path}", token=GH_TOKEN, data=data)


def sonar(path: str) -> Any:
    return _http("GET", f"https://sonarcloud.io/api{path}", token=SONAR_TOKEN)


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class Issue:
    source: str  # "ci", "sonar", "coderabbit", "github_review"
    kind: str  # AUTO_FIX | REAL_BUG | FALSE_POS | ADVISORY
    file: str = ""
    line: int = 0
    message: str = ""
    rule: str = ""
    raw: dict = field(default_factory=dict)

    def __str__(self) -> str:
        loc = f"{self.file}:{self.line}" if self.file else "(repo-level)"
        return f"[{self.kind}][{self.source}] {loc} — {self.message[:120]}"


# ── Git helpers ───────────────────────────────────────────────────────────────


def current_branch() -> str:
    r = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, cwd=REPO_ROOT)
    return r.stdout.strip()


def find_pr(branch: str) -> dict | None:
    prs = gh(f"/repos/{REPO}/pulls?state=open&head=cryptoxdog:{branch}&per_page=5")
    if isinstance(prs, list) and prs:
        return prs[0]
    # Also search all open PRs for this branch
    all_prs = gh(f"/repos/{REPO}/pulls?state=open&per_page=30")
    if isinstance(all_prs, list):
        for pr in all_prs:
            if pr.get("head", {}).get("ref") == branch:
                return pr
    return None


# ── CI signal ─────────────────────────────────────────────────────────────────

# Patterns that are known false positives from CI — don't flag as REAL_BUG
_CI_FALSE_POS_PATTERNS = [
    r"pre-existing wiring issues",
    r"advisory",
    r"warn.only",
    r"MEDIUM.*UNSCOPED",  # xpath medium warnings are advisory
]

# Auto-fixable CI failures
_CI_AUTO_FIX = {
    "ruff": "ruff check --fix . && ruff format .",
    "import": "ruff check --fix --select=I .",
    "format": "ruff format .",
}


def _classify_ci_step(step_name: str, log_excerpt: str) -> str:
    low = (step_name + log_excerpt).lower()
    if any(re.search(p, log_excerpt, re.IGNORECASE) for p in _CI_FALSE_POS_PATTERNS):
        return "FALSE_POS"
    if "ruff" in low or "import" in low or "format" in low or "reformat" in low:
        return "AUTO_FIX"
    return "REAL_BUG"


def get_ci_issues(branch: str) -> list[Issue]:
    issues = []
    runs = gh(f"/repos/{REPO}/actions/runs?branch={branch}&per_page=5")
    if not isinstance(runs, dict):
        return issues

    # Find latest CI Gate run
    ci_run = None
    for run in runs.get("workflow_runs", []):
        if run.get("name") == "CI Gate":
            ci_run = run
            break

    if not ci_run:
        return issues

    run_id = ci_run["id"]
    status = ci_run.get("conclusion", "in_progress")
    if status == "success":
        return issues  # nothing to report

    jobs = gh(f"/repos/{REPO}/actions/runs/{run_id}/jobs")
    if not isinstance(jobs, dict):
        return issues

    for job in jobs.get("jobs", []):
        if job.get("conclusion") not in ("failure", "timed_out"):
            continue
        job_name = job["name"]
        job_id = job["id"]

        # Get log
        log_raw = gh(f"/repos/{REPO}/actions/jobs/{job_id}/logs")
        log = log_raw if isinstance(log_raw, str) else ""

        # Find failed steps
        for step in job.get("steps", []):
            if step.get("conclusion") != "failure":
                continue
            step_name = step["name"]

            # Extract relevant log lines
            excerpt_lines = []
            for line in log.splitlines():
                if (
                    "error" in line.lower()
                    or "failed" in line.lower()
                    or "reformat" in line.lower()
                    or "would" in line.lower()
                ):
                    clean = re.sub(r"^\d{4}-\d{2}-\d{2}T[\d:\.Z]+ ", "", line)
                    if clean and not clean.startswith("[command]"):
                        excerpt_lines.append(clean)
            excerpt = "\n".join(excerpt_lines[:20])

            kind = _classify_ci_step(step_name, excerpt)
            issues.append(
                Issue(
                    source="ci",
                    kind=kind,
                    message=f"Job '{job_name}' / Step '{step_name}'\n{excerpt[:400]}",
                    rule=step_name,
                    raw={"job": job_name, "step": step_name, "log": excerpt},
                )
            )

    return issues


# ── SonarCloud signal ─────────────────────────────────────────────────────────

# SonarCloud rules that are false positives for this codebase
_SONAR_FALSE_POS_RULES = {
    "python:S1192",  # Duplicate string literals — intentional in Odoo (model constants)
    "python:S117",  # Variable naming — Odoo ORM uses PascalCase for model proxies
    "python:S3776",  # Cognitive complexity — complex Odoo methods are expected
    "python:S1135",  # TODO comments — tracked, not forgotten
    "python:S125",  # Commented-out code — sometimes needed for Odoo patterns
}

# SonarCloud rules that indicate real bugs
_SONAR_REAL_BUG_RULES = {
    "python:S1244",  # Float equality — use assertAlmostEqual
    "python:S5890",  # Type hint mismatch — real type error
}


def get_sonar_issues(pr_number: int | None) -> list[Issue]:
    issues = []
    if not SONAR_TOKEN:
        return issues

    path = f"/issues/search?projectKeys={SONAR_PROJECT}&statuses=OPEN&ps=50"
    if pr_number:
        path += f"&pullRequest={pr_number}"

    data = sonar(path)
    if not isinstance(data, dict):
        return issues

    for item in data.get("issues", []):
        rule = item.get("rule", "")
        severity = item.get("severity", "INFO")
        itype = item.get("type", "CODE_SMELL")
        msg = item.get("message", "")
        component = item.get("component", "").split(":")[-1]
        line = item.get("line", 0)

        if rule in _SONAR_FALSE_POS_RULES:
            kind = "FALSE_POS"
        elif rule in _SONAR_REAL_BUG_RULES or itype in ("BUG", "VULNERABILITY"):
            kind = "REAL_BUG"
        elif severity in ("CRITICAL", "BLOCKER") and itype == "BUG":
            kind = "REAL_BUG"
        else:
            kind = "ADVISORY"

        issues.append(
            Issue(
                source="sonar",
                kind=kind,
                file=component,
                line=line,
                message=f"[{severity}] {itype} {rule}: {msg}",
                rule=rule,
                raw=item,
            )
        )

    return issues


# ── CodeRabbit signal ─────────────────────────────────────────────────────────


def get_coderabbit_issues(pr_number: int | None) -> list[Issue]:
    """Get CodeRabbit review comments from GitHub PR comments."""
    issues = []
    if not pr_number:
        return issues

    # CodeRabbit posts as review comments on the PR
    comments = gh(f"/repos/{REPO}/pulls/{pr_number}/comments?per_page=100")
    if not isinstance(comments, list):
        return issues

    for comment in comments:
        user = comment.get("user", {}).get("login", "")
        if "coderabbit" not in user.lower():
            continue

        body = comment.get("body", "")
        path = comment.get("path", "")
        line = comment.get("line") or comment.get("original_line") or 0

        # Classify based on content
        low = body.lower()
        if any(w in low for w in ["actionable", "suggestion", "fix", "should", "must", "error", "bug", "issue"]):
            kind = "REAL_BUG"
        elif any(w in low for w in ["nitpick", "minor", "style", "consider", "optional"]):
            kind = "ADVISORY"
        else:
            kind = "ADVISORY"

        # Truncate long comments
        summary = body[:300].replace("\n", " ").strip()
        issues.append(
            Issue(
                source="coderabbit",
                kind=kind,
                file=path,
                line=line,
                message=summary,
                raw=comment,
            )
        )

    # Also check issue comments (CodeRabbit summary)
    issue_comments = gh(f"/repos/{REPO}/issues/{pr_number}/comments?per_page=50")
    if isinstance(issue_comments, list):
        for comment in issue_comments:
            user = comment.get("user", {}).get("login", "")
            if "coderabbit" not in user.lower():
                continue
            body = comment.get("body", "")
            # Extract actionable items from summary
            for line in body.splitlines():
                line = line.strip()
                if line.startswith(("- [ ]", "* [ ]", "🔴", "🟠", "⚠️")):
                    issues.append(
                        Issue(
                            source="coderabbit",
                            kind="REAL_BUG" if "🔴" in line else "ADVISORY",
                            message=line[:200],
                            raw={"comment_id": comment.get("id")},
                        )
                    )

    return issues


# ── GitHub review comments ────────────────────────────────────────────────────


def get_review_issues(pr_number: int | None) -> list[Issue]:
    issues = []
    if not pr_number:
        return issues

    reviews = gh(f"/repos/{REPO}/pulls/{pr_number}/reviews?per_page=50")
    if not isinstance(reviews, list):
        return issues

    for review in reviews:
        user = review.get("user", {}).get("login", "")
        if "coderabbit" in user.lower() or "bot" in user.lower():
            continue
        state = review.get("state", "")
        body = review.get("body", "")
        if body and state in ("CHANGES_REQUESTED", "COMMENTED"):
            issues.append(
                Issue(
                    source="github_review",
                    kind="REAL_BUG" if state == "CHANGES_REQUESTED" else "ADVISORY",
                    message=f"[{user}] {body[:300]}",
                    raw=review,
                )
            )

    return issues


# ── Auto-fix engine ───────────────────────────────────────────────────────────


def apply_auto_fixes(issues: list[Issue]) -> list[str]:
    """Apply safe auto-fixes. Returns list of fix descriptions."""
    applied = []
    auto_fix_issues = [i for i in issues if i.kind == "AUTO_FIX"]
    if not auto_fix_issues:
        return applied

    # Collect what needs fixing
    needs_ruff = any(
        "ruff" in i.rule.lower() or "format" in i.rule.lower() or "lint" in i.rule.lower() for i in auto_fix_issues
    )
    needs_import_sort = any("import" in i.message.lower() or "I001" in i.message for i in auto_fix_issues)
    needs_float = any("S1244" in i.rule or "float" in i.message.lower() for i in auto_fix_issues)

    if needs_import_sort or needs_ruff:
        print("  → Running ruff check --fix (import sort + lint) ...")
        result = subprocess.run(["ruff", "check", "--fix", "."], capture_output=True, text=True, cwd=REPO_ROOT)
        applied.append(f"ruff check --fix: {result.stdout.strip() or 'no output'}")

    if needs_ruff:
        print("  → Running ruff format ...")
        result = subprocess.run(["ruff", "format", "."], capture_output=True, text=True, cwd=REPO_ROOT)
        applied.append(f"ruff format: {result.stdout.strip() or 'no output'}")

    if needs_float:
        print("  ⚠  Float equality (S1244) requires manual fix — use assertAlmostEqual()")
        applied.append("MANUAL REQUIRED: Float equality checks — replace == with assertAlmostEqual(x, y, places=5)")

    return applied


def commit_and_push(branch: str, fix_descriptions: list[str]) -> bool:
    """Commit any changed files and push to remote via GitHub API."""
    # Check what changed
    result = subprocess.run(["git", "diff", "--name-only"], capture_output=True, text=True, cwd=REPO_ROOT)
    changed = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    if not changed:
        print("  No files changed — nothing to commit.")
        return False

    print(f"  Changed files: {', '.join(changed)}")

    # Get GitHub token
    token = GH_TOKEN
    if not token:
        print("  ❌ No GitHub token — cannot push via API")
        return False

    def api_put(fpath: str, content: bytes, sha: str, msg: str) -> str | None:
        url = f"https://api.github.com/repos/{REPO}/contents/{fpath}"
        data = json.dumps(
            {
                "message": msg,
                "content": base64.b64encode(content).decode(),
                "sha": sha,
                "branch": branch,
            }
        ).encode()
        req = urllib.request.Request(url, method="PUT", data=data)
        req.add_header("Authorization", f"token {token}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, context=_make_ssl_ctx()) as r:
                d = json.load(r)
                return d.get("commit", {}).get("sha", "")[:8]
        except Exception as e:
            print(f"    API error for {fpath}: {e}")
            return None

    commit_msg = "fix(autopilot): auto-fix CI/SonarCloud issues\n\n" + "\n".join(f"- {d}" for d in fix_descriptions)
    pushed = []

    for fpath in changed:
        full_path = REPO_ROOT / fpath
        if not full_path.exists():
            continue
        # Get current SHA on remote
        resp = gh(f"/repos/{REPO}/contents/{fpath}?ref={branch}")
        if not isinstance(resp, dict) or "_error" in resp:
            print(f"    ⚠  Cannot get SHA for {fpath}")
            continue
        remote_sha = resp.get("sha", "")
        sha = api_put(fpath, full_path.read_bytes(), remote_sha, commit_msg)
        if sha:
            pushed.append(f"{fpath} → {sha}")
            print(f"    ✅ Pushed {fpath}: {sha}")

    return bool(pushed)


# ── Report ────────────────────────────────────────────────────────────────────


def print_report(all_issues: list[Issue], pr_number: int | None, branch: str) -> None:
    sep = "=" * 70
    print(f"\n{sep}")
    print("PR AUTOPILOT REPORT")
    print(f"Branch: {branch}  |  PR: #{pr_number or 'none found'}")
    print(sep)

    by_kind: dict[str, list[Issue]] = {"AUTO_FIX": [], "REAL_BUG": [], "FALSE_POS": [], "ADVISORY": []}
    for issue in all_issues:
        by_kind.setdefault(issue.kind, []).append(issue)

    icons = {"AUTO_FIX": "🔧", "REAL_BUG": "🔴", "FALSE_POS": "⚪", "ADVISORY": "🔵"}
    for kind in ("REAL_BUG", "AUTO_FIX", "ADVISORY", "FALSE_POS"):
        issues = by_kind.get(kind, [])
        if not issues:
            continue
        print(f"\n{icons[kind]} {kind} ({len(issues)})")
        print("-" * 50)
        for i in issues:
            print(f"  [{i.source}] {i.file or ''}{f':{i.line}' if i.line else ''}")
            for line in i.message[:300].splitlines():
                print(f"    {line}")

    print(f"\n{sep}")
    print(
        f"SUMMARY: {len(by_kind['REAL_BUG'])} real bugs  |  "
        f"{len(by_kind['AUTO_FIX'])} auto-fixable  |  "
        f"{len(by_kind['ADVISORY'])} advisory  |  "
        f"{len(by_kind['FALSE_POS'])} false positives"
    )
    print(sep)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="PR Autopilot — gather all PR signals and optionally fix them")
    parser.add_argument("--fix", action="store_true", help="Apply safe auto-fixes and push to branch")
    parser.add_argument("--branch", help="Override branch name (default: current git branch)")
    args = parser.parse_args()

    branch = args.branch or current_branch()
    if not branch:
        print("❌ Cannot determine current branch")
        return 1

    print(f"🔍 Scanning branch: {branch}")

    # Find PR
    print("  → Looking up PR ...")
    pr = find_pr(branch)
    pr_number = pr["number"] if pr else None
    if pr_number:
        print(f"  → Found PR #{pr_number}: {pr.get('title', '')[:60]}")
    else:
        print("  → No open PR found for this branch (CI results still available)")

    # Gather all signals
    print("  → Fetching CI results ...")
    ci_issues = get_ci_issues(branch)

    print("  → Fetching SonarCloud issues ...")
    sonar_issues = get_sonar_issues(pr_number)

    print("  → Fetching CodeRabbit comments ...")
    cr_issues = get_coderabbit_issues(pr_number)

    print("  → Fetching GitHub review comments ...")
    review_issues = get_review_issues(pr_number)

    all_issues = ci_issues + sonar_issues + cr_issues + review_issues

    # Print report
    print_report(all_issues, pr_number, branch)

    if not args.fix:
        auto_fixable = [i for i in all_issues if i.kind == "AUTO_FIX"]
        real_bugs = [i for i in all_issues if i.kind == "REAL_BUG"]
        if auto_fixable:
            print(f"\n💡 Run with --fix to auto-apply {len(auto_fixable)} fixable issue(s)")
        if real_bugs:
            print(f"⚠️  {len(real_bugs)} real bug(s) require manual review")
        return 1 if real_bugs else 0

    # Apply fixes
    print("\n🔧 Applying auto-fixes ...")
    fix_descriptions = apply_auto_fixes(all_issues)

    if fix_descriptions:
        # Run pr-check before pushing
        print("\n→ Running make pr-check before push ...")
        result = subprocess.run(["make", "pr-check"], cwd=REPO_ROOT)
        if result.returncode != 0:
            print("❌ make pr-check failed — not pushing. Fix the issues above first.")
            return 1

        print("\n→ Pushing fixes via GitHub API ...")
        pushed = commit_and_push(branch, fix_descriptions)
        if pushed:
            print("\n✅ Fixes pushed — CI will re-trigger automatically")
        else:
            print("\n⚠️  No changes were pushed")
    else:
        print("  No auto-fixable issues found.")

    real_bugs = [i for i in all_issues if i.kind == "REAL_BUG"]
    return 1 if real_bugs else 0


if __name__ == "__main__":
    sys.exit(main())
