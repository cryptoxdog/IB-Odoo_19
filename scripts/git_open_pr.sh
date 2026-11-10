#!/usr/bin/env bash
# Create or reuse the GitHub PR and prove it points at local HEAD.
#
# GitHub is reached over REST only (`gh api repos/OWNER/REPO/...`). The
# `gh pr` / `gh label` forms are GraphQL-backed and refused (HTTP 403) on a
# surface whose egress proxy injects the credential; there `gh auth status`
# also reports a false negative while `gh api user` works.
set -euo pipefail

TARGET="${1:?head branch}"
BASE="${2:-Staging}"
LOCAL_SHA="$(git rev-parse HEAD)"

bash scripts/pr_stack_parent.sh name "${BASE}"

# Publication repository: the one authorized origin push URL, also when this
# script runs on its own. An inherited GH_REPO naming another repository is
# refused, never used.
PUSH_URLS="$(git remote get-url --push --all origin 2>/dev/null || true)"
if [[ -z "${PUSH_URLS}" || "${PUSH_URLS}" == *$'\n'* ]]; then
  echo "refusing to publish: origin must have exactly one push URL" >&2
  exit 1
fi
case "${PUSH_URLS%.git}" in
  https://github.com/cryptoxdog/IB-Odoo_19 | git://github.com/cryptoxdog/IB-Odoo_19 | \
    git@github.com:cryptoxdog/IB-Odoo_19 | ssh://git@github.com/cryptoxdog/IB-Odoo_19) ;;
  *)
    echo "refusing to publish: origin push URL is not cryptoxdog/IB-Odoo_19 (${PUSH_URLS})" >&2
    exit 1
    ;;
esac
if [[ -n "${GH_REPO:-}" && "${GH_REPO}" != "cryptoxdog/IB-Odoo_19" ]]; then
  echo "refusing to publish: GH_REPO=${GH_REPO} is not the origin repository cryptoxdog/IB-Odoo_19" >&2
  exit 1
fi
# `gh api repos/...` takes its host from GH_HOST, not from origin; pin it too.
if [[ -n "${GH_HOST:-}" && "${GH_HOST}" != "github.com" ]]; then
  echo "refusing to publish: GH_HOST=${GH_HOST} is not the origin host github.com" >&2
  exit 1
fi
export GH_REPO="cryptoxdog/IB-Odoo_19" GH_HOST="github.com"
OWNER="${GH_REPO%%/*}"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is not available; publication cannot verify the pull request"
  exit 1
fi

if ! gh api user >/dev/null 2>&1; then
  echo "gh is not authenticated (gh api user failed); run: gh auth login"
  exit 1
fi
if [[ "${BASE}" != "Staging" ]]; then
  bash scripts/pr_stack_parent.sh prove "${BASE}"
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

# The open PR for TARGET → BASE as one JSON object, or "null".
list_open_pr() {
  local raw
  raw="$(gh api --method GET "repos/${GH_REPO}/pulls" -f state=open -f base="${BASE}" -f head="${OWNER}:${TARGET}")" \
    || return 1
  python3 -c '
import json, sys
try:
    items = json.loads(sys.argv[1])
except ValueError:
    sys.exit("pull request lookup returned malformed JSON")
if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
    sys.exit("pull request lookup did not return a list of pull requests")
print(json.dumps(items[0]) if items else "null")
' "${raw}"
}

if ! EXISTING="$(list_open_pr)"; then
  echo "pull request lookup failed for ${TARGET} → ${BASE} (gh api repos/${GH_REPO}/pulls)"
  exit 1
fi

prove_pr() {
  python3 - "$1" "${BASE}" "${TARGET}" "${LOCAL_SHA}" "${GH_REPO}" <<'PY'
import json
import sys

raw, base, target, local_sha, repo = sys.argv[1:]
if not raw or raw == "null":
    print("pull request query returned no open PR", file=sys.stderr)
    sys.exit(1)
try:
    pr = json.loads(raw)
except ValueError:
    print("pull request response is malformed JSON", file=sys.stderr)
    sys.exit(1)
if not isinstance(pr, dict):
    print("pull request response is not an object", file=sys.stderr)
    sys.exit(1)
base_ref = pr.get("base") or {}
head_ref = pr.get("head") or {}
number = pr.get("number")
url = pr.get("html_url") or ""
state = pr.get("state") or ""
base_name = base_ref.get("ref") or ""
base_repo = (base_ref.get("repo") or {}).get("full_name") or ""
head_name = head_ref.get("ref") or ""
head_repo = (head_ref.get("repo") or {}).get("full_name") or ""
head_sha = head_ref.get("sha") or ""
problems = []
if not number:
    problems.append("missing PR number")
if not url:
    problems.append("missing PR url")
if state != "open":
    problems.append(f"state is {state or 'missing'}, expected open")
if base_name != base:
    problems.append(f"base is {base_name or 'missing'}, expected {base}")
if base_repo != repo:
    problems.append(f"base repository is {base_repo or 'missing'}, expected {repo}")
if head_repo != repo:
    problems.append(f"head repository is {head_repo or 'missing'}, expected {repo}")
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
  body="$(gh api "repos/${GH_REPO}/pulls/${number}" --jq '.body // ""')"
  if printf '%s' "${body}" | grep -qF "${stamp}"; then
    return 0
  fi
  gh api --method PATCH "repos/${GH_REPO}/pulls/${number}" \
    -f body="$(printf '%s\n\n%s\n' "${body}" "${stamp}")" >/dev/null
}

