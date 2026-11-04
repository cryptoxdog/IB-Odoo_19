#!/usr/bin/env bash
# Stacked publication base. `name` refuses a protected destination before any
# network call. `prove` follows the open PR of each parent branch down to
# Staging (one open PR per branch, at most five) and requires a HEAD that
# contains the named parent. Callers export GH_REPO before `prove`.
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
  local owner raw hop next seen depth
  if [[ "${base}" == "Staging" ]]; then
    return 0
  fi
  if [[ -z "${GH_REPO:-}" ]]; then
    refuse "GH_REPO is not set"
  fi
  owner="${GH_REPO%%/*}"
  hop="${base}"
  seen=" ${base} "
  for depth in 1 2 3 4 5; do
    raw="$(gh api --method GET "repos/${GH_REPO}/pulls" -f state=open -f head="${owner}:${hop}")" \
      || refuse "cannot look up the parent pull request for ${hop}"
    if ! next="$(python3 - "${raw}" "${GH_REPO}" "${hop}" <<'PY'
import json
import sys

raw, repo, hop = sys.argv[1:]
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
        print(f"stacked parent {hop} has more than one open PR")
    else:
        print(f"stacked parent {hop} has no open PR")
    sys.exit(1)
print((items[0].get("base") or {}).get("ref") or "")
PY
)"; then
      refuse "${next}"
    fi
    if [[ "${next}" == "Staging" ]]; then
      git fetch origin "${base}" || refuse "git fetch origin/${base} failed"
      git merge-base --is-ancestor "origin/${base}" HEAD || refuse "HEAD does not contain origin/${base}"
      return 0
    fi
    case "$(printf '%s' "${next}" | tr '[:upper:]' '[:lower:]')" in
      "" | staging | production | main) refuse "stack under ${base} reaches ${next:-an empty base}, not Staging" ;;
    esac
    case "${seen}" in
      *" ${next} "*) refuse "stack under ${base} loops at ${next}" ;;
    esac
    seen="${seen}${next} "
    hop="${next}"
  done
  refuse "stack under ${base} is deeper than ${depth} pull requests"
}

case "${cmd}" in
  name) check_name ;;
  prove) check_prove ;;
  *) refuse "unknown pr_stack_parent command ${cmd}" ;;
esac
