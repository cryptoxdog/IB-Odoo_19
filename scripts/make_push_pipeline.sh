#!/usr/bin/env bash
# Publication kernel behind `make pr`: pr-check → push → open/verify PR.
# Usage: make_push_pipeline.sh [message] [target] [base] [open_pr] [do_commit]
# `make pr` calls this with do_commit=0. It publishes the committed HEAD only.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${ROOT}" ]]; then
  echo "refusing to publish: not inside a git repository"
  exit 1
fi
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"

MSG="${1:-}"
CURRENT="$(git branch --show-current)"
TARGET="${2:-${CURRENT}}"
BASE="${3:-Staging}"
OPEN_PR="${4:-1}"
DO_COMMIT="${5:-0}"

if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "refusing to publish: HEAD does not exist"
  exit 1
fi

if [[ -z "${CURRENT}" ]]; then
  echo "refusing to publish: detached HEAD; publication requires an attached feature branch"
  exit 1
fi

if [[ -z "${TARGET}" ]]; then
  echo "refusing to publish: publication target branch is empty"
  exit 1
fi

if [[ "${CURRENT}" != "${TARGET}" ]]; then
  echo "refusing to publish: current branch ${CURRENT} is not the publication target ${TARGET}"
  exit 1
fi

# Production is not an ordinary working branch. Staging is: feature work
# publishes into Staging, and an explicit Staging → Production promotion is
# allowed. Any source that matches its base is a self-PR and stops here.
current_lc="$(printf '%s' "${CURRENT}" | tr '[:upper:]' '[:lower:]')"
base_lc="$(printf '%s' "${BASE}" | tr '[:upper:]' '[:lower:]')"
if [[ "${current_lc}" == "production" ]]; then
  echo "refusing to publish: Production is not an ordinary source branch"
  exit 1
fi
if [[ "${current_lc}" == "${base_lc}" ]]; then
  echo "refusing to publish: ${CURRENT} → ${BASE} is a self-PR; source and base must differ"
  exit 1
fi

require_clean() {
  local status
  status="$(git status --porcelain)"
  if [[ -n "${status}" ]]; then
    echo "refusing to publish: working tree, index, or untracked files are not clean"
    printf '%s\n' "${status}"
    exit 1
  fi
}

if [[ "${DO_COMMIT}" != "1" ]]; then
  require_clean
fi

echo "══════════════════════════════════════════════════════"
echo "  make pr — pr-check → push → PR"
echo "  ${CURRENT} → ${BASE}"
echo "══════════════════════════════════════════════════════"
echo ""

if [[ "${DO_COMMIT}" == "1" ]]; then
  echo "→ Commit (explicit do_commit=1 only; make pr does not use this)..."
  bash scripts/git_commit_workspace.sh "${MSG}"
  echo ""
  require_clean
fi

# Makefile COMMIT_EXCLUDE (.cursor-commands). Same refusal the pre-#222 push
# path used: the published commit range must not contain that governance path,
# including when it was committed outside make commit.
range_base="$(git merge-base HEAD "origin/${BASE}" 2>/dev/null || true)"
if [[ -z "${range_base}" ]]; then
  range_base="$(git rev-list --max-parents=0 HEAD | tail -1)"
fi
if git diff --name-only "${range_base}..HEAD" | grep -q '^\.cursor-commands'; then
  echo "⛔ Refusing to push: commits include .cursor-commands (governance repo only)."
  echo "   Remove those paths from the branch before pushing to IB-Odoo_19."
  exit 1
fi

echo "→ PR gate (make pr-check, once, before remote mutation)..."
make pr-check
echo ""

echo "→ Push branch → origin/${TARGET}..."
bash scripts/git_push_with_pr.sh "${TARGET}"
echo ""

if [[ "${OPEN_PR}" != "1" ]]; then
  echo "refusing to publish: open_pr=${OPEN_PR}; publication must create or verify the PR"
  exit 1
fi

echo "→ Open/verify PR → ${BASE}..."
bash scripts/git_open_pr.sh "${TARGET}" "${BASE}"
