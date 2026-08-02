#!/usr/bin/env python3
"""
PR Autopilot — read ALL CI outputs, classify ALL issues, apply ALL safe fixes
               in ONE atomic commit, re-triggering CI exactly once.

Usage:
    python3 scripts/pr_autopilot.py          # report only, no changes
    python3 scripts/pr_autopilot.py --fix    # fix everything + single commit + push

Sources polled:
  - GitHub Actions: EVERY job log in the latest run (success + failure)
  - SonarCloud API: all open issues scoped to the PR
  - CodeRabbit: all bot review comments
  - GitHub PR reviews: all human reviewer comments

Issue classification:
  AUTO_FIX   — safe to auto-apply (ruff lint/format/import-sort)
  REAL_BUG   — genuine code issue; flagged for manual fix
  FALSE_POS  — confirmed scanner false positive (documented pattern)
  ADVISORY   — informational; no action required

Fix strategy (--fix mode):
  1. Gather ALL issues from ALL sources
  2. Apply ALL auto-fixes locally (ruff check --fix + ruff format)
  3. Run make pr-check — must pass before any push
  4. Collect ALL changed files
  5. Single atomic commit via GitHub git-tree API → ONE CI re-trigger
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Allow sibling imports (pr_repair_adapter lives in the same scripts/ directory)
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from pr_repair_adapter import run_repair_loop as _pr_repair_run

    _PR_REPAIR_WIRED = True
except ImportError:
    _PR_REPAIR_WIRED = False

try:
    import certifi  # type: ignore[import-untyped]

    _SSL_CAFILE: str | None = certifi.where()
except ImportError:
    _SSL_CAFILE = None

# ── Config ────────────────────────────────────────────────────────────────────

REPO = "cryptoxdog/IB-Odoo_19"
REPO_ROOT = Path(__file__).parent.parent

_env: dict[str, str] = {}
env_file = REPO_ROOT / ".env.local"
if env_file.exists():
    for _line in env_file.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _, _v = _line.partition("=")
            _env[_k.strip()] = _v.strip()

SONAR_TOKEN = _env.get("SONARCLOUD_API_KEY", "")
SONAR_PROJECT = "cryptoxdog_IB-Odoo_19"

# ── HTTP ──────────────────────────────────────────────────────────────────────


def _make_ssl() -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=_SSL_CAFILE)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2  # enforce TLS 1.2+ explicitly
    return ctx


_SAFE_BRANCH_RE = re.compile(r"^[a-zA-Z0-9/_.\-]+$")


def _safe_ref(name: str) -> str:
    """Validate branch/ref name before embedding in API URL paths."""
    if not _SAFE_BRANCH_RE.match(name):
        raise ValueError(f"Unsafe branch name rejected: {name!r}")
    return name


def _get_gh_token() -> str:
    # Check environment first (GitHub Actions provides GITHUB_TOKEN)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token

    # Fall back to git credential store (local development)
    try:
        r = subprocess.run(
            ["git", "credential", "fill"],
            input="url=https://github.com\n",
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        for ln in r.stdout.splitlines():
            if ln.startswith("password="):
                return ln.split("=", 1)[1]
    except Exception:
        pass
    return ""


GH_TOKEN = _get_gh_token()


def _http(method: str, url: str, token: str = "", data: dict | None = None) -> Any:
    req = urllib.request.Request(url, method=method)
    if token:
        req.add_header("Authorization", f"token {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/vnd.github+json")
    if data:
        req.data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, context=_make_ssl()) as r:
            body = r.read().decode()
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return body
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_msg": str(e)}


def gh(path: str, method: str = "GET", data: dict | None = None) -> Any:
    return _http(method, f"https://api.github.com{path}", token=GH_TOKEN, data=data)


def _fetch_job_log(job_id: int) -> str:
    """Fetch a GitHub Actions job log.

    GitHub's /actions/jobs/{id}/logs returns a 302 redirect to an Azure Blob
    Storage pre-signed URL. If we follow the redirect with the Authorization
    header still set, Azure rejects it with 403 because Azure interprets the
    GitHub PAT as an invalid Azure credential.

    Strategy: use curl (always available in CI) with --location to follow
    redirects naturally, stripping the auth header on redirect automatically.
    Falls back to a two-step urllib approach if curl is unavailable.
    """
    api_url = f"https://api.github.com/repos/{REPO}/actions/jobs/{job_id}/logs"

    # Preferred path: curl handles redirect stripping correctly
    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-L",  # follow redirects
                "--max-redirs",
                "3",
                "-H",
                f"Authorization: token {GH_TOKEN}",
                "-H",
                "Accept: application/vnd.github+json",
                api_url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: two-step urllib — get redirect URL, then fetch without auth
    step1_req = urllib.request.Request(api_url)
    step1_req.add_header("Authorization", f"token {GH_TOKEN}")
    step1_req.add_header("Accept", "application/vnd.github+json")

    class _StopRedirect(urllib.request.HTTPRedirectHandler):
        def http_error_302(self, req, fp, code, msg, headers):  # type: ignore[override]
            raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

        http_error_301 = http_error_303 = http_error_307 = http_error_302

    opener = urllib.request.build_opener(_StopRedirect())
    try:
        with opener.open(step1_req) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        location = e.headers.get("Location") or e.headers.get("location") or ""
        if not location:
            return ""
        blob_req = urllib.request.Request(location)
        try:
            with urllib.request.urlopen(blob_req, context=_make_ssl()) as r:
                return r.read().decode()
        except Exception:
            return ""
    except Exception:
        return ""


def sonar(path: str) -> Any:
    return _http("GET", f"https://sonarcloud.io/api{path}", token=SONAR_TOKEN)


# ── Issue dataclass ───────────────────────────────────────────────────────────


@dataclass
class Issue:
    source: str  # ci | sonar | coderabbit | github_review
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
    r = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return r.stdout.strip()


_PR_URL_RE = re.compile(
    r"github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<num>\d+)",
    re.IGNORECASE,
)


def fetch_pr_by_number(pr_number: int) -> dict | None:
    """Fetch a pull request by number (open or closed)."""
    pr = gh(f"/repos/{REPO}/pulls/{pr_number}")
    if isinstance(pr, dict) and pr.get("number"):
        return pr
    return None


def resolve_pr_ref(ref: str | int) -> tuple[dict | None, str | None, int | None]:
    """Resolve PR URL or number → (pr_dict, head_branch, pr_number)."""
    pr_number: int | None = None
    if isinstance(ref, int):
        pr_number = ref
    elif str(ref).strip().isdigit():
        pr_number = int(str(ref).strip())
    else:
        text = str(ref).strip()
        match = _PR_URL_RE.search(text)
        if match:
            owner, repo, num = match.group("owner"), match.group("repo"), match.group("num")
            expected = REPO.split("/")
            if owner != expected[0] or repo != expected[1]:
                print(f"  ⚠️  PR URL repo {owner}/{repo} != {REPO} — using number from URL anyway")
            pr_number = int(num)
        else:
            raise ValueError(f"Unrecognized PR reference: {ref!r} (use URL or number)")

    pr = fetch_pr_by_number(pr_number) if pr_number else None
    if not pr:
        return None, None, pr_number
    branch = pr.get("head", {}).get("ref")
    return pr, branch, pr.get("number")


def find_pr(branch: str) -> dict | None:
    prs = gh(f"/repos/{REPO}/pulls?state=open&head=cryptoxdog:{branch}&per_page=5")
    if isinstance(prs, list) and prs:
        return prs[0]
    all_prs = gh(f"/repos/{REPO}/pulls?state=open&per_page=50")
    if isinstance(all_prs, list):
        for pr in all_prs:
            if pr.get("head", {}).get("ref") == branch:
                return pr
    return None


# ── Known false-positive patterns ─────────────────────────────────────────────

_GITLEAKS_FP_FINGERPRINTS = {
    "19f08514f46f1c9970ca122d0214a02a85014066:Makefile:curl-auth-user:273",
    "19f08514f46f1c9970ca122d0214a02a85014066:Makefile:generic-api-key:274",
}

_SONAR_FP_RULES = {
    "python:S1192",  # Duplicate string literals — intentional Odoo model constants
    "python:S117",  # Variable naming — Odoo uses PascalCase for model proxies
    "python:S3776",  # Cognitive complexity — complex Odoo methods are expected
    "python:S1135",  # TODO comments — tracked, not forgotten
    "python:S125",  # Commented-out code — sometimes needed for Odoo patterns
}

_SONAR_REAL_BUG_RULES = {
    "python:S1244",  # Float equality — use assertAlmostEqual
    "python:S5527",  # SSL hostname verification
    "python:S4423",  # Weak SSL protocol
    "python:S4830",  # Certificate validation disabled
    "python:S5890",  # Type hint mismatch
}

_CI_FP_PATTERNS = [
    r"pre-existing wiring issues",
    r"advisory",
    r"warn.only",
    r"MEDIUM.*UNSCOPED",
    r"\[MEDIUM\].*notebook",  # xpath medium warnings
]


# ── Gitleaks parser ───────────────────────────────────────────────────────────


def _parse_gitleaks(log: str) -> list[dict]:
    findings: list[dict] = []
    cur: dict = {}
    for raw_line in log.splitlines():
        ln = raw_line.strip()
        if ln.startswith("Finding:"):
            if cur:
                findings.append(cur)
            cur = {"finding": ln.split(":", 1)[-1].strip()}
        elif ":" in ln and cur:
            k, _, v = ln.partition(":")
            k = k.strip().lower().replace("ruleid", "rule").replace(" ", "_")
            if k in ("rule", "file", "line", "commit", "fingerprint", "secret", "entropy"):
                cur[k] = v.strip()
    if cur:
        findings.append(cur)
    return findings


def _classify_gitleaks(f: dict) -> str:
    if f.get("fingerprint", "") in _GITLEAKS_FP_FINGERPRINTS:
        return "FALSE_POS"
    ffile = f.get("file", "")
    rule = f.get("rule", "")
    if ffile == "Makefile" and rule in ("curl-auth-user", "generic-api-key"):
        return "FALSE_POS"
    if ".env" in ffile:
        return "REAL_BUG"
    return "REAL_BUG"


# ── Full CI log reader ────────────────────────────────────────────────────────


def _extract_issues_from_log(log: str, job_name: str) -> list[Issue]:
    """Extract ALL issues from a complete job log, regardless of pass/fail."""
    issues: list[Issue] = []

    # ── Gitleaks findings (always parse even if step succeeded) ──
    if "gitleaks" in log.lower() or "leaks found" in log.lower():
        for f in _parse_gitleaks(log):
            kind = _classify_gitleaks(f)
            rule = f.get("rule", "unknown")
            ffile = f.get("file", "")
            fline = f.get("line", "0")
            issues.append(
                Issue(
                    source="ci",
                    kind=kind,
                    file=ffile,
                    line=int(fline) if fline.isdigit() else 0,
                    message=(
                        f"[gitleaks:{rule}] {f.get('finding', '')[:120]}\n"
                        f"Fingerprint: {f.get('fingerprint', '')}\n"
                        f"Commit: {f.get('commit', '')[:12]}"
                    ),
                    rule=f"gitleaks:{rule}",
                    raw=f,
                )
            )

    # ── Ruff errors ──
    ruff_lines = []
    for raw_line in log.splitlines():
        ln = re.sub(r"^\d{4}-\d{2}-\d{2}T[\d:\.Z]+ ", "", raw_line).strip()
        if re.search(r"\.(py|toml):\d+:\d+:.*[A-Z]\d+", ln):
            ruff_lines.append(ln)
        elif "would reformat" in ln.lower() or "would be reformatted" in ln.lower():
            m = re.search(r"[Ww]ould reformat:?\s+([^\s]+\.py)", ln)
            fpath = m.group(1) if m else ""
            issues.append(
                Issue(
                    source="ci",
                    kind="AUTO_FIX",
                    file=fpath,
                    message=f"ruff format: {ln}",
                    rule="ruff-format",
                    raw={"job": job_name, "line": ln},
                )
            )

    for ln in ruff_lines:
        m = re.match(r"(.+?):(\d+):\d+:\s+([A-Z]\d+)", ln)
        if m:
            fpath, lineno, code = m.group(1), int(m.group(2)), m.group(3)
            kind = "AUTO_FIX" if code[0] in ("I", "E", "F", "W", "UP") else "REAL_BUG"
            issues.append(
                Issue(
                    source="ci",
                    kind=kind,
                    file=fpath,
                    line=lineno,
                    message=ln,
                    rule=f"ruff:{code}",
                    raw={"job": job_name},
                )
            )

    # ── pytest failures ──
    ftest = ""
    for raw_line in log.splitlines():
        ln = re.sub(r"^\d{4}-\d{2}-\d{2}T[\d:\.Z]+ ", "", raw_line).strip()
        if ln.startswith("FAILED ") and "::" in ln:
            test_id = ln.replace("FAILED ", "").split(" -")[0].strip()
            ftest = test_id.split("::")[0]
            kind = "REAL_BUG"
            if any(re.search(p, ln, re.IGNORECASE) for p in _CI_FP_PATTERNS):
                kind = "FALSE_POS"
            issues.append(
                Issue(
                    source="ci",
                    kind=kind,
                    file=ftest,
                    message=f"pytest FAILED: {test_id}",
                    rule="pytest",
                    raw={"job": job_name},
                )
            )
        if ln.startswith("_ ") and "FAILED" in ln or ln.startswith("E   "):
            pass  # Could collect details; keeping lean for now

    # ── Wiring / module errors ──
    for raw_line in log.splitlines():
        ln = re.sub(r"^\d{4}-\d{2}-\d{2}T[\d:\.Z]+ ", "", raw_line).strip()
        if "missing dependency declaration" in ln or "references model" in ln and "does not declare" in ln:
            kind = "REAL_BUG"
            if any(re.search(p, ln, re.IGNORECASE) for p in _CI_FP_PATTERNS):
                kind = "FALSE_POS"
            issues.append(
                Issue(
                    source="ci",
                    kind=kind,
                    message=ln[:200],
                    rule="module-wiring",
                    raw={"job": job_name},
                )
            )

    # ── Static check errors (non-ruff) ──
    for raw_line in log.splitlines():
        ln = re.sub(r"^\d{4}-\d{2}-\d{2}T[\d:\.Z]+ ", "", raw_line).strip()
        if re.match(r".+\.py:\d+.*CRON\d+|.+\.xml:\d+.*CRON\d+", ln):
            issues.append(
                Issue(
                    source="ci",
                    kind="REAL_BUG",
                    message=f"cron invariant: {ln[:200]}",
                    rule="cron-invariant",
                    raw={"job": job_name},
                )
            )

    return issues


def latest_ci_gate_run(branch: str) -> dict | None:
    """Return the latest 'CI Gate' workflow run for a branch, if any."""
    runs = gh(f"/repos/{REPO}/actions/runs?branch={_safe_ref(branch)}&per_page=10")
    if not isinstance(runs, dict):
        return None
    for run in runs.get("workflow_runs", []):
        if run.get("name") == "CI Gate":
            return run
    return None


def get_ci_issues(branch: str, *, verbose: bool = True) -> list[Issue]:
    """Get issues from the latest CI run — reads ALL job logs completely."""
    issues: list[Issue] = []

    ci_run = latest_ci_gate_run(branch)
    if not ci_run:
        return issues

    conclusion = ci_run.get("conclusion") or "in_progress"
    if conclusion == "success":
        if verbose:
            print("  ✅ CI Gate: all checks passed — no issues to fix")
        return issues

    run_id = ci_run["id"]
    if verbose:
        print(f"  → Reading CI run #{run_id} (conclusion: {conclusion})")

    jobs_resp = gh(f"/repos/{REPO}/actions/runs/{run_id}/jobs")
    if not isinstance(jobs_resp, dict):
        return issues

    for job in jobs_resp.get("jobs", []):
        job_name = job["name"]
        job_conclusion = job.get("conclusion", "")
        job_id = job["id"]

        # Always read logs for failed/cancelled jobs; skip cleanly-passing ones
        if job_conclusion == "success":
            continue

        if verbose:
            print(f"  → Reading log: {job_name} ({job_conclusion})")
        log = _fetch_job_log(job_id)

        job_issues = _extract_issues_from_log(log, job_name)
        if verbose:
            print(f"    Found {len(job_issues)} issue(s)")
        issues.extend(job_issues)

    # Deduplicate by (rule, file, line, message[:60])
    seen: set[tuple] = set()
    deduped: list[Issue] = []
    for i in issues:
        key = (i.rule, i.file, i.line, i.message[:60])
        if key not in seen:
            seen.add(key)
            deduped.append(i)

    return deduped


# ── SonarCloud ────────────────────────────────────────────────────────────────


def get_sonar_issues(pr_number: int | None) -> list[Issue]:
    if not SONAR_TOKEN:
        print("  ⚠  SONARCLOUD_API_KEY not set — skipping SonarCloud")
        return []

    path = f"/issues/search?projectKeys={SONAR_PROJECT}&statuses=OPEN&ps=100"
    if pr_number:
        path += f"&pullRequest={pr_number}"

    data = sonar(path)
    if not isinstance(data, dict):
        return []

    issues: list[Issue] = []
    for item in data.get("issues", []):
        rule = item.get("rule", "")
        severity = item.get("severity", "INFO")
        itype = item.get("type", "CODE_SMELL")
        msg = item.get("message", "")
        component = item.get("component", "").split(":")[-1]
        line = item.get("line", 0)

        if rule in _SONAR_FP_RULES:
            kind = "FALSE_POS"
        elif rule in _SONAR_REAL_BUG_RULES or itype in ("BUG", "VULNERABILITY"):
            kind = "REAL_BUG"
        elif severity in ("CRITICAL", "BLOCKER"):
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


# ── CodeRabbit ────────────────────────────────────────────────────────────────


def get_coderabbit_issues(pr_number: int | None) -> list[Issue]:
    if not pr_number:
        return []

    issues: list[Issue] = []

    # Inline review comments
    comments = gh(f"/repos/{REPO}/pulls/{pr_number}/comments?per_page=100")
    if isinstance(comments, list):
        for c in comments:
            if "coderabbit" not in c.get("user", {}).get("login", "").lower():
                continue
            body = c.get("body", "")
            low = body.lower()
            kind = "ADVISORY"
            if any(w in low for w in ("actionable", "must", "should fix", "bug", "error", "vulnerability")):
                kind = "REAL_BUG"
            issues.append(
                Issue(
                    source="coderabbit",
                    kind=kind,
                    file=c.get("path", ""),
                    line=c.get("line") or c.get("original_line") or 0,
                    message=body[:300].replace("\n", " "),
                    raw=c,
                )
            )

    # PR summary comment — extract checkboxes and flagged items
    issue_comments = gh(f"/repos/{REPO}/issues/{pr_number}/comments?per_page=50")
    if isinstance(issue_comments, list):
        for c in issue_comments:
            if "coderabbit" not in c.get("user", {}).get("login", "").lower():
                continue
            for ln in c.get("body", "").splitlines():
                ln = ln.strip()
                if ln.startswith(("🔴", "❌")) or ("actionable" in ln.lower() and "comment" in ln.lower()):
                    issues.append(
                        Issue(
                            source="coderabbit",
                            kind="REAL_BUG",
                            message=ln[:200],
                            raw={"comment_id": c.get("id")},
                        )
                    )

    return issues


# ── Gemini Code Assist reviews ───────────────────────────────────────────────

_GEMINI_BOT_NAMES = {"gemini-code-assist[bot]", "gemini-code-review[bot]", "gemini-code-assist"}

_SUGGESTION_RE = re.compile(r"```suggestion\r?\n(.*?)```", re.DOTALL)


def _extract_suggestions(body: str) -> list[str]:
    """Extract code suggestion blocks from a Gemini/GitHub review comment."""
    return [m.group(1) for m in _SUGGESTION_RE.finditer(body)]


def _suggestion_already_applied(suggestion: str, current_content: str) -> bool:
    """Check if the suggested code is already present in the current file content."""
    # Normalize whitespace for comparison
    norm_suggestion = "\n".join(line.rstrip() for line in suggestion.strip().splitlines())
    norm_current = "\n".join(line.rstrip() for line in current_content.splitlines())
    return norm_suggestion in norm_current


def _apply_suggestion(
    original_content: str,
    suggestion: str,
    start_line: int,
    end_line: int,
) -> str | None:
    """Replace lines [start_line, end_line] (1-indexed, inclusive) with suggestion."""
    lines = original_content.splitlines(keepends=True)
    if start_line < 1 or end_line > len(lines):
        return None
    new_lines = lines[: start_line - 1] + [suggestion.rstrip("\n") + "\n"] + lines[end_line:]
    return "".join(new_lines)


def get_gemini_issues(pr_number: int | None, branch: str) -> list[Issue]:
    """Read Gemini Code Assist review comments, classify each, and check if
    suggested code fixes are already applied or need to be applied."""
    if not pr_number:
        return []

    issues: list[Issue] = []

    # 1. Read all inline review comments from Gemini
    comments = gh(f"/repos/{REPO}/pulls/{pr_number}/comments?per_page=100")
    if not isinstance(comments, list):
        return []

    gemini_comments = [
        c
        for c in comments
        if c.get("user", {}).get("login", "").lower() in _GEMINI_BOT_NAMES
        or "gemini" in c.get("user", {}).get("login", "").lower()
    ]

    if not gemini_comments:
        return []

    print(f"  → Gemini Code Assist: {len(gemini_comments)} inline comment(s)")

    # Cache file contents to avoid re-fetching
    _file_cache: dict[str, str] = {}

    def get_file(fpath: str) -> str:
        if fpath not in _file_cache:
            resp = gh(f"/repos/{REPO}/contents/{fpath}?ref={branch}")
            if "_error" in resp:
                _file_cache[fpath] = ""
            else:
                import base64

                _file_cache[fpath] = base64.b64decode(resp["content"]).decode()
        return _file_cache[fpath]

    for c in gemini_comments:
        body = c.get("body", "")
        fpath = c.get("path", "")
        start_line = c.get("start_line") or c.get("original_line") or c.get("line") or 0
        end_line = c.get("line") or c.get("original_line") or start_line
        severity = "high" if "high" in body.lower()[:200] else "medium"

        suggestions = _extract_suggestions(body)
        current = get_file(fpath) if fpath else ""

        # Determine if already applied
        already_applied = any(_suggestion_already_applied(s, current) for s in suggestions) if suggestions else False

        if already_applied:
            kind = "FALSE_POS"
            msg_prefix = "[already applied] "
        else:
            # Classify by severity signal in body
            if severity == "high" or any(
                w in body.lower() for w in ("flaw", "bug", "incorrect", "broken", "fail", "error", "security")
            ):
                kind = "REAL_BUG"
            else:
                kind = "ADVISORY"
            msg_prefix = ""

        summary = _summarize_review_body(body)

        issues.append(
            Issue(
                source="gemini",
                kind=kind,
                file=fpath,
                line=start_line,
                message=f"{msg_prefix}{summary}",
                rule=f"gemini:{severity}",
                raw={
                    "comment_id": c.get("id"),
                    "suggestions": suggestions,
                    "start_line": start_line,
                    "end_line": end_line,
                    "file": fpath,
                },
            )
        )

    return issues


def apply_gemini_fixes(issues: list[Issue], branch: str) -> list[str]:
    """Apply REAL_BUG Gemini suggestions that have exactly one unambiguous fix."""
    applied: list[str] = []
    gemini_bugs = [i for i in issues if i.source == "gemini" and i.kind == "REAL_BUG"]
    if not gemini_bugs:
        return applied

    import base64

    _file_cache: dict[str, str] = {}
    _file_sha: dict[str, str] = {}

    def load_file(fpath: str) -> tuple[str, str]:
        if fpath not in _file_cache:
            resp = gh(f"/repos/{REPO}/contents/{fpath}?ref={branch}")
            if "_error" in resp:
                _file_cache[fpath] = ""
                _file_sha[fpath] = ""
            else:
                _file_cache[fpath] = base64.b64decode(resp["content"]).decode()
                _file_sha[fpath] = resp["sha"]
        return _file_cache[fpath], _file_sha[fpath]

    for issue in gemini_bugs:
        raw = issue.raw
        suggestions = raw.get("suggestions", [])
        fpath = raw.get("file", "")
        start_line = raw.get("start_line", 0)
        end_line = raw.get("end_line", 0)

        if not suggestions or not fpath or not start_line:
            print(f"  ⚠  Gemini fix skipped (no suggestion/file/line): {issue.message[:60]}")
            continue

        if len(suggestions) > 1:
            print(f"  ⚠  Gemini fix skipped (ambiguous — {len(suggestions)} suggestions): {fpath}:{start_line}")
            continue

        content, file_sha = load_file(fpath)
        if not content:
            print(f"  ⚠  Could not load {fpath}")
            continue

        suggestion = suggestions[0]

        # Final check: already applied?
        if _suggestion_already_applied(suggestion, content):
            print(f"  ✅ Already applied: {fpath}:{start_line}")
            continue

        new_content = _apply_suggestion(content, suggestion, start_line, end_line)
        if new_content is None:
            print(f"  ⚠  Could not apply suggestion at {fpath}:{start_line}-{end_line}")
            continue

        # Update cache
        _file_cache[fpath] = new_content
        print(f"  🔧 Applied Gemini fix: {fpath}:{start_line}-{end_line}")
        applied.append(f"Apply Gemini suggestion: {fpath}:{start_line} — {issue.message[:60]}")

    # Write changed files back locally so atomic_push can pick them up
    root = REPO_ROOT
    for fpath, new_content in _file_cache.items():
        local_path = root / fpath
        if local_path.exists() and local_path.read_text() != new_content:
            local_path.write_text(new_content)
            print(f"  📝 Written locally: {fpath}")

    return applied


# ── GitHub reviews ────────────────────────────────────────────────────────────


def _summarize_review_body(body: str, *, max_len: int = 220) -> str:
    """First substantive line from a bot/human review comment."""
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("!["):
            continue
        if line.startswith("(") and "http" in line:
            continue
        line = re.sub(r"!\[.*?\]\(.*?\)", "", line).strip()
        if line:
            return line[:max_len]
    return body[:max_len].replace("\n", " ")


def get_inline_bot_issues(
    pr_number: int | None,
    *,
    login_substrings: tuple[str, ...],
    source: str,
) -> list[Issue]:
    """Inline PR review comments from bots (Codex, etc.) — not CodeRabbit/Gemini paths."""
    if not pr_number:
        return []

    comments = gh(f"/repos/{REPO}/pulls/{pr_number}/comments?per_page=100")
    if not isinstance(comments, list):
        return []

    issues: list[Issue] = []
    matched = 0
    for c in comments:
        login = c.get("user", {}).get("login", "").lower()
        if not any(sub in login for sub in login_substrings):
            continue
        if "coderabbit" in login or "gemini" in login:
            continue
        matched += 1
        body = c.get("body", "")
        low = body.lower()
        if any(tok in low for tok in ("p1 badge", "p2 badge", "p0 badge", "must fix", "security")):
            kind = "REAL_BUG"
        elif any(tok in low for tok in ("bug", "incorrect", "broken", "wrong location", "flaw")):
            kind = "REAL_BUG"
        else:
            kind = "ADVISORY"
        issues.append(
            Issue(
                source=source,
                kind=kind,
                file=c.get("path", ""),
                line=c.get("line") or c.get("original_line") or 0,
                message=_summarize_review_body(body),
                rule=f"{source}:inline",
                raw=c,
            )
        )
    if matched:
        print(f"  → {source}: {matched} inline comment(s)")
    return issues


def get_codex_issues(pr_number: int | None) -> list[Issue]:
    return get_inline_bot_issues(
        pr_number,
        login_substrings=("codex", "chatgpt-codex"),
        source="codex",
    )


def get_review_issues(pr_number: int | None) -> list[Issue]:
    if not pr_number:
        return []

    reviews = gh(f"/repos/{REPO}/pulls/{pr_number}/reviews?per_page=50")
    if not isinstance(reviews, list):
        return []

    issues: list[Issue] = []
    for r in reviews:
        user = r.get("user", {}).get("login", "")
        if "coderabbit" in user.lower() or "bot" in user.lower():
            continue
        state = r.get("state", "")
        body = r.get("body", "")
        if body and state in ("CHANGES_REQUESTED", "COMMENTED"):
            issues.append(
                Issue(
                    source="github_review",
                    kind="REAL_BUG" if state == "CHANGES_REQUESTED" else "ADVISORY",
                    message=f"[{user}] {body[:300]}",
                    raw=r,
                )
            )

    return issues


# ── Auto-fix engine ───────────────────────────────────────────────────────────


def apply_all_auto_fixes(issues: list[Issue]) -> list[str]:
    """Apply ALL safe auto-fixes in one pass. Returns descriptions of what was done."""
    applied: list[str] = []
    auto = [i for i in issues if i.kind == "AUTO_FIX"]
    if not auto:
        return applied

    print("  → ruff check --fix (lint + import sort) ...")
    r = subprocess.run(["ruff", "check", "--fix", "."], capture_output=True, text=True, cwd=REPO_ROOT)
    applied.append(f"ruff check --fix: {(r.stdout + r.stderr).strip()[:120]}")

    print("  → ruff format ...")
    r = subprocess.run(["ruff", "format", "."], capture_output=True, text=True, cwd=REPO_ROOT)
    applied.append(f"ruff format: {(r.stdout + r.stderr).strip()[:120]}")

    # Flag manual-only items
    for i in auto:
        if "float" in i.message.lower() or "S1244" in i.rule:
            applied.append("MANUAL REQUIRED: Float equality — replace == with assertAlmostEqual(x, y, places=5)")
            break

    return applied


# ── Atomic multi-file GitHub commit ──────────────────────────────────────────


def atomic_push(branch: str, commit_msg: str) -> bool:
    """
    Commit ALL locally-changed files in one atomic push via GitHub git-tree API.
    This creates a single commit regardless of how many files changed.
    Returns True if something was pushed.
    """
    token = GH_TOKEN
    if not token:
        print("  ❌ No GitHub token — cannot push")
        return False

    # Find changed files vs git HEAD
    r = subprocess.run(["git", "diff", "--name-only"], capture_output=True, text=True, cwd=REPO_ROOT)
    changed = [f.strip() for f in r.stdout.splitlines() if f.strip()]
    if not changed:
        print("  No local changes to commit.")
        return False

    print(f"  → Files to commit ({len(changed)}): {', '.join(changed)}")

    ssl_ctx = _make_ssl()

    def api(method: str, path: str, data: dict | None = None) -> Any:
        # SSRF guard (SonarCloud S7044): only same-origin GitHub API paths are
        # allowed — reject anything that could redirect the request elsewhere.
        if not path.startswith("/repos/") or "://" in path or path.startswith("//"):
            raise ValueError(f"Refusing non-GitHub-API path: {path!r}")
        url = f"https://api.github.com{path}"
        req = urllib.request.Request(url, method=method)  # noqa: S310 — https scheme enforced above
        req.add_header("Authorization", f"token {token}")
        req.add_header("Content-Type", "application/json")
        if data:
            req.data = json.dumps(data).encode()
        with urllib.request.urlopen(req, context=ssl_ctx) as resp:  # noqa: S310
            return json.load(resp)

    # 1. Get current branch HEAD commit
    ref = api("GET", f"/repos/{REPO}/git/ref/heads/{_safe_ref(branch)}")
    head_sha = ref["object"]["sha"]

    # 2. Get the tree SHA of HEAD
    head_commit = api("GET", f"/repos/{REPO}/git/commits/{head_sha}")
    base_tree_sha = head_commit["tree"]["sha"]

    # 3. Create blobs for each changed file
    tree_items = []
    for fpath in changed:
        full = REPO_ROOT / fpath
        if not full.exists():
            print(f"    ⚠  {fpath} not found locally — skipping")
            continue
        content = full.read_bytes()
        blob = api(
            "POST",
            f"/repos/{REPO}/git/blobs",
            {"content": base64.b64encode(content).decode(), "encoding": "base64"},
        )
        tree_items.append({"path": fpath, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print(f"    blob {fpath}: {blob['sha'][:8]}")

    if not tree_items:
        print("  No blobs created.")
        return False

    # 4. Create new tree based on current HEAD tree
    new_tree = api(
        "POST",
        f"/repos/{REPO}/git/trees",
        {"base_tree": base_tree_sha, "tree": tree_items},
    )

    # 5. Create commit
    new_commit = api(
        "POST",
        f"/repos/{REPO}/git/commits",
        {
            "message": commit_msg,
            "tree": new_tree["sha"],
            "parents": [head_sha],
        },
    )

    # 6. Update branch reference
    api(
        "PATCH",
        f"/repos/{REPO}/git/refs/heads/{_safe_ref(branch)}",
        {"sha": new_commit["sha"], "force": False},
    )

    print(f"  ✅ Atomic commit: {new_commit['sha'][:8]} → {branch}")
    print("     CI re-triggered by single push")
    return True


# ── Signal gathering (shared by pr-check gate and pr-autopilot) ───────────────


def gather_all_signals(
    branch: str | None = None,
    *,
    pr_ref: str | int | None = None,
    verbose: bool = True,
) -> tuple[list[Issue], int | None, dict | None, str | None]:
    """Poll GitHub Actions logs, SonarCloud, CodeRabbit, Gemini, Codex, and human reviews.

    pr_ref: optional PR URL (https://github.com/org/repo/pull/N) or number — overrides branch lookup.

    Returns (issues, pr_number, pr_dict, ci_gate_conclusion).
    ci_gate_conclusion is None when no CI Gate run exists for the branch.
    """
    pr: dict | None = None
    pr_number: int | None = None

    if pr_ref is not None:
        pr, branch_from_pr, pr_number = resolve_pr_ref(pr_ref)
        branch = branch_from_pr or branch
        if verbose and pr_number:
            url = pr.get("html_url", f"https://github.com/{REPO}/pull/{pr_number}") if pr else ""
            print(f"\n📡 Remote PR signals — PR #{pr_number} {url}")
    else:
        branch = branch or current_branch()

    if not branch:
        return [], pr_number, pr, None

    if verbose and pr_ref is None:
        print(f"\n📡 Remote PR signals — branch: {branch}")

    if not pr:
        pr = find_pr(branch)
        pr_number = pr["number"] if pr else pr_number

    if verbose:
        if pr_number:
            title = (pr or {}).get("title", "")[:70]
            print(f"  → PR #{pr_number}: {title}")
        else:
            print("  → No open PR (CI + SonarCloud branch scope still polled)")

    ci_run = latest_ci_gate_run(branch)
    ci_conclusion = (ci_run.get("conclusion") or "in_progress") if ci_run else None

    if verbose:
        print("  [1/6] GitHub Actions — ALL failed-job logs ...")
    ci_issues = get_ci_issues(branch, verbose=verbose)

    if verbose:
        print("  [2/6] SonarCloud ...")
    sonar_issues = get_sonar_issues(pr_number)

    if verbose:
        print("  [3/6] CodeRabbit review comments ...")
    cr_issues = get_coderabbit_issues(pr_number)

    if verbose:
        print("  [4/6] Human PR reviews ...")
    review_issues = get_review_issues(pr_number)

    if verbose:
        print("  [5/6] Gemini Code Assist ...")
    gemini_issues = get_gemini_issues(pr_number, branch)

    if verbose:
        print("  [6/6] Codex (chatgpt-codex-connector) ...")
    codex_issues = get_codex_issues(pr_number)

    all_issues = ci_issues + sonar_issues + cr_issues + review_issues + gemini_issues + codex_issues
    return all_issues, pr_number, pr, ci_conclusion


# ── Report ────────────────────────────────────────────────────────────────────


def print_report(all_issues: list[Issue], pr_number: int | None, branch: str) -> None:
    sep = "=" * 72
    print(f"\n{sep}")
    print("PR AUTOPILOT — FULL REPORT")
    print(f"Branch: {branch}  |  PR: #{pr_number or 'none'}")
    print(sep)

    by_kind: dict[str, list[Issue]] = {
        "REAL_BUG": [],
        "AUTO_FIX": [],
        "ADVISORY": [],
        "FALSE_POS": [],
    }
    for issue in all_issues:
        by_kind.setdefault(issue.kind, []).append(issue)

    icons = {"AUTO_FIX": "🔧", "REAL_BUG": "🔴", "FALSE_POS": "⚪", "ADVISORY": "🔵"}
    for kind in ("REAL_BUG", "AUTO_FIX", "ADVISORY", "FALSE_POS"):
        bucket = by_kind.get(kind, [])
        if not bucket:
            continue
        print(f"\n{icons[kind]} {kind} ({len(bucket)})")
        print("-" * 52)
        for i in bucket:
            loc = f"{i.file}:{i.line}" if i.file else ""
            print(f"  [{i.source}] {loc}")
            for ln in i.message[:300].splitlines():
                print(f"    {ln}")

    print(f"\n{sep}")
    totals = {k: len(v) for k, v in by_kind.items()}
    print(
        f"TOTALS — 🔴 {totals['REAL_BUG']} real bugs  "
        f"🔧 {totals['AUTO_FIX']} auto-fixable  "
        f"🔵 {totals['ADVISORY']} advisory  "
        f"⚪ {totals['FALSE_POS']} false positives"
    )
    print(sep)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true", help="Apply all safe fixes and push as one commit")
    parser.add_argument("--branch", help="Branch to scan (default: current git branch)")
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Auto-approve any approval-required repair plans without interactive prompt",
    )
    args = parser.parse_args()

    branch = args.branch or current_branch()
    if not branch:
        print("❌ Cannot determine current branch")
        return 1

    print(f"\n🔍 PR Autopilot — scanning branch: {branch}")

    all_issues, pr_number, pr, _ci_conclusion = gather_all_signals(branch, verbose=True)

    print_report(all_issues, pr_number, branch)

    auto_fix_count = sum(1 for i in all_issues if i.kind == "AUTO_FIX")
    real_bug_count = sum(1 for i in all_issues if i.kind == "REAL_BUG")

    if not args.fix:
        if auto_fix_count:
            print(f"\n💡 Run with --fix to auto-apply {auto_fix_count} fixable issue(s) in one commit")
        if real_bug_count:
            print(f"⚠️  {real_bug_count} real bug(s) require manual review after auto-fixes")
        return 1 if real_bug_count or auto_fix_count else 0

    # ── FIX MODE — routed through pr_repair engine ────────────────────────────

    if _PR_REPAIR_WIRED:
        return _pr_repair_run(
            all_issues=all_issues,
            branch=branch,
            pr=pr,
            pr_number=pr_number,
            gh_token=GH_TOKEN,
            atomic_push_fn=atomic_push,
            force_approve=args.approve,
        )

    # Fallback: legacy single-pass fix (used when pr_repair is not installed)
    print("\n⚠️  pr_repair not installed — falling back to legacy fix mode")
    print("   Install: pip install git+https://github.com/cryptoxdog/PR_Repair.git")

    print("\n🔧 Applying ALL auto-fixes ...")
    fix_descriptions = apply_all_auto_fixes(all_issues)

    print("\n🤖 Applying Gemini Code Assist fixes ...")
    gemini_fixes = apply_gemini_fixes(all_issues, branch)
    fix_descriptions.extend(gemini_fixes)

    print("\n🔒 Running make pr-check (must pass before push) ...")
    check = subprocess.run(["make", "pr-check"], cwd=REPO_ROOT)
    if check.returncode != 0:
        print("❌ make pr-check FAILED — aborting push. Fix remaining issues above first.")
        return 1

    remaining_bugs = [i for i in all_issues if i.kind == "REAL_BUG"]
    bug_summary = "\n".join(f"- {i.message[:80]}" for i in remaining_bugs[:10])

    commit_msg = "fix(autopilot): apply all CI auto-fixes\n\n" + "\n".join(f"- {d}" for d in fix_descriptions if d)
    if remaining_bugs:
        commit_msg += f"\n\nRemaining manual fixes needed ({len(remaining_bugs)}):\n{bug_summary}"

    print(f"\n🚀 Atomic push → {branch} ...")
    pushed = atomic_push(branch, commit_msg)

    if pushed:
        print("\n✅ All fixes committed as ONE atomic commit — CI re-triggered once")
        if remaining_bugs:
            print(f"\n⚠️  {len(remaining_bugs)} REAL_BUG issue(s) still require manual fixes:")
            for i in remaining_bugs[:5]:
                print(f"   {i}")
        return 1 if remaining_bugs else 0

    print("\n⚠️  Nothing was pushed (no files changed after fixes)")
    return 1 if real_bug_count else 0


if __name__ == "__main__":
    sys.exit(main())
