#!/usr/bin/env bash
# Staging → Production Promotion Rehearsal — full orchestrator.
#
# Usage:
#   bash tests/production-rehearsal/run.sh
#
# Evidence is written to:
#   tests/production-rehearsal/evidence/YYYY-MM-DD_HHMMSS/
# `evidence/latest` is repointed atomically once the verdict is written.
#
# Every gate writes exactly one receipt (gate-<n>.json, common.py). The
# verdict (verdict.json + verdict.txt) is written on success, on failure, on an
# early refusal and on SIGINT/SIGTERM. `set -e` is deliberately not used: every
# gate captures its own exit status so a failure is recorded, never lost.
#
# Prerequisites: see README.md.
# Spec + acceptance criteria: see SPEC.md.
# Named blockers: see expected/blockers.yaml.
set -uo pipefail
umask 077

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Locate the PlasticOS repo root ───────────────────────────────────────────
ROOT=""
candidate="$KIT_DIR"
for _ in 1 2 3 4 5 6 7 8; do
  if [ -f "${candidate}/Makefile" ] && [ -f "${candidate}/docker-compose.yml" ]; then
    ROOT="${candidate}"
    break
  fi
  candidate="$(dirname "${candidate}")"
done
if [ -z "${ROOT}" ]; then
  echo "❌ Cannot locate PlasticOS root (Makefile + docker-compose.yml not found above ${KIT_DIR})" >&2
  exit 2
fi
cd "${ROOT}" || exit 2

# shellcheck source=rehearsal_common.sh source-path=SCRIPTDIR
. "${KIT_DIR}/rehearsal_common.sh"

# ── Load .env.local / .env secrets (not printed) ────────────────────────────
for _envfile in "${ROOT}/.env.local" "${ROOT}/.env"; do
  if [ -f "${_envfile}" ]; then
    set -a
    # shellcheck source=/dev/null
    . "${_envfile}"
    set +a
  fi
done

# ── Create this run's evidence folder (never reuses one) ─────────────────────
RUN_TS="$(date -u +%Y-%m-%d_%H%M%S)"
RUN_STARTED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
EVIDENCE_ROOT="${KIT_DIR}/evidence"
EVIDENCE_DIR="${EVIDENCE_ROOT}/${RUN_TS}"
mkdir -p "${EVIDENCE_ROOT}"
if ! mkdir "${EVIDENCE_DIR}"; then
  echo "❌ Evidence folder ${EVIDENCE_DIR} already exists; refusing to overwrite a previous run." >&2
  exit 2
fi
export REHEARSAL_EVIDENCE_DIR="${EVIDENCE_DIR}" RUN_STARTED_UTC

echo "════════════════════════════════════════════════════════"
echo " Staging → Production Promotion Rehearsal"
echo " Run:      ${RUN_TS}"
echo " Evidence: ${EVIDENCE_DIR}"
echo "════════════════════════════════════════════════════════"

REHEARSAL_PORT="${REHEARSAL_PORT:-18069}"
CUTOVER_DB="odoo_test_cutover"
BRANCH=""
HEAD_SHA=""
ORIGIN_STAGING=""
PROD_SHA=""
CURRENT_GATE=0
RUN_FAILURES=""
FINALIZED=0

# gate_record <n> <STATE> <reason> [detail] [side_effects:0|1]
gate_record() {
  local n="$1" state="$2" reason="$3" detail="${4:-}" side="${5:-0}"
  if [ "${side}" = "1" ]; then
    rlib gate-write "${EVIDENCE_DIR}" "${n}" "${state}" "${reason}" --detail "${detail}" --side-effects
  else
    rlib gate-write "${EVIDENCE_DIR}" "${n}" "${state}" "${reason}" --detail "${detail}"
  fi
  case "${state}" in
    PASS) echo "  ✅ Gate ${n} PASSED${detail:+ — ${detail}}" ;;
    SKIPPED) echo "  ⏭  Gate ${n} SKIPPED: ${reason}" ;;
    BLOCKED) echo "  ⛔ Gate ${n} BLOCKED: ${reason}${detail:+ — ${detail}}" ;;
    *) echo "  ❌ Gate ${n} ${state}: ${reason}${detail:+ — ${detail}}" ;;
  esac
}

gate_state() {
  rlib gate-state "${EVIDENCE_DIR}" "$1"
}

