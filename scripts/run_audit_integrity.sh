#!/usr/bin/env bash
# Parallel post-static integrity scanners (used by `make audit`).
# Fail-closed: any non-zero child fails the wave.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

run_bg() {
  local label="$1"
  shift
  (
    echo "→ ${label}..."
    "$@"
  ) &
  pids+=("$!")
  labels+=("${label}")
}

pids=()
labels=()

run_bg "Field integrity" python3 ci/check_field_integrity.py
run_bg "ORM integrity" python3 ci/check_orm_integrity.py
run_bg "Orphan model refs" python3 ci/check_orphan_model_refs.py
run_bg "Automation field refs" python3 ci/check_automation_field_refs.py
run_bg "XPath stability" python3 ci/check_xpath_stability.py
run_bg "Constraint patterns" python3 ci/check_constraint_patterns.py
run_bg "Model inheritance" python3 ci/check_model_inheritance.py
run_bg "Disabled actions" python3 ci/check_disabled_actions.py

fail=0
for i in "${!pids[@]}"; do
  if ! wait "${pids[$i]}"; then
    echo "❌ ${labels[$i]} failed" >&2
    fail=1
  fi
done
exit "${fail}"
