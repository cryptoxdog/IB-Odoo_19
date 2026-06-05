#!/usr/bin/env bash
# Apply labels/comments to an existing PR (best-effort; unknown labels are skipped).
set -euo pipefail

PR_NUM="${1:?PR number}"
TITLE="$(git log -1 --pretty=%s)"
LABELS="$(python3 scripts/pr_labels_from_commit.py "${TITLE}" 2>/dev/null || true)"

for label in ${LABELS}; do
  if gh label list --json name --jq '.[].name' 2>/dev/null | grep -qx "${label}"; then
    gh pr edit "${PR_NUM}" --add-label "${label}" 2>/dev/null || true
  fi
done