# skip_from <first_gate> <reason> — SKIPPED for every later gate without a receipt.
skip_from() {
  local n="$1" reason="$2"
  while [ "${n}" -le 7 ]; do
    if [ "$(gate_state "${n}")" = "MISSING" ]; then
      gate_record "${n}" SKIPPED "${reason}"
    fi
    n=$((n + 1))
  done
}

add_run_failure() {
  RUN_FAILURES="${RUN_FAILURES} $1"
}

finalize_run() {
  [ "${FINALIZED}" = "1" ] && return 0
  FINALIZED=1
  local args="" item verdict
  # Evidence must not hold a credential value. Values are read from the
  # environment by name; a hit is redacted in place and fails the run.
  if ! rlib scan-secrets "${EVIDENCE_DIR}" \
    --env ERP_SQL_PASSWORD --env ODOO_WEB_LEAD_API_KEY --env VANILLASOFT_API_KEY \
    --env POSTGRES_PASSWORD --env PGPASSWORD; then
    add_run_failure "evidence-secret-redacted"
  fi
  for item in ${RUN_FAILURES}; do
    args="${args} --run-failure ${item}"
  done
  # shellcheck disable=SC2086  # run-failure codes are single tokens
  verdict="$(rlib finalize "${EVIDENCE_DIR}" --run-ts "${RUN_TS}" --staging-sha "${ORIGIN_STAGING}" \
    --production-sha "${PROD_SHA}" --head-sha "${HEAD_SHA}" --branch "${BRANCH}" ${args})" || verdict="failed"
  rlib link-latest "${EVIDENCE_ROOT}" "${EVIDENCE_DIR}" || echo "⚠️  evidence/latest was not repointed"
  echo ""
  echo "════════════════════════════════════════════════════════"
  cat "${EVIDENCE_DIR}/verdict.txt" 2>/dev/null || echo "verdict=${verdict}"
  if [ "${verdict}" = "ready" ]; then
    echo " ✅ VERDICT: ready — every gate passed at ${ORIGIN_STAGING}"
  else
    echo " ❌ VERDICT: ${verdict}"
  fi
  echo "════════════════════════════════════════════════════════"
  echo " Evidence: ${EVIDENCE_DIR}"
  [ "${verdict}" = "ready" ]
}

# shellcheck disable=SC2329  # invoked by trap
on_signal() {
  local sig="$1" code="$2"
  trap - INT TERM
  echo ""
  echo "⚠️  Interrupted by SIG${sig} during Gate ${CURRENT_GATE}"
  if [ "${CURRENT_GATE}" -ge 1 ] && [ "$(gate_state "${CURRENT_GATE}")" = "MISSING" ]; then
    gate_record "${CURRENT_GATE}" FAIL "interrupted-${sig}" "SIG${sig} before the gate finished" 1
  fi
  skip_from 1 "run-interrupted"
  add_run_failure "interrupted-${sig}"
  finalize_run
  exit "${code}"
}
# shellcheck disable=SC2329  # invoked by trap
on_exit() {
  local rc=$?
  if [ "${FINALIZED}" != "1" ]; then
    if [ "${CURRENT_GATE}" -ge 1 ] && [ "$(gate_state "${CURRENT_GATE}")" = "MISSING" ]; then
      gate_record "${CURRENT_GATE}" FAIL "aborted" "the orchestrator stopped (exit ${rc}) before the gate finished" 1
    fi
    skip_from 1 "run-aborted"
    add_run_failure "aborted"
    finalize_run
    exit 1
  fi
}
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM
trap on_exit EXIT

stop_run() {
  finalize_run
  exit 1
}

# ── Gate 1 — Revision identity (no side effects before it passes) ───────────
echo ""
echo "── Gate 1: Revision identity"
CURRENT_GATE=1
if ! git fetch --no-tags --quiet origin \
  "+refs/heads/Staging:refs/remotes/origin/Staging" \
  "+refs/heads/Production:refs/remotes/origin/Production" >"${EVIDENCE_DIR}/00-fetch.log" 2>&1; then
  gate_record 1 FAIL "remote-fetch-failed" "git fetch of Staging and Production failed; remote state is unproven"
  skip_from 2 "gate1-failed"
  stop_run
