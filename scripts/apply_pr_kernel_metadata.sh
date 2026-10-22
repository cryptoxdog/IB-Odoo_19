#!/usr/bin/env bash
# Apply labels/comments to an existing PR (best-effort; unknown labels are skipped).
# REST only: `gh label list` / `gh pr edit --add-label` are GraphQL-backed.
set -euo pipefail

PR_NUM="${1:?PR number}"
REPO="${GH_REPO:-cryptoxdog/IB-Odoo_19}"
TITLE="$(git log -1 --pretty=%s)"
LABELS="$(python3 scripts/pr_labels_from_commit.py "${TITLE}" 2>/dev/null || true)"

for label in ${LABELS}; do
  if gh api "repos/${REPO}/labels?per_page=100" --jq '.[].name' 2>/dev/null | grep -qx "${label}"; then
    gh api --method POST "repos/${REPO}/issues/${PR_NUM}/labels" -f "labels[]=${label}" >/dev/null 2>&1 || true
  fi
done
