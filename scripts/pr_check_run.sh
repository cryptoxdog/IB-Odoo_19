#!/usr/bin/env bash
# Parallel LOCAL pre-push gate, scheduled in waves and selected by change class.
#
# This is not the GitHub CI job graph. GitHub CI (ci.yml) stays authoritative and
# runs the full suite on every PR (lint, static-checks, pure-python-tests,
# gate-sdk-tests, audit-baseline, secret-scan). Secrets are scanned locally by
# the pre-commit gitleaks-push hook at `git push` time, not here. The Odoo
# install-smoke (`odoo-bin -i` of every PlasticOS module on the Enterprise base)
# runs on GitHub too, as the "Odoo Install Smoke" workflow on every pull request
# (.github/workflows/odoo-install-smoke.yml); `make install-smoke` remains the
# explicit local run for Docker-side debugging and is never part of this gate.
#
# Modes:
#   fast  — audit-quick + pytest (local iteration only; not publication)
#   full  — local pre-push gate (make pr-check), selected by the change class of
#           the branch against the publication base:
#             scope=full       any Odoo load-surface, installer or repo-tooling
#                              path changed (scripts/odoo_load_surface.py owns
#                              the load surface): make audit + audit-baseline +
#                              test, then remote feedback.
#             scope=docs_only  nothing the Odoo install or the repo tooling
#                              reads changed: audit-quick + ban-check, then
#                              remote feedback.
#           Classification fails closed: no base, no merge-base, a classifier
#           error or an empty change set all select scope=full.
#
# Env:
#   PR_BASE=<branch>            publication base (default: Staging)
#   PR_CHECK_SCOPE=full         force the full scope
#   PR_CHECK_JOBS=N             parallel make jobs (default: 4)
#   PR_CHECK_SKIP_REMOTE=1      skip GitHub/Sonar/review sync
#
# Receipts: .cache/pr-check/scope.json (scope, base, head, changed paths) and a
# per-phase elapsed-seconds line for every phase on stdout.
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
PR_BASE="${PR_BASE:-Staging}"
RECEIPT_DIR="$ROOT/.cache/pr-check"
SCOPE_RECEIPT="$RECEIPT_DIR/scope.json"
TOOLING_RE='^(.*\.py|.*\.sh|tests/.*|ci/.*|scripts/.*|tools/.*|Makefile|pyproject\.toml|\.pre-commit-config\.yaml|\.semgrep/.*|\.semgrepignore|\.gitleaks\.toml|\.github/.*|config/.*|requirements.*\.txt|constraints\.txt)$'

SCOPE="full"
SCOPE_REASON="default"
BASE_SHA=""
HEAD_SHA="$(git rev-parse HEAD 2>/dev/null || echo "")"
CHANGED_COUNT=0

log() { printf '%s\n' "$*"; }

PHASE_T=0
phase_start() { PHASE_T="$(date +%s)"; }
phase_end() { log "⏱ ${1}: $(( $(date +%s) - PHASE_T ))s"; }

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

write_scope_receipt() {
  local changed_json
  mkdir -p "$RECEIPT_DIR"
  changed_json="$(printf '%s\n' "${CHANGED_PATHS:-}" | python3 -c 'import json, sys; print(json.dumps([l for l in sys.stdin.read().split("\n") if l]))')"
  python3 - "$SCOPE_RECEIPT" "$SCOPE" "$SCOPE_REASON" "$PR_BASE" "$BASE_SHA" "$HEAD_SHA" "$changed_json" <<'PY'
import json
import sys
from pathlib import Path

path, scope, reason, base, base_sha, head_sha, changed = sys.argv[1:]
Path(path).write_text(
    json.dumps(
        {
            "schema": "l9.pr-check-scope.v1",
            "scope": scope,
            "reason": reason,
            "base": base,
            "base_sha": base_sha,
            "head_sha": head_sha,
            "changed_count": len(json.loads(changed)),
            "changed": json.loads(changed),
        },
        indent=2,
    )
    + "\n"
)
PY
}