fi
BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo "(detached)")"
HEAD_SHA="$(git rev-parse --verify --quiet 'HEAD^{commit}' || true)"
ORIGIN_STAGING="$(git rev-parse --verify --quiet 'refs/remotes/origin/Staging^{commit}' || true)"
PROD_SHA="$(git rev-parse --verify --quiet 'refs/remotes/origin/Production^{commit}' || true)"
DIRTY_FILE="${EVIDENCE_DIR}/00-dirty.txt"
# Only the tracked `evidence/latest` pointer, which every run repoints, is
# exempt. Run folders are git-ignored; committed historical evidence counts.
if ! git status --porcelain=v1 --untracked-files=all -- . \
  ':(exclude)tests/production-rehearsal/evidence/latest' >"${DIRTY_FILE}" 2>&1; then
  echo "git status failed" >>"${DIRTY_FILE}"
  DIRTY_COUNT="unknown"
else
  DIRTY_COUNT="$(grep -c . "${DIRTY_FILE}" || true)"
fi
{
  echo "branch=${BRANCH}"
  echo "HEAD=${HEAD_SHA}"
  echo "origin/Staging=${ORIGIN_STAGING}"
  echo "origin/Production=${PROD_SHA}"
  echo "dirty_paths=${DIRTY_COUNT}"
} >"${EVIDENCE_DIR}/00-staging-sha.txt"
echo "  Branch: ${BRANCH}  HEAD: ${HEAD_SHA:-?}"
echo "  origin/Staging: ${ORIGIN_STAGING:-?}  origin/Production: ${PROD_SHA:-?}"

G1_REASON=""
if [ -z "${HEAD_SHA}" ] || [ -z "${ORIGIN_STAGING}" ] || [ -z "${PROD_SHA}" ]; then
  G1_REASON="ref-unresolved"
elif [ "${BRANCH}" != "Staging" ]; then
  G1_REASON="not-on-staging"
elif [ "${HEAD_SHA}" != "${ORIGIN_STAGING}" ]; then
  G1_REASON="head-not-origin-staging"
elif [ "${DIRTY_COUNT}" != "0" ]; then
  G1_REASON="worktree-dirty"
fi
if [ -n "${G1_REASON}" ]; then
  echo "match=FAIL" >>"${EVIDENCE_DIR}/00-staging-sha.txt"
  gate_record 1 FAIL "${G1_REASON}" "branch=${BRANCH} HEAD=${HEAD_SHA:-?} origin/Staging=${ORIGIN_STAGING:-?} dirty=${DIRTY_COUNT}"
  skip_from 2 "gate1-failed"
  stop_run
fi
echo "match=PASS" >>"${EVIDENCE_DIR}/00-staging-sha.txt"
gate_record 1 PASS "revision-bound" "Staging ${ORIGIN_STAGING}"
echo "origin/Production=${PROD_SHA}" >"${EVIDENCE_DIR}/01-production-sha.txt"

# ── Gate 2 — Merge-tree (read-only) ─────────────────────────────────────────
echo ""
echo "── Gate 2: Merge-tree (read-only)"
CURRENT_GATE=2
MT_OUT="$(git merge-tree --write-tree --name-only --messages "${PROD_SHA}" "${ORIGIN_STAGING}" 2>&1)"
MT_RC=$?
MT_TREE="$(printf '%s\n' "${MT_OUT}" | head -1)"
MT_MARKERS="$(printf '%s\n' "${MT_OUT}" | grep -c '^<<<<<<<' || true)"
{
  echo "origin/Production=${PROD_SHA}"
  echo "origin/Staging=${ORIGIN_STAGING}"
  echo "exit_code=${MT_RC}"
  echo "conflict_markers=${MT_MARKERS}"
  echo "---"
  printf '%s\n' "${MT_OUT}"
} >"${EVIDENCE_DIR}/02-merge-tree.txt"
if [ "${MT_RC}" -eq 0 ] && printf '%s' "${MT_TREE}" | grep -Eq '^[0-9a-f]{40}([0-9a-f]{24})?$' \
  && [ "${MT_MARKERS}" = "0" ]; then
  echo "result=CLEAN" >>"${EVIDENCE_DIR}/02-merge-tree.txt"
  gate_record 2 PASS "merge-clean" "tree ${MT_TREE}"
elif [ "${MT_RC}" -eq 1 ]; then
  echo "result=CONFLICT" >>"${EVIDENCE_DIR}/02-merge-tree.txt"
  gate_record 2 FAIL "merge-conflict" "git merge-tree reported conflicts (exit 1)"
  skip_from 3 "gate2-failed"
  stop_run
