#!/usr/bin/env bash
# GitHub Actions Kernel gate (github_actions_kernel.v1)
# DORA R5 | developer_support
# Checks: triggers, permissions, secrets_handling, job_dependencies (YAML parse),
#         third-party action SHA pins, hard_bans (no secrets, no wildcard permissions)
#
# Usage:
#   ci/check_github_actions_kernel.sh              # all workflow files
#   ci/check_github_actions_kernel.sh --staged     # git-index paths only (make commit)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAGED_ONLY=0
if [[ "${1:-}" == "--staged" ]]; then
    STAGED_ONLY=1
fi

collect_files() {
    if [[ "$STAGED_ONLY" -eq 1 ]]; then
        git diff --cached --name-only --diff-filter=ACMR -- '.github/workflows/*.yml' '.github/workflows/*.yaml' 2>/dev/null || true
    else
        find .github/workflows -maxdepth 1 \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null | sort || true
    fi
}

FILES=()
while IFS= read -r line; do
    [[ -n "$line" ]] && FILES+=("$line")
done < <(collect_files)

if [[ ${#FILES[@]} -eq 0 ]]; then
    exit 0
fi

echo "→ GitHub Actions kernel check (github_actions_kernel.v1)..."
FAIL=0
RESULTS=()

fail() {
    RESULTS+=("❌ $1")
    FAIL=1
}

pass() {
    RESULTS+=("✅ $1")
}

for f in "${FILES[@]}"; do
    [[ -f "$f" ]] || continue
    base="$(basename "$f")"

    # triggers — each workflow must declare on:
    if grep -qE '^[[:space:]]*on:' "$f"; then
        pass "$base: triggers (on: present)"
    else
        fail "$base: missing workflow triggers (on:)"
    fi

    # hard_ban — wildcard permissions
    if grep -qE 'write-all|read-all|permissions:[[:space:]]*\*' "$f"; then
        fail "$base: wildcard permissions forbidden (write-all/read-all/*)"
    else
        pass "$base: permissions (no wildcards)"
    fi

    # secrets_handling — hardcoded secret patterns
    if grep -qE 'ghp_[A-Za-z0-9]+|gho_[A-Za-z0-9]+|github_pat_[A-Za-z0-9]+|sk-[A-Za-z0-9]{20,}' "$f"; then
        fail "$base: possible hardcoded secret/token in workflow"
    else
        pass "$base: secrets_handling (no inline tokens)"
    fi

    # caching / job graph / merge gates — YAML must parse (structural sanity)
    if python3 -c "
import sys, yaml
from pathlib import Path
p = Path('$f')
try:
    data = yaml.safe_load(p.read_text())
except Exception as e:
    print(f'YAML parse error: {e}', file=sys.stderr)
    sys.exit(1)
if not isinstance(data, dict):
    print('Workflow root must be a mapping', file=sys.stderr)
    sys.exit(1)
jobs = data.get('jobs') or {}
if jobs and not isinstance(jobs, dict):
    print('jobs: must be a mapping', file=sys.stderr)
    sys.exit(1)
for job_id, job in (jobs or {}).items():
    needs = job.get('needs')
    if needs is None:
        continue
    need_list = [needs] if isinstance(needs, str) else list(needs)
    for dep in need_list:
        if dep not in jobs:
            print(f'job {job_id} needs unknown job {dep}', file=sys.stderr)
            sys.exit(1)
sys.exit(0)
"; then
        pass "$base: job_dependencies + YAML valid"
    else
        fail "$base: YAML/job_dependencies invalid"
    fi

    # Third-party actions — mutable tags forbidden (actions/* exempt per 86-ci-github-actions)
    if grep -E '^[[:space:]]*- uses:' "$f" | grep -vE 'uses:[[:space:]]+actions/' | grep -qE '@(v[0-9]+[^[:space:]]*|main|master|latest)[[:space:]]*(#|$)'; then
        fail "$base: third-party action uses mutable tag (@vN/@main) — pin SHA"
    else
        pass "$base: third-party actions SHA-pinned or actions/* only"
    fi

    # merge_gate_logic — ci.yml tier ordering when present
    if [[ "$base" == "ci.yml" ]]; then
        if grep -q 'needs: lint' "$f" && grep -q 'needs: static-checks' "$f"; then
            pass "$base: merge_gate_logic (tier needs: present)"
        else
            fail "$base: ci.yml missing expected tier needs: (lint → static-checks → tests)"
        fi
    fi
done

echo ""
for r in "${RESULTS[@]}"; do
    echo "  $r"
done
echo ""

if [[ $FAIL -ne 0 ]]; then
    echo "❌ GitHub Actions kernel check FAILED"
    echo "   Kernel: github_actions_kernel.v1 | hard_bans: no secrets, no wildcard permissions"
    exit 1
fi

echo "✅ GitHub Actions kernel check passed (${#FILES[@]} workflow file(s))"
exit 0
