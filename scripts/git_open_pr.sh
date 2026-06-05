#!/usr/bin/env bash
# Create or refresh GitHub PR with kernel-derived title, body, and labels.
set -euo pipefail

TARGET="${1:?head branch}"
BASE="${2:-Staging}"

if ! command -v gh >/dev/null 2>&1; then
  echo "⚠️  gh CLI not found — install GitHub CLI or open PR manually"
  exit 0
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "⚠️  gh not authenticated — run: gh auth login"
  exit 0
fi

for skip in "${BASE}" Staging Production staging production; do
  if [[ "${TARGET}" == "${skip}" ]]; then
    echo "→ Skipping PR (integration branch ${TARGET})"
    exit 0
  fi
done

EXISTING="$(gh pr list --head "${TARGET}" --base "${BASE}" --state open --json number,url --jq '.[0]' 2>/dev/null || true)"
if [[ -n "${EXISTING}" && "${EXISTING}" != "null" ]]; then
  PR_NUM="$(echo "${EXISTING}" | python3 -c "import json,sys; print(json.load(sys.stdin).get('number',''))")"
  PR_URL="$(echo "${EXISTING}" | python3 -c "import json,sys; print(json.load(sys.stdin).get('url',''))")"
  echo "✅ Open PR #${PR_NUM} → ${BASE}: ${PR_URL}"
  bash scripts/apply_pr_kernel_metadata.sh "${PR_NUM}" || true
  echo "   CI + auto-merge run on synchronize (.github/workflows/auto-merge.yml)"
  exit 0
fi

git fetch origin "${BASE}" 2>/dev/null || true
AHEAD="$(git rev-list --count "origin/${BASE}..HEAD" 2>/dev/null || echo 0)"
if [[ "${AHEAD}" == "0" ]]; then
  echo "⚠️  No commits ahead of origin/${BASE} — PR not created"
  exit 0
fi

TITLE="$(git log -1 --pretty=%s)"
BODY="$(python3 scripts/build_pr_body.py "${BASE}")"

if ! PR_URL="$(gh pr create --base "${BASE}" --head "${TARGET}" --title "${TITLE}" --body "${BODY}")"; then
  echo "⚠️  gh pr create failed"
  exit 0
fi

echo "✅ PR created → ${BASE}: ${PR_URL}"
PR_NUM="$(gh pr list --head "${TARGET}" --base "${BASE}" --state open --json number --jq '.[0].number' 2>/dev/null || true)"
if [[ -n "${PR_NUM}" ]]; then
  bash scripts/apply_pr_kernel_metadata.sh "${PR_NUM}" || true
fi
echo "   CI Gate runs on pull_request; auto-merge when checks pass"
