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
#           pure-Python tests + local Odoo install-smoke (when its load inputs
#           changed) + remote PR feedback (when available) (make pr-check)
#
# Env:
#   PR_CHECK_JOBS=N           parallel make jobs (default: 4)
#   PR_CHECK_SKIP_REMOTE=1    skip GitHub/Sonar/review sync
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
    log " make pr-check — full local pre-push gate (parallel waves)"
    log " GitHub CI remains authoritative (gate-sdk-tests, secret-scan run there)"
    log "════════════════════════════════════════════════════"
    # Wave 1: local counterparts of ci.yml's static/baseline/pytest collectors.
    run_wave audit audit-baseline test
    # Wave 2: local Odoo load (not in GHA). Cached when plasticos/load inputs unchanged.
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