else
  echo "result=ERROR" >>"${EVIDENCE_DIR}/02-merge-tree.txt"
  gate_record 2 FAIL "merge-tree-error" "git merge-tree exit ${MT_RC}; a clean merge is unproven"
  skip_from 3 "gate2-failed"
  stop_run
fi

# ── Gate 3 — Install-smoke ───────────────────────────────────────────────────
echo ""
echo "── Gate 3: Install-smoke"
CURRENT_GATE=3
SMOKE_LOG="${EVIDENCE_DIR}/03-install-smoke.txt"
make install-smoke >"${SMOKE_LOG}" 2>&1
SMOKE_RC=$?
if [ "${SMOKE_RC}" -eq 0 ]; then
  # A matching receipt is a cached fingerprint match, not a fresh install.
  if grep -q "install-smoke evidence matches; not upgrading" "${SMOKE_LOG}"; then
    gate_record 3 PASS "install-smoke-cached-receipt" "fingerprint receipt matched; no fresh install ran" 1
  else
    gate_record 3 PASS "install-smoke-ran" "make install-smoke exited 0" 1
  fi
else
  gate_record 3 FAIL "install-smoke-failed" "make install-smoke exited ${SMOKE_RC}" 1
  skip_from 4 "gate3-failed"
  stop_run
fi

# ── Gate 4 — Cutover clone ───────────────────────────────────────────────────
echo ""
echo "── Gate 4: Cutover clone"
CURRENT_GATE=4
CLONE_LOG="${EVIDENCE_DIR}/04-clone.log"
G4_REASON=""
if ! bash scripts/test_env.sh clone "${CUTOVER_DB}" >>"${CLONE_LOG}" 2>&1; then
  G4_REASON="clone-failed"
elif ! bash scripts/test_env.sh upgrade "${CUTOVER_DB}" >>"${CLONE_LOG}" 2>&1; then
  G4_REASON="upgrade-failed"
elif ! bash scripts/test_env.sh assert-clone "${CUTOVER_DB}" >>"${CLONE_LOG}" 2>&1; then
  G4_REASON="assert-clone-failed"
fi
if [ -n "${G4_REASON}" ]; then
  gate_record 4 FAIL "${G4_REASON}" "see 04-clone.log" 1
  skip_from 5 "gate4-failed"
  stop_run
fi
CENSUS_RAW="${EVIDENCE_DIR}/04-clone-census.raw"
PARTNER_COUNT="$(business_partner_census "${CUTOVER_DB}" "${CENSUS_RAW}")"
CENSUS_RC=$?
echo "partner_census_before_import=${PARTNER_COUNT:-unknown}" >"${EVIDENCE_DIR}/04-clone-census.txt"
if [ "${CENSUS_RC}" -ne 0 ]; then
  gate_record 4 FAIL "census-unproven" "the business-partner census query failed or returned no integer" 1
  skip_from 5 "gate4-failed"
  stop_run
elif [ "${PARTNER_COUNT}" -ne 0 ]; then
  gate_record 4 FAIL "clone-not-empty" "${PARTNER_COUNT} business partners (inactive included) before import" 1
  skip_from 5 "gate4-failed"
  stop_run
fi
gate_record 4 PASS "clone-empty" "${CUTOVER_DB} verified, 0 business partners" 1

# ── Gate 5 — Web lead e2e ────────────────────────────────────────────────────
echo ""
echo "── Gate 5: Web lead e2e"
CURRENT_GATE=5
bash "${KIT_DIR}/weblead_e2e.sh" "${ROOT}" "${CUTOVER_DB}" "${REHEARSAL_PORT}" "${EVIDENCE_DIR}"
G5_RC=$?
if [ "$(gate_state 5)" = "MISSING" ]; then
  gate_record 5 FAIL "helper-no-receipt" "weblead_e2e.sh exited ${G5_RC} without a gate receipt" 1
fi

# ── Gate 6 — ERP 10% slice ───────────────────────────────────────────────────
echo ""
echo "── Gate 6: ERP 10% slice"
CURRENT_GATE=6
bash "${KIT_DIR}/erp_slice.sh" "${ROOT}" "${CUTOVER_DB}" "${EVIDENCE_DIR}"
G6_RC=$?
if [ "$(gate_state 6)" = "MISSING" ]; then
  gate_record 6 FAIL "helper-no-receipt" "erp_slice.sh exited ${G6_RC} without a gate receipt" 1
