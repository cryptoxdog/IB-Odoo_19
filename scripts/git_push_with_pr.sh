#!/usr/bin/env bash
# Push current branch to origin (upstream tracking).
set -euo pipefail

TARGET="${1:?target branch required}"

BRANCH="$(git branch --show-current)"

if ! git push -u origin "HEAD:${TARGET}"; then
  echo "⚠️  git push failed (Dropbox mmap issue?). Run: make api-push-check"
  exit 1
fi
echo "✅ Push complete → origin/${TARGET} (${BRANCH})"
