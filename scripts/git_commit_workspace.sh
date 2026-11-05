#!/usr/bin/env bash
# Stage workspace, validate conventional commit (kernel), commit.
# Called after make pr-check in make_push_pipeline.sh.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "${ROOT}"

MSG="${1:-}"
REQUIRE_CHANGES="${2:-}"

if git diff --quiet && git diff --cached --quiet \
  && [[ -z "$(git ls-files --others --exclude-standard)" ]]; then
  if [[ "${REQUIRE_CHANGES}" == "require" ]]; then
    echo "Nothing to commit (working tree clean)."
    exit 1
  fi
  echo "→ Nothing to commit (working tree clean)."
  exit 0
fi

echo "→ Staging all changes (git add -A)..."
git add -A

if git diff --cached --quiet; then
  if [[ "${REQUIRE_CHANGES}" == "require" ]]; then
    echo "Nothing to commit after staging (ignored paths only?)."
    exit 1
  fi
  echo "→ Nothing to commit after staging (ignored paths only?)."
  exit 0
fi

if [[ -z "${MSG}" ]]; then
  echo "→ Inferring conventional commit message from staged files..."
  MSG="$(python3 scripts/infer_conventional_commit.py)"
  echo "   Proposed: ${MSG}"
fi

echo "→ Validating commit message (conventional commit kernel)..."
python3 scripts/validate_conventional_commit.py "${MSG}"

MSG_FILE="$(mktemp)"
trap 'rm -f "${MSG_FILE}"' EXIT
printf '%s\n' "${MSG}" >"${MSG_FILE}"
if command -v pre-commit >/dev/null 2>&1; then
  pre-commit run conventional-pre-commit \
    --hook-stage commit-msg \
    --commit-msg-filename "${MSG_FILE}" \
    || {
      echo "❌ pre-commit conventional-pre-commit rejected the message"
      exit 1
    }
fi

if git diff --cached --name-only | grep -qE '^\.github/workflows/.*\.ya?ml$'; then
  echo "→ Workflow files staged — running GitHub Actions kernel..."
  make github-actions-kernel-check staged=1
fi

echo "→ Committing: ${MSG}"
git commit -F "${MSG_FILE}"

echo ""
echo "============================================"
echo "Committed ($(git rev-parse --short HEAD)):"
echo "============================================"
git show --stat --oneline -1