# The range moved, so the machine-owned regions of a composed body (Files
# touched, Changes by intent, Evidence, Protected-root) are stale. Recompose
# those regions only; prose a person wrote, ticked gates and the title stay.
# A body the composer did not write is "unmanaged" and left as it is. Advisory:
# a refresh failure never fails a publication that has already pushed.
refresh_composed_body() {
  local number="$1" scratch status
  scratch="$(git rev-parse --show-toplevel)/.l9/pr"
  mkdir -p "${scratch}"
  if ! gh api "repos/${GH_REPO}/pulls/${number}" --jq '.body // ""' >"${scratch}/open-pr-body.md"; then
    echo "   warning: could not read the open PR body; it was not refreshed" >&2
    return 0
  fi
  rm -f "${scratch}/pr-body-refresh.json"
  if ! bash scripts/compose_pr_body.sh refresh "${BASE}" "${scratch}/open-pr-body.md" \
      "${scratch}/pr-body-refresh.json" >"${scratch}/pr-body.md"; then
    echo "   warning: the composer could not refresh the PR body; it keeps its previous text" >&2
    return 0
  fi
  status="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' \
    "${scratch}/pr-body-refresh.json" 2>/dev/null || echo unknown)"
  case "${status}" in
    updated|migrated)
      if gh api --method PATCH "repos/${GH_REPO}/pulls/${number}" \
          -f body="$(cat "${scratch}/pr-body.md")" >/dev/null; then
        echo "   body refreshed (${status}): Files touched and the other machine-owned regions match this range"
      else
        echo "   warning: could not PATCH the refreshed PR body" >&2
      fi
      ;;
    unchanged) echo "   body unchanged: its machine-owned regions already match this range" ;;
    unmanaged) echo "   body has no machine-owned regions and was not composed here; left as written" ;;
    *) echo "   warning: PR body refresh status unreadable (${status}); not refreshed" >&2 ;;
  esac
}

if [[ -n "${EXISTING}" && "${EXISTING}" != "null" ]]; then
  # GitHub updates an open PR's head asynchronously after the push; re-read
  # a few times before declaring the SHA wrong. Every other mismatch (base,
  # branch, repository, state) is final on the first read.
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
  refresh_composed_body "${PR_NUM}"
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

# One template, one composer (scripts/compose_pr_body.sh): the org template
# with every touched file listed first. No local builder, no local template.
if ! TITLE="$(bash scripts/compose_pr_body.sh title "${BASE}")" || [[ -z "${TITLE}" ]]; then
  TITLE="$(git log -1 --pretty=%s)"
fi
if ! BODY="$(bash scripts/compose_pr_body.sh body "${BASE}")" || [[ -z "${BODY}" ]]; then
  echo "could not compose the PR body from the org template (scripts/compose_pr_body.sh)"
  exit 1
fi
STAMP="<!-- L9_PROTECTED_ROOT_PR -->"
if ! printf '%s' "${BODY}" | grep -qF "${STAMP}"; then
  BODY="${BODY}"$'\n\n'"${STAMP}"
fi

# The POST response is the created PR; it is the proof input, not a later lookup.
if ! CREATED="$(gh api --method POST "repos/${GH_REPO}/pulls" \
  -f base="${BASE}" -f head="${TARGET}" -f title="${TITLE}" -f body="${BODY}")"; then
  echo "pull request creation failed for ${TARGET} → ${BASE} (gh api repos/${GH_REPO}/pulls)"
  exit 1
fi
PROOF="$(prove_pr "${CREATED}")"
PR_NUM="${PROOF%%$'\t'*}"
PR_URL="${PROOF#*$'\t'}"
echo "✅ PR created → ${BASE}: ${PR_URL}"
echo "   head ${LOCAL_SHA}"
bash scripts/apply_pr_kernel_metadata.sh "${PR_NUM}" || true
echo "   Merge is a separate human decision. This command does not merge."