fi

# ── Gate 7 — VanillaSoft historical cohort (bounded sample) ──────────────────
# The same `make import-vanillasoft` production runs, in its history mode:
# the operator's frozen 4,876-ContactID census (VANILLASOFT_HISTORY_CENSUS and
# its declared SHA-256 come from the environment; the kit never writes one),
# fetched one ContactID at a time through the history driver, capped at
# REHEARSAL_HISTORY_MAX_IDS. The ledger is this run's evidence file, so a
# production checkpoint is never bound to the disposable clone. A PASS proves
# only that the sample exercised the pipeline; it never claims the cohort.
echo ""
echo "── Gate 7: VanillaSoft historical cohort (bounded sample)"
CURRENT_GATE=7
REHEARSAL_HISTORY_MAX_IDS="${REHEARSAL_HISTORY_MAX_IDS:-100}"
VS_CENSUS="${VANILLASOFT_HISTORY_CENSUS:-}"
VS_CENSUS_SHA="$(printf '%s' "${VANILLASOFT_HISTORY_CENSUS_SHA256:-}" | tr '[:upper:]' '[:lower:]')"
VS_LEDGER="${EVIDENCE_DIR}/06-crm-history.jsonl"
G7_STATE=""
if [ "$(gate_state 6)" != "PASS" ]; then
  gate_record 7 SKIPPED "gate6-not-passed" "VanillaSoft contacts resolve against ERP partners"
# ── Safety guards: the rehearsal is never production and never a rolling window
elif [ "${ODOO_STAGE:-}" = "production" ]; then
  gate_record 7 FAIL "production-stage-refused" "ODOO_STAGE=production; refusing a rehearsal import against production"
elif [ -n "${VANILLASOFT_PRODUCTION_PERMIT:-}" ]; then
  gate_record 7 FAIL "production-permit-refused" "VANILLASOFT_PRODUCTION_PERMIT is set; the rehearsal never passes a permit"
elif [ -n "${VANILLASOFT_CALL_FLOOR:-}${VANILLASOFT_CONTACT_FLOOR:-}" ]; then
  gate_record 7 FAIL "rolling-floor-refused" "a VanillaSoft call or contact floor is set; Gate 7 runs the historical cohort, not a window"
elif [ -n "${VANILLASOFT_HISTORY_CHECKPOINT:-}" ]; then
  gate_record 7 FAIL "history-checkpoint-refused" "VANILLASOFT_HISTORY_CHECKPOINT is set; the rehearsal writes its own ledger and never binds an operator ledger to the clone"
# ── Runtime inputs the operator supplies (never generated here) ──────────────
elif [ -z "${VS_CENSUS}" ]; then
  gate_record 7 BLOCKED "vanillasoft-history-census-unbound" "VANILLASOFT_HISTORY_CENSUS is unset; the approved 4,876-ContactID census is an operator runtime input"
elif [ -z "${VS_CENSUS_SHA}" ]; then
  gate_record 7 BLOCKED "vanillasoft-history-digest-unbound" "VANILLASOFT_HISTORY_CENSUS_SHA256 is unset; the census is used only against its independently declared digest"
elif [ ! -r "${VS_CENSUS}" ]; then
  gate_record 7 FAIL "vanillasoft-history-census-unreadable" "VANILLASOFT_HISTORY_CENSUS names a file that cannot be read"
elif ! printf '%s\n' "${REHEARSAL_HISTORY_MAX_IDS}" | grep -Eq '^[1-9][0-9]*$'; then
  gate_record 7 FAIL "vanillasoft-history-bound-invalid" "REHEARSAL_HISTORY_MAX_IDS must be a positive integer"
else
  VS_CENSUS_ABS="$(cd "$(dirname "${VS_CENSUS}")" && pwd)/$(basename "${VS_CENSUS}")"
  VS_CENSUS_ACTUAL="$(rlib sha256 "${VS_CENSUS}" 2>/dev/null || true)"
  if [ "${VS_CENSUS_ABS#"${ROOT}/"}" = "${VS_CENSUS_ABS}" ]; then
    gate_record 7 FAIL "vanillasoft-history-census-unmounted" "the census must be inside the checkout, the only bind mount the odoo container reads"
  elif [ "${VS_CENSUS_ACTUAL}" != "${VS_CENSUS_SHA}" ]; then
    gate_record 7 FAIL "vanillasoft-history-census-digest-mismatch" "the census file's SHA-256 is not the declared VANILLASOFT_HISTORY_CENSUS_SHA256"
  else
    # scripts/test_env.sh run validates the history form itself (census, digest
    # and ledger named, no floor, no permit) before make starts; a refusal
    # there is exit 2 and lands as FAIL vanillasoft-preflight-failed below.
    G7_STATE="run"
  fi
