#!/usr/bin/env bash
# Staging → Production Promotion Rehearsal — full orchestrator.
#
# Usage:
#   bash tests/production-rehearsal/run.sh
#
# Evidence is written to:
#   tests/production-rehearsal/evidence/YYYY-MM-DD_HHMMSS/
# A symlink `evidence/latest` always points to the most recent run.
#
# Prerequisites: see README.md.
# Spec + acceptance criteria: see SPEC.md.
# Named blockers: see expected/blockers.yaml.
set -euo pipefail

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

cd "${ROOT}"

# ── Load .env.local secrets (not printed) ────────────────────────────────────
if [ -f "${ROOT}/.env.local" ]; then
  set -a
  # shellcheck source=/dev/null
  . "${ROOT}/.env.local"
  set +a
fi
if [ -f "${ROOT}/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  . "${ROOT}/.env"
  set +a
fi

# ── Create dated evidence folder ─────────────────────────────────────────────
RUN_TS="$(date -u +%Y-%m-%d_%H%M%S)"
EVIDENCE_DIR="${KIT_DIR}/evidence/${RUN_TS}"
mkdir -p "${EVIDENCE_DIR}"
ln -sfn "${EVIDENCE_DIR}" "${KIT_DIR}/evidence/latest"
export REHEARSAL_EVIDENCE_DIR="${EVIDENCE_DIR}"

echo "════════════════════════════════════════════════════════"
echo " Staging → Production Promotion Rehearsal"
echo " Run:      ${RUN_TS}"
echo " Evidence: ${EVIDENCE_DIR}"
echo "════════════════════════════════════════════════════════"

REHEARSAL_PORT="${REHEARSAL_PORT:-18069}"
CUTOVER_DB="odoo_test_cutover"
VERDICT="ready"
FAILURES=()

# ── Gate 1 — Branch identity ─────────────────────────────────────────────────
echo ""
echo "── Gate 1: Branch identity"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
STAGING_HEAD="$(git rev-parse HEAD)"
ORIGIN_STAGING="$(git rev-parse origin/Staging)"
echo "  Branch: ${BRANCH}  HEAD: ${STAGING_HEAD}"
echo "  origin/Staging: ${ORIGIN_STAGING}"
{
  echo "branch=${BRANCH}"
  echo "HEAD=${STAGING_HEAD}"
  echo "origin/Staging=${ORIGIN_STAGING}"
} > "${EVIDENCE_DIR}/00-staging-sha.txt"

if [ "${BRANCH}" != "Staging" ] || [ "${STAGING_HEAD}" != "${ORIGIN_STAGING}" ]; then
  echo "  ❌ Gate 1 FAILED: not on Staging or ahead of origin"
  VERDICT="failed"; FAILURES+=("Gate1-branch-identity")
else
  echo "  ✅ Gate 1 PASSED"
fi

# ── Gate 2 — Merge-tree ───────────────────────────────────────────────────────
echo ""
echo "── Gate 2: Merge-tree (read-only)"
PROD_SHA="$(git rev-parse origin/Production)"
echo "  origin/Production: ${PROD_SHA}"
echo "origin/Production=${PROD_SHA}" > "${EVIDENCE_DIR}/01-production-sha.txt"

MT_OUT="$(git merge-tree origin/Production origin/Staging 2>&1)"
MT_CONFLICTS=$(echo "${MT_OUT}" | grep -c "^<<<<<<" || true)
{
  echo "origin/Production=${PROD_SHA}"
  echo "origin/Staging=${ORIGIN_STAGING}"
  echo "conflict_markers=${MT_CONFLICTS}"
  echo "---"
  echo "${MT_OUT}"
} > "${EVIDENCE_DIR}/02-merge-tree.txt"

if [ "${MT_CONFLICTS}" -gt 0 ]; then
  echo "  ❌ Gate 2 FAILED: ${MT_CONFLICTS} conflict markers"
  VERDICT="failed"; FAILURES+=("Gate2-merge-conflict")
else
  echo "  ✅ Gate 2 PASSED: clean merge (${PROD_SHA} ← ${STAGING_HEAD})"
fi

# ── Gate 3 — Install-smoke ────────────────────────────────────────────────────
echo ""
echo "── Gate 3: Install-smoke"
SMOKE_LOG="${EVIDENCE_DIR}/03-install-smoke.txt"
if make install-smoke > "${SMOKE_LOG}" 2>&1; then
  echo "  ✅ Gate 3 PASSED"
else
  echo "  ❌ Gate 3 FAILED — see ${SMOKE_LOG}"
  VERDICT="failed"; FAILURES+=("Gate3-install-smoke")
fi

# ── Gate 4 — Cutover clone ────────────────────────────────────────────────────
echo ""
echo "── Gate 4: Cutover clone"
bash scripts/test_env.sh clone "${CUTOVER_DB}" 2>&1
bash scripts/test_env.sh upgrade "${CUTOVER_DB}" 2>&1 | tail -3
bash scripts/test_env.sh assert-clone "${CUTOVER_DB}" 2>&1

PARTNER_COUNT=$(docker compose exec -T db \
  psql -U odoo -t -c \
  "SELECT COUNT(*) FROM res_partner WHERE (customer_rank > 0 OR supplier_rank > 0) AND active = true;" \
  "${CUTOVER_DB}" 2>/dev/null | tr -d '[:space:]')
echo "  Business partners before data: ${PARTNER_COUNT:-0}"
echo "partner_census_before_import=${PARTNER_COUNT:-0}" > "${EVIDENCE_DIR}/04-clone-census.txt"

if [ "${PARTNER_COUNT:-0}" -gt 0 ]; then
  echo "  ❌ Gate 4 FAILED: clone has ${PARTNER_COUNT} business partners already"
  VERDICT="failed"; FAILURES+=("Gate4-clone-not-empty")
else
  echo "  ✅ Gate 4 PASSED"
fi

# ── Gate 5 — Web lead e2e ─────────────────────────────────────────────────────
echo ""
echo "── Gate 5: Web lead e2e"
if bash "${KIT_DIR}/weblead_e2e.sh" "${ROOT}" "${CUTOVER_DB}" "${REHEARSAL_PORT}" "${EVIDENCE_DIR}"; then
  echo "  ✅ Gate 5 PASSED"
else
  echo "  ❌ Gate 5 FAILED"
  VERDICT="failed"; FAILURES+=("Gate5-weblead-e2e")
fi

# ── Gate 6 — ERP 10% slice ────────────────────────────────────────────────────
echo ""
echo "── Gate 6: ERP 10% slice"
if bash "${KIT_DIR}/erp_slice.sh" "${ROOT}" "${CUTOVER_DB}" "${EVIDENCE_DIR}"; then
  ERP_PASSED=1
  echo "  ✅ Gate 6 PASSED"
else
  ERP_PASSED=0
  echo "  ❌ Gate 6 FAILED"
  VERDICT="failed"; FAILURES+=("Gate6-erp-import")
fi

# ── Gate 7 — VanillaSoft 100 contacts ────────────────────────────────────────
echo ""
echo "── Gate 7: VanillaSoft 100 contacts"
if [ "${ERP_PASSED}" -eq 0 ]; then
  echo "  ⏭  Gate 7 SKIPPED: Gate 6 did not pass. VanillaSoft contacts resolve against ERP partners."
  VERDICT="failed"; FAILURES+=("Gate7-skipped-erp-not-passed")
else
  # ── Bind VANILLASOFT_API_KEY from Infisical (value never printed) ──────────
  _GOV="${HOME}/.cursor-governance"
  [ -d "${_GOV}/ops/secrets" ] || _GOV="${HOME}/Cursor-Governance"
  _GOV_PY="${_GOV}/.venv/bin/python"
  [ -x "${_GOV_PY}" ] || _GOV_PY="python3"
  _BIND_SCRIPT="${_GOV}/ops/secrets/capability_bind.py"

  VS_BIND_STATUS=$("${_GOV_PY}" "${_BIND_SCRIPT}" --check VANILLASOFT_API_KEY 2>&1 || true)
  if echo "${VS_BIND_STATUS}" | grep -q "source=infisical"; then
    # Inject into clone ICP — value flows through python to psql, never touches shell stdout
    "${_GOV_PY}" - <<PYEOF 2>/dev/null
import sys
sys.path.insert(0, "${_GOV}")
from ops.secrets.capability_bind import bind
val = bind("VANILLASOFT_API_KEY")
import subprocess
subprocess.run(
    ["docker", "compose", "exec", "-T", "db", "psql", "-U", "odoo",
     "-c", f"INSERT INTO ir_config_parameter (key,value) VALUES ('plasticos_crm_sync.vanillasoft_api_key',\$\${val}\$\$) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value;",
     "${CUTOVER_DB}"],
    check=True, capture_output=True
)
print("VanillaSoft API key injected from Infisical")
PYEOF
    echo "  ✅ VANILLASOFT_API_KEY bound from Infisical and injected into ${CUTOVER_DB} ICP"
  else
    echo "  ❌ Gate 7 BLOCKED: VANILLASOFT_API_KEY not bound (${VS_BIND_STATUS})"
    echo "     Add VANILLASOFT_API_KEY to ~/.cursor-governance/ops/secrets/infisical-cursor-governance.yaml"
    VERDICT="blocked"; FAILURES+=("Gate7-vanillasoft-key-missing")
    VS_BIND_STATUS="failed"  # mark skip
  fi

  if echo "${VS_BIND_STATUS}" | grep -q "source=infisical"; then
    # Set a 7-day floor so only recent contacts are fetched (bounded rehearsal scope)
    VANILLASOFT_CALL_FLOOR="$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)"
    export VANILLASOFT_CALL_FLOOR

    VS_REPORT="${EVIDENCE_DIR}/06-crm-result.json"
    if ODOO_DB_NAME="${CUTOVER_DB}" VANILLASOFT_REPORT_PATH="${VS_REPORT}" \
       make import-vanillasoft > "${EVIDENCE_DIR}/06-crm-log.txt" 2>&1; then
      echo "  ✅ Gate 7 PASSED"
    else
      echo "  ❌ Gate 7 FAILED — see ${EVIDENCE_DIR}/06-crm-log.txt"
      VERDICT="failed"; FAILURES+=("Gate7-vanillasoft-sync")
    fi
  fi
fi

# ── Confirm Production SHA unchanged ─────────────────────────────────────────
echo ""
PROD_SHA_FINAL="$(git rev-parse origin/Production)"
if [ "${PROD_SHA_FINAL}" != "${PROD_SHA}" ]; then
  echo "⚠️  origin/Production changed during rehearsal! Started=${PROD_SHA} Ended=${PROD_SHA_FINAL}"
  VERDICT="failed"; FAILURES+=("Production-SHA-drifted")
else
  echo "✅ origin/Production unchanged at ${PROD_SHA}"
fi

# ── Write verdict ─────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
{
  echo "run_ts=${RUN_TS}"
  echo "staging_sha=${STAGING_HEAD}"
  echo "production_sha=${PROD_SHA}"
  echo "verdict=${VERDICT}"
  if [ ${#FAILURES[@]} -gt 0 ]; then
    echo "failures=${FAILURES[*]}"
  fi
} | tee "${EVIDENCE_DIR}/verdict.txt"

if [ "${VERDICT}" = "ready" ]; then
  echo " ✅ VERDICT: ready — Staging is promotable to Production"
else
  echo " ❌ VERDICT: ${VERDICT} — Failed gates: ${FAILURES[*]:-none}"
fi
echo "════════════════════════════════════════════════════════"
echo " Evidence: ${EVIDENCE_DIR}"
echo " Latest:   ${KIT_DIR}/evidence/latest"

[ "${VERDICT}" = "ready" ]
