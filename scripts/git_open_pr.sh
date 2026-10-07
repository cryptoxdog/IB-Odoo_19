#!/usr/bin/env bash
# Create or reuse the GitHub PR and prove it points at local HEAD.
set -euo pipefail

TARGET="${1:?head branch}"
BASE="${2:-Staging}"
LOCAL_SHA="$(git rev-parse HEAD)"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is not available; publication cannot verify the pull request"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "gh is not authenticated; run: gh auth login"
  exit 1
fi

case "${TARGET}" in
  Staging|Production|staging|production)
    echo "refusing to publish: ${TARGET} is a protected branch"
    exit 1
    ;;
esac

if [[ "${TARGET}" == "${BASE}" ]]; then
  echo "refusing to publish: head and base are both ${TARGET}"
  exit 1
fi

PR_FIELDS="number,url,state,baseRefName,headRefName,headRefOid"

if ! EXISTING="$(gh pr list --head "${TARGET}" --base "${BASE}" --state open --json "${PR_FIELDS}" --jq '.[0]')"; then
  echo "gh pr list failed for ${TARGET} → ${BASE}"
  exit 1
fi

prove_pr() {
  python3 - "$1" "${BASE}" "${TARGET}" "${LOCAL_SHA}" <<'PY'
import json
import sys

raw, base, target, local_sha = sys.argv[1:]
if not raw or raw == "null":
    print("pull request query returned no open PR", file=sys.stderr)
    sys.exit(1)
pr = json.loads(raw)
number = pr.get("number")
url = pr.get("url") or ""
state = pr.get("state") or ""
base_name = pr.get("baseRefName") or ""
head_name = pr.get("headRefName") or ""
head_sha = pr.get("headRefOid") or ""
problems = []
if not number:
    problems.append("missing PR number")
if not url:
    problems.append("missing PR url")
if state != "OPEN":
    problems.append(f"state is {state or 'missing'}, expected OPEN")
if base_name != base:
    problems.append(f"base is {base_name or 'missing'}, expected {base}")
if head_name != target:
    problems.append(f"head branch is {head_name or 'missing'}, expected {target}")
if head_sha != local_sha:
    problems.append(f"head SHA is {head_sha or 'missing'}, expected {local_sha}")
if problems:
    print("PR publication proof failed:", file=sys.stderr)
    for item in problems:
        print(f"  {item}", file=sys.stderr)
    sys.exit(1)
print(f"{number}\t{url}")
PY
}

if [[ -n "${EXISTING}" && "${EXISTING}" != "null" ]]; then
  PROOF="$(prove_pr "${EXISTING}")"
  PR_NUM="${PROOF%%$'\t'*}"
  PR_URL="${PROOF#*$'\t'}"
  echo "✅ Open PR #${PR_NUM} → ${BASE}: ${PR_URL}"
  echo "   head ${LOCAL_SHA}"
  bash scripts/apply_pr_kernel_metadata.sh "${PR_NUM}" || true
  echo "   CI + auto-merge run on synchronize (.github/workflows/auto-merge.yml)"
  exit 0
fi

if ! git fetch origin "${BASE}"; then
  echo "git fetch origin/${BASE} failed; cannot tell whether this branch is ahead"
  exit 1
fi
AHEAD="$(git rev-list --count "origin/${BASE}..HEAD")"
if [[ "${AHEAD}" == "0" ]]; then
  echo "no commits ahead of origin/${BASE} and no open PR for ${TARGET}"
  exit 1
fi

TITLE="$(git log -1 --pretty=%s)"
BODY="$(python3 scripts/build_pr_body.py "${BASE}")"

if ! gh pr create --base "${BASE}" --head "${TARGET}" --title "${TITLE}" --body "${BODY}" >/dev/null; then
  echo "gh pr create failed for ${TARGET} → ${BASE}"
  exit 1
fi

if ! CREATED="$(gh pr list --head "${TARGET}" --base "${BASE}" --state open --json "${PR_FIELDS}" --jq '.[0]')"; then
  echo "gh pr list failed after create for ${TARGET} → ${BASE}"
  exit 1
fi
PROOF="$(prove_pr "${CREATED}")"
PR_NUM="${PROOF%%$'\t'*}"
PR_URL="${PROOF#*$'\t'}"
echo "✅ PR created → ${BASE}: ${PR_URL}"
echo "   head ${LOCAL_SHA}"
bash scripts/apply_pr_kernel_metadata.sh "${PR_NUM}" || true
echo "   CI Gate runs on pull_request; auto-merge when checks pass"