fi
if [ "${G7_STATE}" = "run" ]; then
  # ── Bind VANILLASOFT_API_KEY from Infisical (value never printed) ──────────
  _GOV="${HOME}/.cursor-governance"
  [ -d "${_GOV}/ops/secrets" ] || _GOV="${HOME}/Cursor-Governance"
  _GOV_PY="${_GOV}/.venv/bin/python"
  [ -x "${_GOV_PY}" ] || _GOV_PY="python3"
  VS_BIND_STATUS="$("${_GOV_PY}" "${_GOV}/ops/secrets/capability_bind.py" --check VANILLASOFT_API_KEY 2>&1 || true)"
  if ! printf '%s\n' "${VS_BIND_STATUS}" | grep -q "source=infisical"; then
    gate_record 7 BLOCKED "vanillasoft-key-unbound" "capability_bind did not report source=infisical"
  else
    # The key flows Infisical → this Python process → psql stdin. It is never on
    # argv, never in the shell, never printed, and psql's output is discarded.
    REHEARSAL_GOV="${_GOV}" REHEARSAL_DB="${CUTOVER_DB}" REHEARSAL_COMPOSE="${ROOT}/docker-compose.yml" \
      "${_GOV_PY}" - >"${EVIDENCE_DIR}/06-crm-key.log" 2>&1 <<'PYEOF'
import os
import secrets
import subprocess
import sys

sys.path.insert(0, os.environ["REHEARSAL_GOV"])
from ops.secrets.capability_bind import bind  # noqa: E402

value = bind("VANILLASOFT_API_KEY")
if not value:
    print("VanillaSoft key bound empty")
    sys.exit(3)
tag = "$vs" + secrets.token_hex(8) + "$"
if tag in value:
    sys.exit(4)
