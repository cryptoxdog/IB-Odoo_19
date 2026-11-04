#!/usr/bin/env bash
# Pre-push gate. Run by .pre-commit-config.yaml at the pre-push stage:
#   gitleaks-push -> pre_push_validate.sh gitleaks   (full secret scan)
#   pr-validate   -> pre_push_validate.sh gate       (make pr-check)
#
# make pr (scripts/git_push_with_pr.sh) owns an unconditional gate that runs
# before every push attempt, including retries where git has nothing new to
# push and pre-commit runs no hook. It sets L9_PUBLISH_VALIDATED_SHA and
# L9_PUBLISH_TARGET on its own `git push` only, after that gate passed. This
# hook skips its duplicate work only when that binding names exactly this
# push (the pushed SHA, HEAD, a clean tree, remote origin, refs/heads/<target>)
# AND the hook runs under scripts/git_push_with_pr.sh. Any other push,
# including a direct `git push` that sets the variables itself, runs the full
# gate here.
#
# Push forms (pre-commit 4.7.0, see tests/test_publication_real_push.py):
#   update / new branch with new commits   validated here
#   up-to-date, or a new ref to a commit the remote already has
#                                          pre-commit runs no hook; nothing new
#                                          reaches the remote
#   branch deletion                        no hook; no content
#   several refs in one push               pre-commit binds the first new ref
#                                          only; hooks cannot see the others
#   root of history (all-files mode)       refused below
#
# Threat model: this stops accidental, stale and env-forged bypass. A
# deliberate local actor can still skip hooks with --no-verify (governed for
# agents) or by disguising a process as the publisher; ci.yml is the merge gate.
set -euo pipefail

refuse() {
  echo "pre-push refused: $*" >&2
  exit 1
}

mode="${1:-}"
case "${mode}" in
  gitleaks | gate) ;;
  *) refuse "usage: pre_push_validate.sh gitleaks|gate" ;;
esac

to_ref="${PRE_COMMIT_TO_REF:-}"
if [[ -z "${to_ref}" ]]; then
  if [[ -n "${PRE_COMMIT_REMOTE_NAME:-}" ]]; then
    refuse "a push that includes the root of history is not supported (pre-commit gives no pushed SHA)"
  fi
  refuse "PRE_COMMIT_TO_REF is unset; this gate runs only as a pre-push hook"
fi

head="$(git rev-parse HEAD)"
if [[ "${to_ref}" != "${head}" ]]; then
  refuse "pushed commit ${to_ref} is not the checked-out HEAD ${head}; check out the commit you push"
fi
if [[ -n "$(git status --porcelain)" ]]; then
  refuse "working tree, index, or untracked files are not clean"
fi

# The binding variables alone are not evidence: anyone can set them on a plain
# `git push`. They are honoured only when this hook descends from the publisher,
# scripts/git_push_with_pr.sh, which runs the full gate before every push. A
# process that cannot be inspected fails closed (the full gate runs). The
# publisher must be the program itself (argv[0]) or the script its interpreter
# runs (argv[1]); a process that merely names the path in an argument (an
# editor, `grep`, `bash -c "..."`) does not count.
launched_by_publisher() {
  local pid="${PPID}" args _ field
  local -a argv
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    [[ "${pid}" =~ ^[0-9]+$ ]] && ((pid > 1)) || return 1
    argv=()
    if [[ -r "/proc/${pid}/cmdline" ]]; then
      mapfile -d '' -t argv < "/proc/${pid}/cmdline"
      pid="$(awk '/^PPid:/ {print $2}' "/proc/${pid}/status" 2> /dev/null)"
    else
      args="$(ps -o args= -p "${pid}" 2> /dev/null)" || return 1
      read -r -a argv <<< "${args}"
      pid="$(ps -o ppid= -p "${pid}" 2> /dev/null | tr -d ' ')"
    fi
    for field in "${argv[@]:0:2}"; do
      [[ "${field}" == "scripts/git_push_with_pr.sh" || "${field}" == */scripts/git_push_with_pr.sh ]] && return 0
    done
  done
  return 1
}

publisher_validated() {
  [[ -n "${L9_PUBLISH_VALIDATED_SHA:-}" && -n "${L9_PUBLISH_TARGET:-}" ]] || return 1
  [[ "${L9_PUBLISH_VALIDATED_SHA}" == "${to_ref}" ]] || return 1
  [[ "${PRE_COMMIT_REMOTE_NAME:-}" == "origin" ]] || return 1
  [[ "${PRE_COMMIT_REMOTE_BRANCH:-}" == "refs/heads/${L9_PUBLISH_TARGET}" ]] || return 1
  launched_by_publisher
}

if publisher_validated; then
  echo "pre-push ${mode}: validated by make pr in this process (${to_ref} -> origin/${L9_PUBLISH_TARGET})"
  exit 0
fi
if [[ -n "${L9_PUBLISH_VALIDATED_SHA:-}${L9_PUBLISH_TARGET:-}" ]]; then
  echo "pre-push ${mode}: publisher binding does not match this push; running the full gate" >&2
fi

case "${mode}" in
  gitleaks)
    if ! command -v gitleaks >/dev/null 2>&1; then
      refuse "gitleaks is not on PATH"
    fi
    if ! gitleaks detect --config .gitleaks.toml --redact --exit-code 2; then
      refuse "gitleaks detect failed"
    fi
    ;;
  gate)
    bypass="${PR_SMOKE_BYPASS:-}"
    if [[ -n "${bypass// /}" ]]; then
      refuse "PR_SMOKE_BYPASS applies only to make pr-nosmoke, not to a direct push"
    fi
    # Git runs hooks with GIT_DIR and other repo-local variables set (GIT_DIR is
    # absolute in a linked worktree). make pr-check runs test fixtures that call
    # git in their own temporary repositories; inherited, these variables point
    # those calls at this repository (2026-11-03: fixtures committed onto the
    # branch and set core.bare). Clear them; git finds this repo from the cwd.
    while IFS= read -r git_var; do
      unset "${git_var}"
    done < <(git rev-parse --local-env-vars)
    if ! make pr-check; then
      refuse "make pr-check failed"
    fi
    if [[ "$(git rev-parse HEAD)" != "${to_ref}" ]] || [[ -n "$(git status --porcelain)" ]]; then
      refuse "HEAD or the worktree changed during validation"
    fi
    ;;
esac
