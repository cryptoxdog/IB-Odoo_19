#!/usr/bin/env bash
# Publication kernel behind `make pr`: preflight → pr-check → L4 → push → PR.
# Usage: make_push_pipeline.sh [message] [target] [base] [open_pr] [do_commit]
# `make pr` publishes one committed feature branch into Staging, or onto an open parent PR's branch with `base=`.
set -euo pipefail

refuse() {
  echo "refusing to publish: $*" >&2
  exit 1
}

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${ROOT}" ]]; then
  refuse "not inside a git repository"
fi
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"

MSG="${1:-}"
CURRENT="$(git branch --show-current)"
TARGET="${2:-${CURRENT}}"
BASE="${3:-Staging}"
OPEN_PR="${4:-1}"
DO_COMMIT="${5:-0}"

if [[ -n "${MSG}" ]]; then
  refuse "make pr does not take a commit message and does not commit"
fi
if [[ "${DO_COMMIT}" != "0" ]]; then
  refuse "make pr does not commit; publish an already committed HEAD"
fi
if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  refuse "HEAD does not exist"
fi
if [[ -z "${CURRENT}" ]]; then
  refuse "detached HEAD; publication requires an attached feature branch"
fi
if [[ -z "${TARGET}" ]]; then
  refuse "publication target branch is empty"
fi
if [[ "${CURRENT}" != "${TARGET}" ]]; then
  refuse "current branch ${CURRENT} is not the publication target ${TARGET}"
fi
bash scripts/pr_stack_parent.sh name "${BASE}"

current_lc="$(printf '%s' "${CURRENT}" | tr '[:upper:]' '[:lower:]')"
case "${current_lc}" in
  staging|production)
    refuse "${CURRENT} is a protected source branch"
    ;;
esac
if [[ "${CURRENT}" == "${BASE}" ]]; then
  refuse "${CURRENT} → ${BASE} is a self-PR; source and base must differ"
fi

status="$(git status --porcelain)"
if [[ -n "${status}" ]]; then
  echo "refusing to publish: working tree, index, or untracked files are not clean" >&2
  printf '%s\n' "${status}" >&2
  exit 1
fi

# Publication repository: the one authorized origin push URL (same allowlist
# as git_push_with_pr.sh). git_push_with_pr.sh runs as a child, so its export
# never reaches this process; bind GH_REPO here, before the first API call, so
# git_open_pr.sh and apply_pr_kernel_metadata.sh inherit it. An inherited
# GH_REPO naming another repository is refused, never used.
push_urls="$(git remote get-url --push --all origin 2>/dev/null || true)"
if [[ -z "${push_urls}" || "${push_urls}" == *$'\n'* ]]; then
  refuse "origin must have exactly one push URL"
fi
case "${push_urls%.git}" in
  https://github.com/cryptoxdog/IB-Odoo_19 | git://github.com/cryptoxdog/IB-Odoo_19 | \
    git@github.com:cryptoxdog/IB-Odoo_19 | ssh://git@github.com/cryptoxdog/IB-Odoo_19) ;;
  *) refuse "origin push URL is not cryptoxdog/IB-Odoo_19 (${push_urls})" ;;
esac
if [[ -n "${GH_REPO:-}" && "${GH_REPO}" != "cryptoxdog/IB-Odoo_19" ]]; then
  refuse "GH_REPO=${GH_REPO} is not the origin repository cryptoxdog/IB-Odoo_19"
fi
# `gh api repos/...` takes its host from GH_HOST, not from origin; pin it too.
if [[ -n "${GH_HOST:-}" && "${GH_HOST}" != "github.com" ]]; then
  refuse "GH_HOST=${GH_HOST} is not the origin host github.com"
fi
export GH_REPO="cryptoxdog/IB-Odoo_19" GH_HOST="github.com"

# REST only. `gh auth status` reports a false negative and `gh pr`/`gh label`
# are GraphQL-backed (HTTP 403) on a surface whose egress proxy injects the
# credential; probe the capability actually used.
if ! command -v gh >/dev/null 2>&1; then
  refuse "gh CLI is not available; publication cannot create or verify the pull request"
