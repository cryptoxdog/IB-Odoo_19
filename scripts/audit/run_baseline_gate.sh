#!/usr/bin/env bash
# Fail-slow collection, fail-closed verdict for the two audit baselines.
#
# Both scanners always run. A scanner exit of 1 that still produced a fresh
# findings list is classified by check_baseline.py (known baseline entries
# stay green). A crash, a missing report, a malformed report, or a preexisting
# report is not a pass. Makefile and ci.yml both call this script so the
# verdict cannot drift.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 1

run_one() {
  local report="$1"
  local scanner="$2"
  local baseline="$3"
  local severities="$4"
  local label="$5"
  local stamp rc check
  rm -f "$report"
  stamp="$(mktemp)"
  python3 -c 'import time; time.sleep(0.05)'
  set +e
  python3 "$scanner" .
  rc=$?
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    python3 "$ROOT/scripts/audit/check_baseline.py" \
      "$report" "$baseline" \
      --severities "$severities" \
      --label "$label" \
      --scanner-rc "$rc" \
      --newer-than "$stamp" \
      --summary-file "$GITHUB_STEP_SUMMARY"
  else
    python3 "$ROOT/scripts/audit/check_baseline.py" \
      "$report" "$baseline" \
      --severities "$severities" \
      --label "$label" \
      --scanner-rc "$rc" \
      --newer-than "$stamp"
  fi
  check=$?
  rm -f "$stamp"
  return "$check"
}

echo "→ Comprehensive audit vs ci/baselines/odoo_audit_baseline.json"
run_one \
  odoo_audit_report.json \
  "$ROOT/scripts/audit/odoo_audit.py" \
  "$ROOT/ci/baselines/odoo_audit_baseline.json" \
  "CRITICAL,HIGH" \
  "Comprehensive audit"
comprehensive=$?

echo "→ Extended audit vs ci/baselines/extended_audit_baseline.json"
run_one \
  extended_audit_report.json \
  "$ROOT/scripts/audit/run_all_audits.py" \
  "$ROOT/ci/baselines/extended_audit_baseline.json" \
  "HIGH" \
  "Extended audit"
extended=$?

if [ "$comprehensive" -ne 0 ] || [ "$extended" -ne 0 ]; then
  echo "❌ Audit baseline verdict failed (comprehensive=${comprehensive} extended=${extended})" >&2
  exit 1
fi
echo "✅ No audit baseline regression"
