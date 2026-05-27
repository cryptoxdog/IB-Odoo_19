#!/usr/bin/env python3
"""
PlasticOS PR Repair Adapter — bridges pr_autopilot signal sources to the
pr_repair engine (cryptoxdog/PR_Repair).

Signal flow:
  pr_autopilot  (CI logs, SonarCloud, Gemini, CodeRabbit) → Issue objects
      → issue_to_finding()          → Finding objects with PlasticOS taxonomy
      → PRLoopOrchestrator          → state-machine-governed repair loop
      → plasticos_repair_executor   → ruff --fix + Gemini patches + atomic_push
      → PRStateStore                → persisted state across CI re-runs

Usage (called by pr_autopilot.py in --fix mode):
    from pr_repair_adapter import run_repair_loop
    return run_repair_loop(all_issues=issues, branch=branch, pr=pr, pr_number=pr_number)

State persistence:
    .pr-repair-state/<repo>__pr_<number>.json — attempt count, failure fingerprint
    Mounted as Actions cache in pr-repair-loop.yml so state survives across CI runs.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

# ── Path setup — allow sibling imports when run as script ────────────────────

_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# ── pr_repair imports (installed via requirements.txt git dep) ────────────────

try:
    from pr_repair.config import AppConfig
    from pr_repair.orchestration.pr_loop import (
        PRLoopConfig,
        PRLoopOrchestrator,
        PRLoopState,
    )
    from pr_repair.runtime.pr_state_store import PRStateStore
    from pr_repair.types import (
        ExecutionMode,
        Finding,
        PRRef,
        RepairExecution,
        RepairPlan,
        Severity,
        SourceName,
        TierLevel,
    )
    from pr_repair.verification.native_runner import run_verification

    PR_REPAIR_AVAILABLE = True
except ImportError as _err:
    PR_REPAIR_AVAILABLE = False
    _PR_REPAIR_IMPORT_ERROR = str(_err)

if TYPE_CHECKING:
    from pr_autopilot import Issue

# ── Constants ─────────────────────────────────────────────────────────────────

REPO = "cryptoxdog/IB-Odoo_19"
REPO_ROOT = Path(__file__).parent.parent
STATE_DIR = REPO_ROOT / ".pr-repair-state"

# Verification command for PlasticOS — runs audit-quick + semgrep + pipeline-guard
VERIFY_COMMAND = ["make", "pr-check"]

# Write ceiling: T1 = only low-tier safe files (scripts, tests, modules).
# T2+ (migrations, security/, workflow files) require human approval.
WRITE_CEILING = "T1"

# Maximum repair attempts per PR head SHA before the loop terminates
MAX_REPAIR_ATTEMPTS = 3

# ── PlasticOS protected paths ─────────────────────────────────────────────────
# Auto-repair is NEVER applied to these — changes here require human review.
# Intentionally narrow: ruff/format fixes are safe everywhere.
# Only block paths where a wrong auto-change causes irreversible security or
# architectural damage (auth, migrations, workflow files, the repair scripts themselves).

PLASTICOS_PROTECTED_PATHS = [
    ".github/workflows/",
    "plasticos_security_base/",
    "security/ir.model.access.csv",
    "**/migrations/",
    ".pre-commit-config.yaml",
    ".env",
    ".env.local",
    "scripts/pr_autopilot.py",
    "scripts/pr_repair_adapter.py",
]

# ── Rule → pr_repair category mapping ────────────────────────────────────────
# Maps autopilot Issue.rule prefixes to pr_repair taxonomy categories.
# "lint_failure" and "typing_failure" are AUTO_REPAIRABLE in pr_repair.
# Everything else is APPROVAL_REQUIRED or NEVER_AUTO_REPAIR.

_RULE_TO_CATEGORY: list[tuple[str, str]] = [
    # Ruff lint/format — auto-repairable (ruff --fix handles these)
    ("ruff:I", "lint_failure"),
    ("ruff:E", "lint_failure"),
    ("ruff:F", "lint_failure"),
    ("ruff:W", "lint_failure"),
    ("ruff:UP", "lint_failure"),
    ("ruff:B", "lint_failure"),
    ("ruff:C9", "lint_failure"),
    ("ruff-format", "lint_failure"),
    # Gemini code-assist suggestions (explicit suggested_fix) — treated as lint
    # because the fix is deterministic (reviewer-provided code block).
    ("gemini:", "lint_failure"),
    # SonarCloud — map to lint_failure only for safe auto-fixes
    ("sonar:python:S1244", "lint_failure"),  # float equality → assertAlmostEqual
    ("sonar:python:S5527", "coderabbit_security_issue"),  # SSL hostname check
    ("sonar:python:S4423", "coderabbit_security_issue"),  # weak SSL
    ("sonar:python:S4830", "coderabbit_security_issue"),  # cert validation
    # Module wiring / CI failures
    ("module-wiring", "github_required_check_failure"),
    ("cron-invariant", "compliance_failure"),
    ("pytest", "github_required_check_failure"),
    # Secret scanning — NEVER auto-repair
    ("gitleaks:", "coderabbit_security_issue"),
    # CodeRabbit — advisory by default
    ("coderabbit", "coderabbit_style_violation"),
    # GitHub human reviews
    ("github_review", "ambiguous_comment"),
]

_KIND_TO_SEVERITY: dict[str, str] = {
    "REAL_BUG": "high",
    "AUTO_FIX": "low",
    "ADVISORY": "low",
    "FALSE_POS": "low",
}


# ── Issue → Finding conversion ────────────────────────────────────────────────


def issue_to_finding(issue: Issue, pr_number: int) -> Finding:
    """Convert an autopilot Issue into a pr_repair Finding.

    Key decisions:
    - Ruff AUTO_FIX issues: lint_failure + repairable=True (ruff --fix handles them)
    - Gemini REAL_BUG with suggestions: lint_failure + repairable=True + suggested_fix
    - Security findings: coderabbit_security_issue + repairable=False (NEVER_AUTO_REPAIR)
    - Everything else: mapped category + repairable=False
    """
    category = _infer_category(issue)
    suggested_fix = _extract_suggested_fix(issue)
    repairable = _is_repairable(issue, category, suggested_fix)
    severity_str = _KIND_TO_SEVERITY.get(issue.kind, "low")
    severity = Severity(severity_str)
    source_name = _infer_source_name(issue)
    protected = _is_protected_path(issue.file)

    if protected:
        repairable = False
        category = "protected_file_violation"

    fingerprint = f"{issue.rule}|{issue.file}|{issue.line}|{issue.message[:60]}"

    return Finding(
        finding_id=f"{issue.rule}:{issue.file or 'repo'}:{issue.line}:{uuid.uuid4().hex[:6]}",
        pr_number=pr_number,
        source_name=source_name,
        source_priority=_source_priority(issue.source),
        severity=severity,
        category=category,
        message=issue.message[:500],
        file_path=issue.file if issue.file else None,
        line_start=issue.line if issue.line else None,
        suggested_fix=suggested_fix,
        repairable=repairable,
        confidence=0.95 if suggested_fix else (0.85 if issue.kind == "AUTO_FIX" else 0.50),
        fingerprint=fingerprint,
        tier_impact=TierLevel.t1,
        protected_path=protected,
    )


def issues_to_findings(issues: list[Issue], pr_number: int) -> list[Finding]:
    """Convert all autopilot issues to pr_repair findings."""
    return [issue_to_finding(i, pr_number) for i in issues]


def _infer_category(issue: Issue) -> str:
    for prefix, category in _RULE_TO_CATEGORY:
        if issue.rule.startswith(prefix) or issue.source.startswith(prefix.rstrip(":")):
            return category
    # Fallback by kind
    if issue.kind == "AUTO_FIX":
        return "lint_failure"
    if issue.kind == "FALSE_POS":
        return "ambiguous_comment"
    return "ambiguous_comment"


def _extract_suggested_fix(issue: Issue) -> str | None:
    """Pull the first unambiguous code suggestion from a Gemini/review issue."""
    if issue.source != "gemini":
        return None
    suggestions = issue.raw.get("suggestions", [])
    if len(suggestions) == 1:
        return suggestions[0].strip()
    return None


def _is_repairable(issue: Issue, category: str, suggested_fix: str | None) -> bool:
    """Determine if this finding can be auto-repaired without human approval."""
    # Explicit never-repair signals
    if issue.kind == "FALSE_POS":
        return False
    if category in {"coderabbit_security_issue", "protected_file_violation", "architecture_boundary_violation"}:
        return False
    # Auto-fix lint issues: ruff --fix handles them, no suggested_fix needed
    if issue.kind == "AUTO_FIX" and category == "lint_failure":
        return True
    # Gemini suggestion with an explicit code fix: safe to apply deterministically
    if issue.source == "gemini" and suggested_fix is not None and category == "lint_failure":
        return True
    return False


def _is_protected_path(file_path: str) -> bool:
    if not file_path:
        return False
    for pattern in PLASTICOS_PROTECTED_PATHS:
        if pattern.endswith("/"):
            if file_path.startswith(pattern) or f"/{pattern}" in file_path:
                return True
        elif pattern.startswith("**/"):
            segment = pattern[3:]
            if segment in file_path:
                return True
        elif file_path == pattern or file_path.endswith(f"/{pattern}"):
            return True
    return False


def _infer_source_name(issue: Issue) -> SourceName:
    mapping = {
        "ci": SourceName.github_checks,
        "sonar": SourceName.github_checks,
        "coderabbit": SourceName.github_review_comments,
        "gemini": SourceName.github_review_comments,
        "github_review": SourceName.github_review_comments,
    }
    return mapping.get(issue.source, SourceName.github_checks)


def _source_priority(source: str) -> int:
    priorities = {"ci": 1, "sonar": 2, "gemini": 3, "coderabbit": 4, "github_review": 5}
    return priorities.get(source, 9)


# ── PlasticOS AppConfig ───────────────────────────────────────────────────────


def build_plasticos_config(gh_token: str) -> AppConfig:
    """Build pr_repair AppConfig configured for PlasticOS/IB-Odoo_19."""
    return AppConfig(
        github_token=gh_token,
        github_repository=REPO,
        mode=ExecutionMode.repair_verify_and_push,
        allow_push=True,
        write_ceiling=TierLevel(WRITE_CEILING),
        verify_command=VERIFY_COMMAND,
        output_dir=REPO_ROOT / "runtime" / "pr_repair",
    )


# ── PRRef builder ─────────────────────────────────────────────────────────────


def build_pr_ref(branch: str, pr: dict | None, pr_number: int | None) -> PRRef:
    """Construct a pr_repair PRRef from autopilot PR data."""
    actual_pr_number = pr_number or 0
    if pr:
        return PRRef(
            repo_owner="cryptoxdog",
            repo_name="IB-Odoo_19",
            pr_number=actual_pr_number,
            title=pr.get("title", ""),
            head_branch=branch,
            base_branch=pr.get("base", {}).get("ref", "Staging"),
            head_sha=pr.get("head", {}).get("sha", _git_head_sha()),
            is_draft=pr.get("draft", False),
            author=pr.get("user", {}).get("login", ""),
            labels=[label["name"] for label in pr.get("labels", [])],
        )
    return PRRef(
        repo_owner="cryptoxdog",
        repo_name="IB-Odoo_19",
        pr_number=actual_pr_number,
        title=f"branch:{branch}",
        head_branch=branch,
        base_branch="Staging",
        head_sha=_git_head_sha(),
        is_draft=False,
        author="",
    )


def _git_head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return result.stdout.strip()


# ── PlasticOS repair executor ─────────────────────────────────────────────────


def plasticos_repair_executor(
    plan: RepairPlan,
    config: AppConfig,
    repo_root: Path | None,
    all_issues: list[Issue],
    branch: str,
    atomic_push_fn,
) -> RepairExecution:
    """Custom repair executor for PlasticOS.

    Execution order:
    1. Apply Gemini suggestions via autopilot's apply_gemini_fixes()
       (context-aware multi-line handler — NOT pr_repair's patch_applier which
       does raw single-line replacement and breaks multi-line suggestion blocks)
    2. Run ruff check --fix + ruff format for lint_failure findings
    3. Run make pr-check verification
    4. If passes: atomic_push via GitHub git-tree API
    5. Return RepairExecution with full status

    Rollback strategy: git restore . if verification fails.
    """
    # Lazy import to avoid circular import — autopilot imports this module at top
    import importlib

    autopilot = importlib.import_module("pr_autopilot")

    root = repo_root or REPO_ROOT
    execution_id = str(uuid.uuid4())
    modified_files: list[str] = []

    # Step 1: Apply Gemini suggestions via autopilot's context-aware fixer.
    # autopilot.apply_gemini_fixes() uses start_line/end_line from the GitHub
    # comment metadata to replace the exact diff hunk — handles multi-line
    # suggestion blocks correctly. pr_repair's patch_applier only does single-
    # line replacements and would corrupt multi-line blocks.
    gemini_issues = [i for i in all_issues if i.source == "gemini" and i.kind == "REAL_BUG"]
    if gemini_issues:
        print(f"  → pr_repair: applying {len(gemini_issues)} Gemini suggestion(s) via context-aware patcher ...")
        applied = autopilot.apply_gemini_fixes(all_issues, branch)
        if applied:
            for iss in gemini_issues:
                if iss.raw.get("file"):
                    modified_files.append(iss.raw["file"])
            print(f"    ✅ Applied {len(applied)} suggestion(s)")
        else:
            print("    ℹ  No Gemini suggestions applied (already applied or no code blocks)")

    # Step 2: Run ruff for lint_failure findings (format + auto-fix)
    lint_findings = [f for f in plan.targeted_findings if f.category == "lint_failure"]
    if lint_findings:
        print("  → pr_repair: ruff check --fix + ruff format ...")
        subprocess.run(["ruff", "check", "--fix", "."], capture_output=True, cwd=root)
        subprocess.run(["ruff", "format", "."], capture_output=True, cwd=root)

    # Step 3: Verify
    print(f"  → pr_repair: verifying with {' '.join(VERIFY_COMMAND)} ...")
    verification_result = run_verification(VERIFY_COMMAND, root)

    if not verification_result.success:
        print("  ❌ pr_repair: verification failed — rolling back local changes")
        subprocess.run(["git", "restore", "."], capture_output=True, cwd=root)
        return RepairExecution(
            execution_id=execution_id,
            pr_ref=plan.pr_ref,
            plan_id=plan.plan_id,
            mode=plan.execution_mode,
            modified_files=[],
            verification_result=verification_result,
            status="rolled_back_verification_failed",
        )

    # Step 4: Collect changed files and push
    changed_result = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    changed = [f.strip() for f in changed_result.stdout.splitlines() if f.strip()]

    if not changed:
        print("  ℹ  pr_repair: no file changes after repairs")
        return RepairExecution(
            execution_id=execution_id,
            pr_ref=plan.pr_ref,
            plan_id=plan.plan_id,
            mode=plan.execution_mode,
            modified_files=[],
            verification_result=verification_result,
            status="no_applicable_instructions",
        )

    commit_msg = (
        f"fix(pr-{plan.pr_ref.pr_number}): apply PlasticOS CI auto-repairs\n\n"
        f"Repair attempt #{plan.pr_ref.pr_number} via pr_repair engine.\n"
        f"Changed: {', '.join(changed[:10])}"
    )
    pushed = atomic_push_fn(branch, commit_msg)

    return RepairExecution(
        execution_id=execution_id,
        pr_ref=plan.pr_ref,
        plan_id=plan.plan_id,
        mode=plan.execution_mode,
        modified_files=changed,
        verification_result=verification_result,
        push_result=f"atomic_push:{branch}" if pushed else None,
        status="completed" if pushed else "no_changes",
    )


# ── Main entry point: run_repair_loop ────────────────────────────────────────


def run_repair_loop(
    *,
    all_issues: list[Issue],
    branch: str,
    pr: dict | None,
    pr_number: int | None,
    gh_token: str,
    atomic_push_fn,
    force_approve: bool = False,
) -> int:
    """Run the pr_repair state-machine-governed repair loop.

    Called by pr_autopilot.py in --fix mode instead of the manual fix block.

    When the plan requires human approval, presents a summary of what will be
    changed and prompts for y/n confirmation (or auto-approves with force_approve=True
    or when running non-interactively in CI via PR_REPAIR_FORCE_APPROVE=1).

    Returns:
        0 — all issues resolved
        1 — issues remain or repair blocked
    """
    if not PR_REPAIR_AVAILABLE:
        print(f"⚠  pr_repair not installed: {_PR_REPAIR_IMPORT_ERROR}")
        print("   Install with: pip install git+https://github.com/cryptoxdog/PR_Repair.git")
        return 1

    print("\n🔁 PR Repair Engine — initialising ...")

    config = build_plasticos_config(gh_token)
    pr_ref = build_pr_ref(branch, pr, pr_number)
    findings = issues_to_findings(all_issues, pr_number or 0)

    repairable_count = sum(1 for f in findings if f.repairable)
    print(f"  → {len(findings)} finding(s) converted  ({repairable_count} repairable)")

    if not findings:
        print("  ✅ No findings — nothing to repair")
        return 0

    # State store: persisted at .pr-repair-state/ (mounted as Actions cache in CI)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_store = PRStateStore(STATE_DIR)

    def _make_executor(approved: bool):
        """Return a repair executor, with optional approval bypass."""

        def _executor(plan: RepairPlan, _config: AppConfig, _repo_root: Path | None) -> RepairExecution:
            return plasticos_repair_executor(
                plan=plan,
                config=_config,
                repo_root=_repo_root,
                all_issues=all_issues,
                branch=branch,
                atomic_push_fn=atomic_push_fn,
            )

        return _executor

    def _finding_provider(_pr_ref: PRRef) -> list[Finding]:
        return findings

    ci_status = "failure"
    review_status = "unknown"
    orchestrator = PRLoopOrchestrator(
        app_config=config,
        state_store=state_store,
        finding_provider=_finding_provider,
        repair_executor=_make_executor(False),
        loop_config=PRLoopConfig(max_repair_attempts=MAX_REPAIR_ATTEMPTS),
        repo_root=REPO_ROOT,
    )
    orchestrator.signal_provider = lambda _pr_ref: (ci_status, review_status)

    print("  → Running PRLoopOrchestrator.on_pr_event() ...")
    result = orchestrator.on_pr_event(pr_ref)

    # ── Interactive approval ───────────────────────────────────────────────────
    if result.state == PRLoopState.approval_required and result.plan:
        approved = _interactive_approval(
            plan=result.plan,
            findings=findings,
            force_approve=force_approve,
        )
        if not approved:
            print("\n⛔  Repair declined — no changes made.")
            return 1

        # User approved — execute the repair plan directly, bypassing the
        # orchestrator's approval gate (which would loop back to approval_required).
        print("\n  → Executing approved repair plan ...")
        execution = plasticos_repair_executor(
            plan=result.plan,
            config=config,
            repo_root=REPO_ROOT,
            all_issues=all_issues,
            branch=branch,
            atomic_push_fn=atomic_push_fn,
        )
        if execution.status == "completed":
            remaining = [f for f in findings if not f.repairable]
            print("\n🔄 PR Repair Loop result: waiting_for_ci_rerun")
            print(f"   Fixes committed and pushed → {branch}")
            print("   CI will re-run. Next failure will trigger another repair attempt.")
            if remaining:
                print(f"\n⚠   {len(remaining)} finding(s) still require manual fix:")
                for f in remaining[:5]:
                    print(f"    {f.file_path or '(repo)'}:{f.line_start or '?'} — {f.message[:80]}")
            return 0
        if execution.status in ("rolled_back_verification_failed", "no_applicable_instructions", "no_changes"):
            print(f"\n🚫 Repair result: {execution.status}")
            if execution.verification_result and not execution.verification_result.success:
                print("   make pr-check failed. Output:")
                print(execution.verification_result.stderr[-500:] or execution.verification_result.stdout[-500:])
            return 1
        print(f"\n🚫 Repair result: {execution.status}")
        return 1

    _print_loop_result(result, branch)

    terminal_states_ok = {PRLoopState.clean, PRLoopState.waiting_for_ci_rerun}
    return 0 if result.state in terminal_states_ok else 1


def _interactive_approval(
    *,
    plan: RepairPlan,
    findings: list[Finding],
    force_approve: bool,
) -> bool:
    """Present what needs approval and ask the user to confirm.

    In CI (non-interactive) mode or when force_approve=True, auto-approves.
    """
    sep = "─" * 60
    print(f"\n{sep}")
    print("🔐  APPROVAL REQUIRED — Review before auto-repair proceeds")
    print(sep)

    # Show what's protected / why approval is needed
    protected = [f for f in findings if f.protected_path]
    approval_needed = [f for f in findings if f.repairable and not f.protected_path]
    non_repairable = [f for f in findings if not f.repairable and not f.protected_path]

    if protected:
        print(f"\n🔒  Protected-path findings ({len(protected)}) — NOT auto-repaired:")
        for f in protected:
            print(f"    {f.file_path}:{f.line_start or '?'}  [{f.category}]")
            print(f"    {f.message[:100]}")

    if approval_needed:
        print(f"\n🔧  Will be auto-repaired if approved ({len(approval_needed)}):")
        for f in approval_needed:
            fix_note = f"→ apply: {f.suggested_fix[:60]!r}" if f.suggested_fix else "→ ruff --fix / ruff format"
            print(f"    {f.file_path or '(repo)'}:{f.line_start or '?'}  [{f.category}]")
            print(f"    {f.message[:100]}")
            print(f"    {fix_note}")

    if non_repairable:
        print(f"\n⚠   Cannot auto-repair ({len(non_repairable)}) — will be left for manual fix:")
        for f in non_repairable:
            print(f"    {f.file_path or '(repo)'}:{f.line_start or '?'} — {f.message[:80]}")

    print(f"\n  Risk level : {plan.risk_level}")
    print(f"  Files      : {', '.join(plan.target_files) or '(format-only)'}")
    print(f"  Verify cmd : {' '.join(plan.verification_command)}")
    print(sep)

    # Auto-approve in CI or when forced
    ci_env = bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS") or os.environ.get("PR_REPAIR_FORCE_APPROVE"))
    if force_approve or ci_env:
        print("  ✅ Auto-approved (CI/force mode)")
        return True

    if not approval_needed:
        print("  ℹ  Nothing repairable in this plan — skipping.")
        return False

    try:
        answer = input("\n  Approve and apply repairs? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  (non-interactive — treating as decline)")
        return False

    return answer in ("y", "yes")


def _print_loop_result(result, branch: str) -> None:
    state_icons = {
        PRLoopState.clean: "✅",
        PRLoopState.waiting_for_ci_rerun: "🔄",
        PRLoopState.approval_required: "🔐",
        PRLoopState.blocked: "🚫",
        PRLoopState.max_attempts_reached: "🛑",
    }
    icon = state_icons.get(result.state, "ℹ")
    print(f"\n{icon} PR Repair Loop result: {result.state.value}")

    if result.reason:
        print(f"   Reason: {result.reason}")

    if result.state == PRLoopState.waiting_for_ci_rerun:
        print(f"   Fixes committed and pushed → {branch}")
        print("   CI will re-run. Next failure will trigger another repair attempt.")

    if result.state == PRLoopState.approval_required and result.plan:
        guarded = [f.file_path or "(repo)" for f in result.plan.targeted_findings if f.protected_path]
        print(f"   Protected paths require human review: {guarded or '(risk level)'}")

    if result.state == PRLoopState.max_attempts_reached:
        print(f"   Reached {MAX_REPAIR_ATTEMPTS} repair attempts. Manual intervention required.")

    if result.state == PRLoopState.blocked and result.persisted_state.last_failure_fingerprint:
        if result.reason == "repeated_same_failure":
            print("   Same failures appeared on consecutive attempts — auto-repair cannot fix these.")
            print("   Manual fix required.")

    if result.execution and result.execution.verification_result:
        vr = result.execution.verification_result
        status = "passed" if vr.success else "FAILED"
        print(f"   Verification ({' '.join(vr.command)}): {status}")
