#!/usr/bin/env bash
# Publication kernel behind `make pr`: preflight → pr-check → L4 → push → PR.
# Usage: make_push_pipeline.sh [message] [target] [base] [open_pr] [do_commit]
# `make pr` publishes one committed feature branch into Staging only.
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
if [[ "${BASE}" != "Staging" ]]; then
  refuse "destination must be Staging (got ${BASE})"
fi

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

if ! command -v gh >/dev/null 2>&1; then
  refuse "gh CLI is not available; publication cannot create or verify the pull request"
fi
if ! gh auth status >/dev/null 2>&1; then
  refuse "gh is not authenticated"
fi
if ! gh pr list --head "${TARGET}" --base "${BASE}" --state open --json number >/dev/null 2>&1; then
  refuse "cannot look up pull requests for ${TARGET} → ${BASE}"
fi

echo "══════════════════════════════════════════════════════"
echo "  make pr — pr-check → L4 → push → PR"
echo "  ${CURRENT} → ${BASE}"
echo "══════════════════════════════════════════════════════"
echo ""

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
  pr_number="$(gh pr list --head "${TARGET}" --base "${BASE}" --state open --json number --jq '.[0].number')"
  if [[ -z "${pr_number}" ]] || ! gh pr comment "${pr_number}" --body "${bypass_note}" >/dev/null; then
    echo "warning: could not post the install-smoke bypass note on the PR" >&2
  fi
fi
