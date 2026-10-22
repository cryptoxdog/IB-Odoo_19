#!/usr/bin/env bash
# Create or reuse the GitHub PR and prove it points at local HEAD.
#
# GitHub is reached over REST only (`gh api repos/{owner}/{repo}/...`). The
# `gh pr list/view/edit/create` forms are GraphQL-backed and are refused on a
# model-controlled surface whose egress proxy injects the credential; there
# `gh auth status` also reports a false negative while `gh api user` works
# (Cursor-Governance rule 62, docs/DEGRADED_MODE_CONTRACT.md).
set -euo pipefail

TARGET="${1:?head branch}"
BASE="${2:-Staging}"
LOCAL_SHA="$(git rev-parse HEAD)"

if [[ "${BASE}" != "Staging" ]]; then
  echo "refusing to publish: destination must be Staging (got ${BASE})" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is not available; publication cannot verify the pull request"
  exit 1
fi

if ! gh api user >/dev/null 2>&1; then
  echo "gh is not authenticated (gh api user failed); run: gh auth login"
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

# owner/name of the publication repository: GH_REPO (exported by the push
# pipeline) or the origin remote URL.
REPO="${GH_REPO:-}"
if [[ -z "${REPO}" ]]; then
  REPO="$(git remote get-url origin 2>/dev/null | sed -E 's#^(https://|git://|ssh://)?(git@)?github\.com[:/]##; s#\.git$##')"
fi
if [[ "${REPO}" != */* ]]; then
  echo "cannot determine the GitHub repository (GH_REPO unset and origin is not a github.com URL)"
  exit 1
fi
OWNER="${REPO%%/*}"

# One open PR for TARGET → BASE as a JSON object, or "null".
list_open_pr() {
  local raw
  if ! raw="$(gh api --method GET "repos/${REPO}/pulls" -f state=open -f base="${BASE}" -f head="${OWNER}:${TARGET}")"; then
    return 1
  fi
  python3 -c 'import json,sys; items=json.loads(sys.argv[1] or "[]"); print(json.dumps(items[0]) if items else "null")' "${raw}"
}

if ! EXISTING="$(list_open_pr)"; then
  echo "pull request lookup failed for ${TARGET} → ${BASE} (gh api repos/${REPO}/pulls)"
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
url = pr.get("html_url") or ""
state = pr.get("state") or ""
base_name = (pr.get("base") or {}).get("ref") or ""
head_name = (pr.get("head") or {}).get("ref") or ""
head_sha = (pr.get("head") or {}).get("sha") or ""
problems = []
if not number:
    problems.append("missing PR number")
if not url:
    problems.append("missing PR url")
if state != "open":
    problems.append(f"state is {state or 'missing'}, expected open")
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

ensure_protected_root_stamp() {
  local number="$1"
  local stamp="<!-- L9_PROTECTED_ROOT_PR -->"
  local body
  body="$(gh api "repos/${REPO}/pulls/${number}" --jq '.body // ""')"
  if printf '%s' "${body}" | grep -qF "${stamp}"; then
    return 0
  fi
  # REST PATCH: `gh pr edit --body` is GraphQL-backed and unavailable here.
  gh api --method PATCH "repos/${REPO}/pulls/${number}" -f body="$(printf '%s\n\n%s\n' "${body}" "${stamp}")" >/dev/null
}

if [[ -n "${EXISTING}" && "${EXISTING}" != "null" ]]; then
  # GitHub updates an open PR's head asynchronously after the push; re-read
  # a few times before declaring the SHA wrong. Every other mismatch (base,
  # branch, state) is final on the first read.
  for _attempt in 1 2 3 4 5 6; do
    SEEN_SHA="$(python3 -c 'import json,sys; print((json.loads(sys.argv[1]).get("head") or {}).get("sha") or "")' "${EXISTING}")"
    [[ "${SEEN_SHA}" == "${LOCAL_SHA}" ]] && break
    sleep 5
    EXISTING="$(list_open_pr)"
  done
  PROOF="$(prove_pr "${EXISTING}")"
  PR_NUM="${PROOF%%$'\t'*}"
  PR_URL="${PROOF#*$'\t'}"
  echo "✅ Open PR #${PR_NUM} → ${BASE}: ${PR_URL}"
  echo "   head ${LOCAL_SHA}"
  ensure_protected_root_stamp "${PR_NUM}"
  bash scripts/apply_pr_kernel_metadata.sh "${PR_NUM}" || true
  echo "   Merge is a separate human decision. This command does not merge."
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
STAMP="<!-- L9_PROTECTED_ROOT_PR -->"
if ! printf '%s' "${BODY}" | grep -qF "${STAMP}"; then
  BODY="${BODY}"$'\n\n'"${STAMP}"
fi

# REST POST returns the created PR; it is the proof input, no second lookup.
if ! CREATED="$(gh api --method POST "repos/${REPO}/pulls" -f base="${BASE}" -f head="${TARGET}" -f title="${TITLE}" -f body="${BODY}")"; then
  echo "pull request creation failed for ${TARGET} → ${BASE} (gh api repos/${REPO}/pulls)"
  exit 1
fi
PROOF="$(prove_pr "${CREATED}")"
PR_NUM="${PROOF%%$'\t'*}"
PR_URL="${PROOF#*$'\t'}"
echo "✅ PR created → ${BASE}: ${PR_URL}"
echo "   head ${LOCAL_SHA}"
bash scripts/apply_pr_kernel_metadata.sh "${PR_NUM}" || true
echo "   Merge is a separate human decision. This command does not merge."
