#!/usr/bin/env bash
# Full github push kernel: pr-check → commit → push → PR (CI + auto-merge).
# Usage: make_push_pipeline.sh [message] [target] [base] [open_pr] [do_commit]
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"

MSG="${1:-}"
TARGET="${2:-$(git branch --show-current)}"
BASE="${3:-Staging}"
OPEN_PR="${4:-1}"
DO_COMMIT="${5:-1}"

echo "══════════════════════════════════════════════════════"
echo "  make push — pr-check → commit → push → PR"
echo "══════════════════════════════════════════════════════"
echo ""

echo "→ [1/4] PR gate (pipeline checks on workspace, before commit)..."
make pr-check
echo ""

if [[ "${DO_COMMIT}" == "1" ]]; then
  echo "→ [2/4] Commit (conventional message kernel + GA workflow kernel)..."
  bash scripts/git_commit_workspace.sh "${MSG}"
else
  echo "→ [2/4] Skipping commit (commit=0)"
fi
echo ""

echo "→ [3/4] Push branch → origin/${TARGET}..."
bash scripts/git_push_with_pr.sh "${TARGET}"
echo ""

if [[ "${OPEN_PR}" == "0" ]]; then
  echo "→ [4/4] Skipping PR (pr=0)"
  exit 0
fi

echo "→ [4/4] Open/update PR → ${BASE} (labels + CI)..."
bash scripts/git_open_pr.sh "${TARGET}" "${BASE}"