sql = (
    "INSERT INTO ir_config_parameter (key, value) VALUES "
    f"('plasticos_crm_sync.vanillasoft_api_key', {tag}{value}{tag}) "
    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;\n"
)
done = subprocess.run(
    ["docker", "compose", "-f", os.environ["REHEARSAL_COMPOSE"], "exec", "-T", "db",
     "psql", "-U", "odoo", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", os.environ["REHEARSAL_DB"]],
    input=sql, text=True, capture_output=True, check=False,
)
print(f"key injection exit={done.returncode}")
sys.exit(0 if done.returncode == 0 else 5)
PYEOF
    VS_INJECT_RC=$?
    if [ "${VS_INJECT_RC}" -ne 0 ]; then
      gate_record 7 FAIL "vanillasoft-key-injection-failed" "exit ${VS_INJECT_RC}; see 06-crm-key.log" 1
    else
      # The history driver refuses while the incremental cron is active. The
      # clone inherits the template's cron row, so it is deactivated here, the
      # same operator step production takes before its history run.
      printf '%s\n' "UPDATE ir_cron SET active = false WHERE id IN (SELECT res_id FROM ir_model_data WHERE module = 'plasticos_crm_sync' AND name = 'cron_crm_sync_all' AND model = 'ir.cron');" \
        | db_query "${CUTOVER_DB}" "${EVIDENCE_DIR}/06-crm-cron.raw" \
        || echo "query-failed" >>"${EVIDENCE_DIR}/06-crm-cron.raw"
      # Durable VanillaSoft refs before the run: the fresh clone should hold none.
      VS_REFS_BEFORE="$(vanillasoft_ref_census "${CUTOVER_DB}" "${EVIDENCE_DIR}/06-crm-refs-before.raw")" \
        || echo "query-failed" >"${EVIDENCE_DIR}/06-crm-refs-before.raw"
      echo "durable_refs_before=${VS_REFS_BEFORE:-unknown}" >"${EVIDENCE_DIR}/06-crm-refs.txt"
      EVIDENCE_REL="${EVIDENCE_DIR#"${ROOT}/"}"
      VS_REPORT="/mnt/extra-addons/${EVIDENCE_REL}/06-crm-result.json"
      # Host paths, relative to the checkout: the Makefile places them on the
      # container's bind mount itself (runtime_path). The report path is the
      # container path, as for Gate 6. No floor is passed: history mode only.
      bash "${ROOT}/scripts/test_env.sh" run "${CUTOVER_DB}" -- \
        make import-vanillasoft \
          ODOO_DB_NAME="${CUTOVER_DB}" \
          VANILLASOFT_HISTORY_CENSUS="${VS_CENSUS_ABS#"${ROOT}/"}" \
          VANILLASOFT_HISTORY_CENSUS_SHA256="${VS_CENSUS_SHA}" \
          VANILLASOFT_HISTORY_CHECKPOINT="${EVIDENCE_REL}/06-crm-history.jsonl" \
          VANILLASOFT_HISTORY_MAX_IDS="${REHEARSAL_HISTORY_MAX_IDS}" \
          VANILLASOFT_REPORT_PATH="${VS_REPORT}" \
          >"${EVIDENCE_DIR}/06-crm-log.txt" 2>&1
      VS_RC=$?
      VS_REFS_AFTER="$(vanillasoft_ref_census "${CUTOVER_DB}" "${EVIDENCE_DIR}/06-crm-refs-after.raw")" \
        || echo "query-failed" >"${EVIDENCE_DIR}/06-crm-refs-after.raw"
      echo "durable_refs_after=${VS_REFS_AFTER:-unknown}" >>"${EVIDENCE_DIR}/06-crm-refs.txt"
      rlib check-vanillasoft-history "${EVIDENCE_DIR}" \
        --report "${EVIDENCE_DIR}/06-crm-result.json" \
        --import-exit "${VS_RC}" \
        --ledger "${VS_LEDGER}" \
        --log "${EVIDENCE_DIR}/06-crm-log.txt" \
        --refs-before "${EVIDENCE_DIR}/06-crm-refs-before.raw" \
        --refs-after "${EVIDENCE_DIR}/06-crm-refs-after.raw" \
        --census-sha256 "${VS_CENSUS_SHA}" \
        --database "${CUTOVER_DB}" \
        --max-ids "${REHEARSAL_HISTORY_MAX_IDS}" \
        --release-sha "${HEAD_SHA}" \
        --run-started "${RUN_STARTED_UTC}"
    fi
  fi
fi
if [ "$(gate_state 7)" = "MISSING" ]; then
  gate_record 7 FAIL "no-receipt" "Gate 7 ended without a receipt" 1
fi
CURRENT_GATE=0

# ── Remote refs unchanged since Gate 1 ───────────────────────────────────────
echo ""
LS_REMOTE="$(git ls-remote origin refs/heads/Staging refs/heads/Production 2>/dev/null)"
LS_RC=$?
REMOTE_STAGING="$(printf '%s\n' "${LS_REMOTE}" | awk '$2 == "refs/heads/Staging" {print $1}')"
REMOTE_PROD="$(printf '%s\n' "${LS_REMOTE}" | awk '$2 == "refs/heads/Production" {print $1}')"
{
  echo "start_staging=${ORIGIN_STAGING}"
  echo "end_staging=${REMOTE_STAGING}"
  echo "start_production=${PROD_SHA}"
  echo "end_production=${REMOTE_PROD}"
} >"${EVIDENCE_DIR}/07-remote-refs.txt"
if [ "${LS_RC}" -ne 0 ] || [ -z "${REMOTE_STAGING}" ] || [ -z "${REMOTE_PROD}" ]; then
  echo "⚠️  Remote refs could not be re-read; readiness is unproven"
  add_run_failure "remote-refs-unverifiable"
else
  if [ "${REMOTE_PROD}" != "${PROD_SHA}" ]; then
    echo "⚠️  origin/Production moved during the rehearsal: ${PROD_SHA} → ${REMOTE_PROD}"
    add_run_failure "production-ref-drifted"
  fi
  if [ "${REMOTE_STAGING}" != "${ORIGIN_STAGING}" ]; then
    echo "⚠️  origin/Staging moved during the rehearsal: ${ORIGIN_STAGING} → ${REMOTE_STAGING}"
    add_run_failure "staging-ref-drifted"
  fi
fi

finalize_run
exit $?
