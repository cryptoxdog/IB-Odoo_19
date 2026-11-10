#!/usr/bin/env bash
# PR title and body for `make pr`, from ONE template: the org template
# `${PR_TEMPLATE_OWNER:-Quantum-L9}/.github` .github/pull_request_template.md,
# filled by the Cursor-Governance composer (ops/scripts/compose_pr_body.py).
# The template lists every file the PR touches first (## Files touched). This
# repository keeps no local PR template and no local body builder: a second
# template here would diverge from the one governance publishes with.
#
# Usage:
#   compose_pr_body.sh check   BASE                     prove the template is readable
#   compose_pr_body.sh title   BASE                     print the PR title
#   compose_pr_body.sh body    BASE                     print the PR body
#   compose_pr_body.sh refresh BASE BODY_FILE STATUS    recompose machine-owned regions
#
# `.l9/pr/pr-intent.json` (schema l9.pr_intent.v1: head, title, problem,
# reviewer_focus) supplies the prose when its `head` names HEAD.
set -euo pipefail

refuse() {
  echo "refusing to compose the PR body: $*" >&2
  exit 1
}

MODE="${1:?mode: check|title|body|refresh}"
BASE="${2:?base branch}"
BASE="${BASE#origin/}"
ROOT="$(git rev-parse --show-toplevel)"

resolver="${HOME}/.cursor-governance/ops/scripts/resolve_governance_paths.sh"
[[ -f "${resolver}" ]] || refuse "no governance resolver at \$HOME/.cursor-governance (the composer lives there)"
# shellcheck disable=SC1090
source "${resolver}"
resolve_governance_paths || refuse "governance paths did not resolve"
composer="${GOV_ROOT}/ops/scripts/compose_pr_body.py"
[[ -f "${composer}" ]] || refuse "composer missing: ${composer}"
py="${GOV_ROOT}/.venv/bin/python"
[[ -x "${py}" ]] || py="python3"

args=(--workspace "${ROOT}" --pr-base "origin/${BASE}"
  --org-owner "${PR_TEMPLATE_OWNER:-Quantum-L9}" --repo-name "IB-Odoo_19")
intent="${ROOT}/.l9/pr/pr-intent.json"
[[ -f "${intent}" ]] && args+=(--intent-file "${intent}")

# Protected-root: an empty list in the body is a written claim, so only a
# measured range may say "none". Unmeasurable -> the composer says so.
additive_args() {
  local validator="${GOV_ROOT}/ops/scripts/validate_root_file_protection.py"
  local touched
  if [[ ! -f "${ROOT}/ops/config/root-file-protection.json" || ! -f "${validator}" ]]; then
    return 0
  fi
  mkdir -p "${ROOT}/.l9/pr"
  if touched="$("${py}" "${validator}" --list-touched-additive-only \
      --base "origin/${BASE}" --head HEAD --repo "${ROOT}" 2>/dev/null)"; then
    if [[ -n "${touched}" ]]; then
      printf '%s\n' "${touched}" > "${ROOT}/.l9/pr/additive-only.txt"
      args+=(--additive-only-file "${ROOT}/.l9/pr/additive-only.txt")
    fi
  else
    args+=(--additive-only-unmeasured)
  fi
}

case "${MODE}" in
  check)
    exec "${py}" "${composer}" "${args[@]}" --check-template
    ;;
  title)
    exec "${py}" "${composer}" "${args[@]}" --print-title
    ;;
  body)
    additive_args
    body="$("${py}" "${composer}" "${args[@]}")"
    if [[ "${BASE}" == "Staging" ]]; then
      printf '%s\n' "${body}"
      exit 0
    fi
    # A stacked PR merges after its parent. Say so right under the file list,
    # outside every machine-owned region, so a refresh keeps it.
    STACK_NOTE="Stacked on \`${BASE}\`; merge that branch's pull request into Staging first." \
      python3 -c '
import os, sys
body, note = sys.stdin.read(), os.environ["STACK_NOTE"]
end = "<!-- FILES-TOUCHED:END -->"
if end in body:
    head, tail = body.split(end, 1)
    sys.stdout.write(f"{head}{end}\n\n{note}\n{tail}")
else:
    sys.stdout.write(f"{note}\n\n{body}")
' <<<"${body}"
    ;;
  refresh)
    body_file="${3:?body file}"
    status_file="${4:?status file}"
    additive_args
    exec "${py}" "${composer}" "${args[@]}" --refresh-body "${body_file}" --status-file "${status_file}"
    ;;
  *)
    refuse "unknown mode ${MODE}"
    ;;
esac
