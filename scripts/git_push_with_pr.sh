#!/usr/bin/env bash
# Push the current HEAD and prove origin's branch ref matches it.
set -euo pipefail

TARGET="${1:?target branch required}"
LOCAL_SHA="$(git rev-parse HEAD)"

if ! git push -u origin "HEAD:${TARGET}"; then
  echo "git push failed for origin/${TARGET} (local HEAD ${LOCAL_SHA})"
  echo "Dropbox mmap issue? Run: make api-push-check"
  exit 1
fi

REMOTE_SHA="$(git ls-remote --heads origin "${TARGET}" | awk 'NR == 1 { print $1 }')"
if [[ -z "${REMOTE_SHA}" ]]; then
  echo "remote refs/heads/${TARGET} is missing after push; local HEAD is ${LOCAL_SHA}"
  exit 1
fi
if [[ "${REMOTE_SHA}" != "${LOCAL_SHA}" ]]; then
  echo "remote refs/heads/${TARGET} is ${REMOTE_SHA}; local HEAD is ${LOCAL_SHA}"
  exit 1
fi
echo "✅ Push complete → origin/${TARGET} (${LOCAL_SHA})"
