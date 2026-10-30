#!/usr/bin/env bash
# Parallel LOCAL pre-push gate, scheduled in waves.
#
# This is not the GitHub CI job graph. GitHub CI (ci.yml) stays authoritative and
# runs lanes this script does not reproduce (gate-sdk-tests against the pinned
# SDK, gitleaks secret-scan). Secrets are scanned locally by the pre-commit
# gitleaks-push hook at `git push` time, not here.
#
# Modes:
#   fast  — audit-quick + pytest (local iteration only; not publication)
#   full  — local blocking static audit (make audit) + audit baseline +
#           pure-Python tests + remote PR feedback (when available) (make pr-check)
#
# full runs only what the branch changed can reach. scripts/pr_check_scope.py
# compares the branch with origin/$PR_BASE (committed range, working tree,
# untracked files) and decides: the static audits run when any non-documentation
# path changed; pytest runs only the test modules touched by, or reading, the
# changed paths (the whole suite when the harness changed). The full Docker
# install is optional. INSTALL_SMOKE_GATE=1 restores it for an addon load
# input or an installer input. Every doubt keeps the audit and pytest gate.
# GitHub ci.yml still runs everything on the PR.
#
# Env:
#   PR_BASE=<branch>          publication base (default: Staging)
#   PR_CHECK_SCOPE=full       run the whole gate regardless of what changed
#   PR_CHECK_JOBS=N           parallel make jobs (default: 4)
#   PR_CHECK_SKIP_REMOTE=1    skip GitHub/Sonar/review sync
#   INSTALL_SMOKE_GATE=1      restore the full install as a gate (default: off)
#   PR_CHECK_SKIP_SMOKE=1     skip Docker install-smoke
#   PR_CHECK_FORCE_SMOKE=1    ignore install-smoke evidence and install again
#   PR_CHECK_SMOKE_CACHE=0    disable evidence reuse (always install when not skipped)
#
# Usage:
#   scripts/pr_check_run.sh fast
#   scripts/pr_check_run.sh full
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MODE="${1:-full}"
JOBS="${PR_CHECK_JOBS:-4}"
MAKE="${MAKE:-make}"

log() { printf '%s\n' "$*"; }

run_wave() {
  # Run independent make targets in one -j wave; fail if any fails.
  local -a targets=("$@")
  if [ "${#targets[@]}" -eq 0 ]; then
    return 0
  fi
  log "→ Wave (${#targets[@]} targets, -j${JOBS}): ${targets[*]}"
  # GNU/BSD make: building multiple goals with -j runs their graphs concurrently.
  "${MAKE}" -j"${JOBS}" --no-print-directory "${targets[@]}"
}

# Remember the skip, then drop it before pytest. Publication tests copy the
# environment and refuse a publish when either switch is still set.
SMOKE_SKIP=0
_bypass="${PR_SMOKE_BYPASS:-}"
_bypass="${_bypass// /}"
if [ "${PR_CHECK_SKIP_SMOKE:-0}" = "1" ] || [ -n "${_bypass}" ]; then
  SMOKE_SKIP=1
fi
unset _bypass
unset PR_CHECK_SKIP_SMOKE PR_SMOKE_BYPASS

maybe_install_smoke() {
  if [ "${SMOKE_SKIP}" = "1" ]; then
    log "→ install-smoke skipped"
    return 0
  fi
  if [ "${INSTALL_SMOKE_GATE:-0}" != "1" ]; then
    log "→ full install-smoke is optional (INSTALL_SMOKE_GATE=1 restores the gate)"
    return 0
  fi

  local use_cache="${PR_CHECK_SMOKE_CACHE:-1}"
  local force="${PR_CHECK_FORCE_SMOKE:-0}"
  local rc

  if [ "$force" != "1" ] && [ "$use_cache" = "1" ]; then
    set +e
    bash "$ROOT/scripts/install_smoke.sh" --recheck
    rc=$?
    set -e
    if [ "$rc" -eq 0 ]; then
      log "→ install-smoke evidence matches the live image, modules, and database"
      return 0
    fi
    if [ "$rc" -eq 2 ]; then
      log "→ install-smoke recheck refused"
      return 2
    fi
    log "→ install-smoke evidence miss; running a fresh install"
  fi

  "${MAKE}" --no-print-directory install-smoke
}

maybe_remote() {
  if [ "${PR_CHECK_SKIP_REMOTE:-0}" = "1" ]; then
    log "→ Remote PR feedback skipped (PR_CHECK_SKIP_REMOTE=1)"
    return 0
  fi
  "${MAKE}" --no-print-directory pr-remote-feedback
}

case "$MODE" in
  fast | pr)
    log "════════════════════════════════════════════════════"
    log " fast local gate (audit-quick + test)"
    log " This is not publication. Validation: make pr-check. Publish: make pr."
    log "════════════════════════════════════════════════════"
    run_wave audit-quick test
    log ""
    log "✅ Fast local gate passed — this is not publication"
    ;;
  full | pr-check)
    log "════════════════════════════════════════════════════"
    log " make pr-check — local pre-push gate scoped to the changed files (parallel waves)"
    log " GitHub CI remains authoritative (gate-sdk-tests, secret-scan run there)"
    log "════════════════════════════════════════════════════"
    # One scope decision for the whole gate; the receipt is read again by
    # scripts/git_push_with_pr.sh for the post-gate smoke recheck. A stale
    # receipt never survives into this run.
    rm -f "$ROOT/.cache/pr-check/scope.json"
    scope="$(python3 "$ROOT/scripts/pr_check_scope.py" --base "${PR_BASE:-Staging}" --receipt "$ROOT/.cache/pr-check/scope.json")" \
      || scope=$'audit=1\nsmoke=1\ntests=all\nreason=scope owner failed; whole gate'
    scope_audit="$(printf '%s\n' "$scope" | sed -n 's/^audit=//p')"
    scope_smoke="$(printf '%s\n' "$scope" | sed -n 's/^smoke=//p')"
    scope_tests="$(printf '%s\n' "$scope" | sed -n 's/^tests=//p')"
    log "scope: $(printf '%s\n' "$scope" | sed -n 's/^reason=//p')"
    # Wave 1: local counterparts of ci.yml's static/baseline/pytest collectors.
    targets=()
    if [ "$scope_audit" != "0" ]; then targets+=(audit audit-baseline); else log "→ audits skipped: only documentation changed"; fi
    case "$scope_tests" in
      all) targets+=(test) ;;
      "") log "→ pytest skipped: no test module is touched by or reads the changed paths" ;;
      *) export TEST_PATHS="$scope_tests"; targets+=(test-scoped) ;;
    esac
    # Bash 3.2 (macOS /bin/bash) treats "${targets[@]}" as unbound under
    # set -u when the array is empty. A documentation-only scope leaves it
    # empty: both collectors are skipped, and that is a successful gate.
    if [ "$scope_audit" = "0" ] && [ -z "$scope_tests" ]; then
      log "→ no local collector: documentation-only change"
    fi
    if [ "${#targets[@]}" -gt 0 ]; then
      run_wave "${targets[@]}"
    fi
    # Wave 2: local Odoo load (not in GHA), only when an addon or installer input changed.
    if [ "$scope_smoke" = "0" ]; then
      SMOKE_SKIP=1
      log "→ install-smoke not needed: no addon load input or installer input changed"
    fi
    maybe_install_smoke
    # Wave 3: remote signals when a PR/token exists.
    maybe_remote
    log ""
    log "✅ Local pre-push gate passed — GitHub CI is the merge verdict"
    ;;
  *)
    log "Usage: $0 {fast|full}" >&2
    exit 2
    ;;
esac