fi
if ! gh api user >/dev/null 2>&1; then
  refuse "gh is not authenticated (gh api user failed)"
fi
if [[ "${BASE}" != "Staging" ]]; then
  bash scripts/pr_stack_parent.sh prove "${BASE}"
fi
# Open PR(s) for TARGET → BASE; prints the first PR number, or nothing.
open_pr_number() {
  local raw
  raw="$(gh api --method GET "repos/${GH_REPO}/pulls" -f state=open -f base="${BASE}" -f head="${GH_REPO%%/*}:${TARGET}")" \
    || return 1
  python3 - "${raw}" "${GH_REPO}" <<'PY'
import json
import sys

raw, repo = sys.argv[1:]
try:
    items = json.loads(raw)
except ValueError:
    sys.exit("pull request lookup returned malformed JSON")
if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
    sys.exit("pull request lookup did not return a list of pull requests")
for item in items:
    if ((item.get("base") or {}).get("repo") or {}).get("full_name") != repo:
        sys.exit(f"pull request lookup returned a pull request outside {repo}")
if items:
    print(items[0].get("number") or "")
PY
}
if ! open_pr_number >/dev/null; then
  refuse "cannot look up pull requests for ${TARGET} → ${BASE} (gh api repos/${GH_REPO}/pulls)"
fi

echo "══════════════════════════════════════════════════════"
echo "  make pr — pr-check → L4 → push → PR"
echo "  ${CURRENT} → ${BASE}"
echo "══════════════════════════════════════════════════════"
echo ""

# L4 runs twice: here, before any local work, and again inside
# git_push_with_pr.sh at the push boundary, after its validation gate.
# git_push_with_pr.sh owns that gate on every attempt (pre-push hooks may not
# run at all on a retry); the pre-push stage is bound to it so the candidate is
# validated once (scripts/pre_push_validate.sh).
echo "→ L4 release check (before local gate and before any remote mutation)..."
bash scripts/git_push_with_pr.sh --check-l4
echo ""

# Makefile COMMIT_EXCLUDE (.cursor-commands). The published commit range must
# not contain that governance path.
range_base="$(git merge-base HEAD "origin/${BASE}" 2>/dev/null || true)"
if [[ -z "${range_base}" ]]; then
  range_base="$(git rev-list --max-parents=0 HEAD | tail -1)"
fi
if git diff --name-only "${range_base}..HEAD" | grep -q '^\.cursor-commands'; then
  echo "⛔ Refusing to push: commits include .cursor-commands (governance repo only)." >&2
  echo "   Remove those paths from the branch before pushing to IB-Odoo_19." >&2
  exit 1
fi

if [[ "${OPEN_PR}" != "1" ]]; then
  refuse "open_pr=${OPEN_PR}; publication must create or verify the PR"
fi

echo "→ Push branch → origin/${TARGET}..."
bash scripts/git_push_with_pr.sh "${TARGET}"
echo ""

echo "→ Open/verify PR → ${BASE}..."
if ! bash scripts/git_open_pr.sh "${TARGET}" "${BASE}"; then
  echo "partial publication: origin/${TARGET} was pushed at $(git rev-parse HEAD)," >&2
  echo "but the pull request into ${BASE} was not created or proven. Re-run make pr to create/verify it." >&2
  exit 1
fi

PR_SMOKE_BYPASS="${PR_SMOKE_BYPASS:-}"
if [[ -n "${PR_SMOKE_BYPASS// /}" ]]; then
  bypass_note="Local Odoo install-smoke was bypassed for $(git rev-parse HEAD) by the operator: ${PR_SMOKE_BYPASS}"
  if ! pr_number="$(open_pr_number)" || [[ -z "${pr_number}" ]] \
    || ! gh api --method POST "repos/${GH_REPO}/issues/${pr_number}/comments" -f body="${bypass_note}" >/dev/null; then
    echo "warning: could not post the install-smoke bypass note on the PR" >&2
  fi
fi
