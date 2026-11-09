#!/usr/bin/env bash
# Stacked publication base. `name` refuses a protected destination before any
# network call. `prove` walks at most two open parent PRs and requires that
# walk to end at Staging. The new pull request is the third. Callers export
# GH_REPO before `prove`. HEAD must contain the immediate parent.
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
  local branch hop raw next seen
  if [[ "${base}" == "Staging" ]]; then
    return 0
  fi
  if [[ -z "${GH_REPO:-}" ]]; then
    refuse "GH_REPO is not set"
  fi
  branch="${base}"
  seen="${base}"
  for hop in 1 2; do
    raw="$(gh api --method GET "repos/${GH_REPO}/pulls" -f state=open -f head="${GH_REPO%%/*}:${branch}")" \
      || refuse "cannot look up the parent pull request for ${branch}"
    if ! next="$(python3 - "${raw}" "${GH_REPO}" "${branch}" "${hop}" "${seen}" <<'PY'
import json
import sys

raw, repo, branch, hop_text, seen_csv = sys.argv[1:]
hop = int(hop_text)
seen = {part for part in seen_csv.split(",") if part}
try:
    items = json.loads(raw)
except ValueError:
    print("pull request lookup returned malformed JSON")
    sys.exit(1)
if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
    print("pull request lookup did not return a list of pull requests")
    sys.exit(1)
owner = repo.split("/")[0]
matched = []
for item in items:
    base_info = item.get("base") or {}
    head_info = item.get("head") or {}
    base_repo = (base_info.get("repo") or {}).get("full_name")
    head_repo = (head_info.get("repo") or {}).get("full_name")
    if base_repo != repo or head_repo != repo:
        print(f"pull request lookup returned a pull request outside {repo}")
        sys.exit(1)
    if head_info.get("ref") == branch or head_info.get("label") == f"{owner}:{branch}":
        matched.append(item)
if len(matched) != 1:
    if matched:
        print(f"stacked parent {branch} has more than one open PR")
    elif hop == 1:
        print(f"stacked parent {branch} has no open PR into Staging")
    else:
        print(f"stacked parent {branch} has no open PR")
    sys.exit(1)
base_ref = (matched[0].get("base") or {}).get("ref") or ""
if base_ref.lower() in {"production", "main"} or (base_ref.lower() == "staging" and base_ref != "Staging"):
    print(f"stacked parent chain reaches {base_ref}")
    sys.exit(1)
if base_ref == "Staging":
    print("Staging")
    sys.exit(0)
if not base_ref or base_ref in seen:
    print(f"stacked parent chain loops at {base_ref or branch}")
    sys.exit(1)
if hop >= 2:
    print("stacked parent chain does not reach Staging within three pull requests")
    sys.exit(1)
print(base_ref)
PY
)"; then
      refuse "${next}"
    fi
    if [[ "${next}" == "Staging" ]]; then
      break
    fi
    seen="${seen},${next}"
    branch="${next}"
  done
  git fetch origin "${base}" || refuse "git fetch origin/${base} failed"
  git merge-base --is-ancestor "origin/${base}" HEAD || refuse "HEAD does not contain origin/${base}"
}

case "${cmd}" in
  name) check_name ;;
  prove) check_prove ;;
  *) refuse "unknown pr_stack_parent command ${cmd}" ;;
esac
