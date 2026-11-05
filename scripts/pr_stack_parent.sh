#!/usr/bin/env bash
# Stacked publication base. `name` refuses a protected destination before any
# network call. `prove` requires exactly one open parent PR into Staging and
# a HEAD that contains that branch. Callers export GH_REPO before `prove`.
# Usage: pr_stack_parent.sh name <base>
#        pr_stack_parent.sh prove <base>
set -euo pipefail

refuse() {
  echo "refusing to publish: $*" >&2
  exit 1
}

cmd="${1:-}"
base="${2:-}"
if [[ -z "${cmd}" || -z "${base}" ]]; then
  refuse "usage: pr_stack_parent.sh name|prove <base>"
fi

check_name() {
  if [[ "${base}" == "Staging" ]]; then
    return 0
  fi
  local base_lc
  base_lc="$(printf '%s' "${base}" | tr '[:upper:]' '[:lower:]')"
  case "${base_lc}" in
    staging|production|main)
      refuse "destination must be Staging or a stacked parent branch (got ${base})"
      ;;
  esac
}

check_prove() {
  local owner raw reason
  if [[ "${base}" == "Staging" ]]; then
    return 0
  fi
  if [[ -z "${GH_REPO:-}" ]]; then
    refuse "GH_REPO is not set"
  fi
  owner="${GH_REPO%%/*}"
  raw="$(gh api --method GET "repos/${GH_REPO}/pulls" -f state=open -f base=Staging -f head="${owner}:${base}")" \
    || refuse "cannot look up the parent pull request for ${base}"
  if ! reason="$(python3 - "${raw}" "${GH_REPO}" "${base}" <<'PY'
import json
import sys

raw, repo, base = sys.argv[1:]
try:
    items = json.loads(raw)
except ValueError:
    print("pull request lookup returned malformed JSON")
    sys.exit(1)
if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
    print("pull request lookup did not return a list of pull requests")
    sys.exit(1)
for item in items:
    full_name = ((item.get("base") or {}).get("repo") or {}).get("full_name")
    if full_name != repo:
        print(f"pull request lookup returned a pull request outside {repo}")
        sys.exit(1)
if len(items) != 1:
    if items:
        print(f"stacked parent {base} has more than one open PR into Staging")
    else:
        print(f"stacked parent {base} has no open PR into Staging")
    sys.exit(1)
PY
)"; then
    refuse "${reason}"
  fi
  git fetch origin "${base}" || refuse "git fetch origin/${base} failed"
  git merge-base --is-ancestor "origin/${base}" HEAD || refuse "HEAD does not contain origin/${base}"
}

case "${cmd}" in
  name) check_name ;;
  prove) check_prove ;;
  *) refuse "unknown pr_stack_parent command ${cmd}" ;;
esac
