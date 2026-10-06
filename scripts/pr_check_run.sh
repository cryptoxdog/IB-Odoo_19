#!/usr/bin/env bash
# Parallel LOCAL pre-push gate, scheduled in waves.
#
# This is not the GitHub CI job graph. GitHub CI (ci.yml) stays authoritative and
# runs lanes this script does not reproduce (gate-sdk-tests against the pinned
# SDK, gitleaks secret-scan). Secrets are scanned locally by the pre-commit
# gitleaks-push hook at `git push` time, not here.
#
# Modes:
#   fast  — audit-quick + pytest (local iteration; make pr)
#   full  — local blocking static audit (make audit) + audit baseline +
#           pure-Python tests + local Odoo install-smoke (when its load inputs
#           changed) + remote PR feedback (when available) (make pr-check / push)
#
# Env:
#   PR_CHECK_JOBS=N           parallel make jobs (default: 4)
#   PR_CHECK_SKIP_REMOTE=1    skip GitHub/Sonar/review sync
#   PR_CHECK_SKIP_SMOKE=1     skip Docker install-smoke
#   PR_CHECK_FORCE_SMOKE=1    ignore install-smoke content cache
#   PR_CHECK_SMOKE_CACHE=0    disable smoke cache (always run when not skipped)
#
# Usage:
#   scripts/pr_check_run.sh fast
#   scripts/pr_check_run.sh full
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MODE="${1:-full}"
JOBS="${PR_CHECK_JOBS:-4}"
CACHE_DIR="${ROOT}/.cache/pr-check"
SMOKE_CACHE="${CACHE_DIR}/install-smoke.sha"
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

smoke_fingerprint() {
  # Content hash of load-bearing paths for install-smoke. Docs/tests-only edits miss.
  python3 - <<'PY'
import hashlib
from pathlib import Path

root = Path(".")
paths: list[Path] = []

for mod in sorted(root.glob("plasticos_*")):
    if not mod.is_dir():
        continue
    for pat in ("**/*.py", "**/*.xml", "**/*.csv", "**/*.yml", "**/*.yaml"):
        paths.extend(p for p in mod.glob(pat) if p.is_file())

for rel in (
    "config/odoo_module_order.yaml",
    "requirements.txt",
    "constraints.txt",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
    "scripts/install_smoke.sh",
    "scripts/get_odoo_module_order.py",
):
    p = root / rel
    if p.is_file():
        paths.append(p)

h = hashlib.sha256()
for p in sorted(set(paths), key=lambda x: str(x)):
    h.update(str(p).encode())
    h.update(b"\0")
    h.update(p.read_bytes())
    h.update(b"\0")
print(h.hexdigest())
PY
}

maybe_install_smoke() {
  if [ "${PR_CHECK_SKIP_SMOKE:-0}" = "1" ]; then
    log "→ install-smoke skipped (PR_CHECK_SKIP_SMOKE=1)"
    return 0
  fi

  local use_cache="${PR_CHECK_SMOKE_CACHE:-1}"
  local force="${PR_CHECK_FORCE_SMOKE:-0}"
  local fp

  if [ "$force" != "1" ] && [ "$use_cache" = "1" ]; then
    fp="$(smoke_fingerprint)"
    if [ -f "$SMOKE_CACHE" ] && [ "$(cat "$SMOKE_CACHE")" = "$fp" ]; then
      log "→ install-smoke skipped (unchanged load fingerprint — PR_CHECK_FORCE_SMOKE=1 to re-run)"
      return 0
    fi
  fi

  "${MAKE}" --no-print-directory install-smoke
  mkdir -p "$CACHE_DIR"
  smoke_fingerprint >"$SMOKE_CACHE"
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
    log " make pr — fast local gate (audit-quick + test)"
    log " Full pre-push gate: make pr-check"
    log "════════════════════════════════════════════════════"
    run_wave audit-quick test
    log ""
    log "✅ Fast PR gate passed — iterate freely; run make pr-check before push"
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
