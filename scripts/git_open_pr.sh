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

# The SSOT injector: the Cursor-Governance composer (ops/scripts/compose_pr_body.py)
# that SSOT make pr runs for every L9 repository, called with the same flags
# open_pr_after_gate.sh passes. It fills the Quantum-L9/.github PR template at an
# exact commit (Files touched first). The one difference: SSOT make pr names the
# repo's owner as the template owner, and cryptoxdog has no .github template, so
# the owner here is Quantum-L9 (PR_TEMPLATE_OWNER overrides). Odoo builds no body
# of its own; .github/pull_request_template.md is the org template's byte copy for
# the GitHub web page, and the composer never reads it.
ssot_compose() {
  local resolver="${HOME}/.cursor-governance/ops/scripts/resolve_governance_paths.sh"
  local root py touched
  if [[ ! -f "${resolver}" ]]; then
    echo "the SSOT composer is not available (no governance resolver at \$HOME/.cursor-governance)" >&2
    return 1
  fi
  # shellcheck disable=SC1090
  source "${resolver}"
  resolve_governance_paths || return 1
  py="${GOV_ROOT}/.venv/bin/python"
  [[ -x "${py}" ]] || py="python3"
  root="$(git rev-parse --show-toplevel)"
  mkdir -p "${root}/.l9/pr"
  local args=(--workspace "${root}" --pr-base "origin/${BASE}"
    --org-owner "${PR_TEMPLATE_OWNER:-Quantum-L9}" --repo-name "IB-Odoo_19")
  [[ -f "${root}/.l9/pr/pr-intent.json" ]] && args+=(--intent-file "${root}/.l9/pr/pr-intent.json")
  if [[ "${1:-}" != "--print-title" ]]; then
    # Protected-root, measured as open_pr_after_gate.sh measures it: a measured
    # empty list is an answer, an unmeasured range is said to be unmeasured.
    if [[ -f "${root}/ops/config/root-file-protection.json" && -f "${GOV_ROOT}/ops/scripts/validate_root_file_protection.py" ]]; then
      if touched="$("${py}" "${GOV_ROOT}/ops/scripts/validate_root_file_protection.py" --list-touched-additive-only \
          --base "origin/${BASE}" --head HEAD --repo "${root}" 2>/dev/null)"; then
        if [[ -n "${touched}" ]]; then
          printf '%s\n' "${touched}" > "${root}/.l9/pr/additive-only.txt"
          args+=(--additive-only-file "${root}/.l9/pr/additive-only.txt")
        fi
      else
        args+=(--additive-only-unmeasured)
      fi
    fi
  fi
  "${py}" "${GOV_ROOT}/ops/scripts/compose_pr_body.py" "${args[@]}" "$@"
}

# The range moved, so the machine-owned regions of a composed body (Files
# touched, Changes by intent, Evidence, Protected-root) are stale. Recompose
# those regions only, as SSOT make pr does; text a person wrote, ticked gates
# and the title stay. A body the composer did not write is "unmanaged" and left
# alone. Advisory: a refresh failure never fails a publication already pushed.
refresh_composed_body() {
  local number="$1" scratch status
  scratch="$(git rev-parse --show-toplevel)/.l9/pr"
  mkdir -p "${scratch}"
  if ! gh api "repos/${GH_REPO}/pulls/${number}" --jq '.body // ""' >"${scratch}/open-pr-body.md"; then
    echo "   warning: could not read the open PR body; it was not refreshed" >&2
    return 0
  fi
  rm -f "${scratch}/pr-body-refresh.json"
  if ! ssot_compose --refresh-body "${scratch}/open-pr-body.md" \
      --status-file "${scratch}/pr-body-refresh.json" >"${scratch}/pr-body.md"; then
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
    unmanaged) echo "   body has no machine-owned regions and was not composed by make pr; left as written" ;;
    *) echo "   warning: PR body refresh status unreadable (${status}); not refreshed" >&2 ;;
  esac
}

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

if ! TITLE="$(ssot_compose --print-title)" || [[ -z "${TITLE}" ]]; then
  TITLE="$(git log -1 --pretty=%s)"
fi
if ! BODY="$(ssot_compose --handoff "$(git rev-parse --show-toplevel)/.l9/pr/pr-body-completion.json")" \
    || [[ -z "${BODY}" ]]; then
  echo "could not compose the PR body with the SSOT composer; the branch is pushed but no PR was opened"
  exit 1
fi
if [[ "${BASE}" != "Staging" ]]; then
  # A stacked PR merges after its parent. Say so under the file list, outside
  # every machine-owned region, so a refresh keeps it.
  BODY="$(STACK_NOTE="Stacked on \`${BASE}\`; merge that branch's pull request into Staging first." python3 -c '
import os, sys
body, note, end = sys.stdin.read(), os.environ["STACK_NOTE"], "<!-- FILES-TOUCHED:END -->"
if end in body:
    head, tail = body.split(end, 1)
    sys.stdout.write(f"{head}{end}\n\n{note}\n{tail}")
else:
    sys.stdout.write(f"{note}\n\n{body}")
' <<<"${BODY}")"
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