classify_scope() {
  # Decide between scope=full and scope=docs_only from the paths that differ
  # from the publication base (committed range, working tree and untracked
  # files). Anything the Odoo install or the repository tooling reads forces
  # full; so does every failure to classify.
  local mb rc classified
  CHANGED_PATHS=""
  if [ "${PR_CHECK_SCOPE:-}" = "full" ]; then
    SCOPE="full"; SCOPE_REASON="forced by PR_CHECK_SCOPE=full"
    return 0
  fi
  if ! git fetch -q origin "$PR_BASE" 2>/dev/null; then
    SCOPE="full"; SCOPE_REASON="cannot fetch origin/${PR_BASE}"
    return 0
  fi
  if ! mb="$(git merge-base "origin/${PR_BASE}" HEAD 2>/dev/null)"; then
    SCOPE="full"; SCOPE_REASON="no merge-base with origin/${PR_BASE}"
    return 0
  fi
  BASE_SHA="$mb"
  CHANGED_PATHS="$(
    {
      git diff --name-only "${mb}..HEAD"
      git diff --name-only HEAD
      git ls-files --others --exclude-standard
    } | sort -u
  )"
  CHANGED_COUNT="$(printf '%s\n' "$CHANGED_PATHS" | grep -c . || true)"
  if [ "$CHANGED_COUNT" -eq 0 ]; then
    SCOPE="full"; SCOPE_REASON="no change against origin/${PR_BASE}@${mb:0:12}"
    return 0
  fi
  if printf '%s\n' "$CHANGED_PATHS" | grep -E -q "$TOOLING_RE"; then
    SCOPE="full"; SCOPE_REASON="repository tooling or Python changed"
    return 0
  fi
  set +e
  # shellcheck disable=SC2086
  classified="$(printf '%s\n' "$CHANGED_PATHS" | xargs -d '\n' python3 "$ROOT/scripts/odoo_load_surface.py" --root "$ROOT" --classify 2>&1)"
  rc=$?
  set -e
  case "$rc" in
    0) SCOPE="docs_only"; SCOPE_REASON="${CHANGED_COUNT} changed, 0 load-surface/installer/tooling paths" ;;
    3) SCOPE="full"; SCOPE_REASON="Odoo load surface or installer input changed" ;;
    *) SCOPE="full"; SCOPE_REASON="load-surface classifier failed (exit ${rc}): ${classified%%$'\n'*}" ;;
  esac
}

maybe_remote() {
  if [ "${PR_CHECK_SKIP_REMOTE:-0}" = "1" ]; then
    log "→ Remote PR feedback skipped (PR_CHECK_SKIP_REMOTE=1)"
    return 0
  fi
  "${MAKE}" --no-print-directory pr-remote-feedback
}

run_full_scope() {
  # Local counterparts of ci.yml's static/baseline/pytest collectors. The Odoo
  # load itself is proven by the "Odoo Install Smoke" workflow on the PR.
  phase_start
  run_wave audit audit-baseline test
  phase_end "wave1 (audit + audit-baseline + test)"
}

run_docs_only_scope() {
  # Lint, format, XML and wiring on the whole tree are seconds; the heavy
  # collectors (semgrep, audit-baseline, pytest) run in CI on the PR and read
  # nothing this change touched.
  phase_start
  run_wave audit-quick ban-check
  phase_end "wave1 (audit-quick + ban-check)"
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
    log " make pr-check — local pre-push gate (change-class scoped, parallel waves)"
    log " GitHub CI remains authoritative (full suite + Odoo install smoke run on the PR)"
    log "════════════════════════════════════════════════════"
    phase_start
    classify_scope
    write_scope_receipt
    log "scope=${SCOPE} reason=${SCOPE_REASON} base=origin/${PR_BASE}${BASE_SHA:+@${BASE_SHA:0:12}} changed=${CHANGED_COUNT}"
    phase_end "classify"
    if [ "$SCOPE" = "docs_only" ]; then
      run_docs_only_scope
    else
      run_full_scope
    fi
    phase_start
    maybe_remote
    phase_end "remote feedback"
    log ""
    log "✅ Local pre-push gate passed (scope=${SCOPE}) — GitHub CI is the merge verdict"
    ;;
  *)
    log "Usage: $0 {fast|full}" >&2
    exit 2
    ;;
esac
