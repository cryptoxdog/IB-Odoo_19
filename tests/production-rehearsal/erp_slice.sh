#!/usr/bin/env bash
# Gate 6 — ERP 10% slice import from the restored SQL Server database.
#
# The importer writes its own summary (05-erp-summary.json) and census
# (05-erp-summary-census.json); this script never writes into either. The gate
# verdict is $EVIDENCE_DIR/gate-6.json, written by common.py check-erp
# from the summary, the census, the import exit code, a read-only count of
# the imported counterparty, address and contact identities on the clone, and
# an independent field comparison of those persisted rows with the SQL source.
# Exit 0 only on PASS.
# Usage: bash erp_slice.sh <plasticos_root> <db> <evidence_dir>
set -uo pipefail
umask 077

ROOT="${1:?plasticos_root required}"
DB="${2:?db name required}"
EVIDENCE_DIR="${3:?evidence_dir required}"
KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=rehearsal_common.sh source-path=SCRIPTDIR
. "${KIT_DIR}/rehearsal_common.sh"

SUMMARY_FILE="${EVIDENCE_DIR}/05-erp-summary.json"
IMPORT_LOG="${EVIDENCE_DIR}/05-erp-import.log"
LAYERS_FILE="${EVIDENCE_DIR}/05-erp-layers.json"
ODOO_FIDELITY="${EVIDENCE_DIR}/05-erp-fidelity-odoo.json"
FIDELITY_FILE="${EVIDENCE_DIR}/05-erp-fidelity.json"
COVERAGE_FILE="${EVIDENCE_DIR}/05-erp-fidelity-coverage.json"
# The Odoo container sees the repo at /mnt/extra-addons. The summary must be
# written there so the host evidence folder receives it through the bind mount.
EVIDENCE_REL="${EVIDENCE_DIR#"${ROOT}/"}"
CONTAINER_SUMMARY="/mnt/extra-addons/${EVIDENCE_REL}/05-erp-summary.json"
PROOF_DIR="${HOME}/.l9/erp-proof"
PROOF_PW="${PROOF_DIR}/reader.pw"
PROOF_DB="${PROOF_DIR}/database"

echo "→ [Gate 6] ERP 10% slice import on ${DB}"

# gate6 <STATE> <reason> [detail] — scan, write the receipt, exit nonzero.
gate6() {
  local state="$1" reason="$2" detail="${3:-}"
  if ! rlib scan-secrets "${EVIDENCE_DIR}" --env ERP_SQL_PASSWORD; then
    state="FAIL"
    reason="evidence-secret-redacted"
    detail="the ERP reader password appeared in evidence and was redacted"
  fi
  rlib gate-write "${EVIDENCE_DIR}" 6 "${state}" "${reason}" --detail "${detail}" --side-effects
  echo "  ❌ Gate 6 ${state}: ${reason}${detail:+ — ${detail}}"
  exit 1
}

# ── Safety guards (before any read of the source or write to the clone) ─────
if [ "${ODOO_STAGE:-}" = "production" ]; then
  gate6 FAIL "production-stage-refused" "ODOO_STAGE=production; refusing a rehearsal import against production"
fi
if [ -n "${ERP_PRODUCTION_PERMIT:-}" ]; then
  gate6 FAIL "production-permit-refused" "ERP_PRODUCTION_PERMIT is set; the rehearsal never passes a permit"
fi
if [ "${ERP_REQUIRE_EMPTY:-1}" != "1" ]; then
  gate6 FAIL "empty-guard-disabled" "ERP_REQUIRE_EMPTY must stay 1 on the rehearsal clone"
fi
if [ -n "${ERP_PAYLOAD_ROOT:-}" ] || [ -n "${PAYLOAD_ROOT:-}" ]; then
  gate6 FAIL "payload-root-refused" "a payload root selects the frozen grid; Gate 6 reads only the restored database"
fi

# The restored database and its reader login already exist. A .bak is not
# opened here, and nothing is written to .env.local. An exported server and
# database still win. The password stays in the environment, never on argv.
if [ -z "${ERP_SQL_SERVER:-}" ] && [ -z "${ERP_SQL_DATABASE:-}" ]; then
  if [ ! -s "${PROOF_PW}" ] || [ ! -s "${PROOF_DB}" ]; then
    gate6 BLOCKED "erp-proof-files-missing" \
      "${PROOF_DIR} lacks reader.pw or database and ERP_SQL_SERVER / ERP_SQL_DATABASE are unset"
  fi
  ERP_SQL_SERVER="host.docker.internal"
  ERP_SQL_PORT="14330"
  ERP_SQL_DATABASE="$(tr -d '[:space:]' < "${PROOF_DB}")"
  ERP_SQL_USER="erp_reader"
  ERP_SQL_PASSWORD="$(cat "${PROOF_PW}")"
elif [ -z "${ERP_SQL_SERVER:-}" ] || [ -z "${ERP_SQL_DATABASE:-}" ]; then
  gate6 BLOCKED "erp-source-incomplete" "ERP_SQL_SERVER and ERP_SQL_DATABASE must both be set"
elif [ -z "${ERP_SQL_PASSWORD:-}" ] && [ -s "${PROOF_PW}" ]; then
  ERP_SQL_USER="${ERP_SQL_USER:-erp_reader}"
  ERP_SQL_PASSWORD="$(cat "${PROOF_PW}")"
fi
if [ -z "${ERP_SQL_PORT:-}" ] && [ "${ERP_SQL_SERVER}" = "host.docker.internal" ]; then
  ERP_SQL_PORT="14330"
fi
export ERP_SQL_SERVER ERP_SQL_DATABASE
[ -n "${ERP_SQL_PORT:-}" ] && export ERP_SQL_PORT
[ -n "${ERP_SQL_USER:-}" ] && export ERP_SQL_USER
[ -n "${ERP_SQL_PASSWORD:-}" ] && export ERP_SQL_PASSWORD
echo "  ✅ ERP source ${ERP_SQL_SERVER}:${ERP_SQL_PORT:-1433} (database and credential not printed)"
echo "  ✅ Projection scripts: plasticos_partner_import/erp_extracted_data"

# ── Partner census before import (inactive partners count too) ─────────────
echo "  → Partner census before import..."
PARTNER_COUNT="$(business_partner_census "${DB}" "${EVIDENCE_DIR}/05-erp-census-before.raw")" \
  || gate6 FAIL "census-unproven" "the business-partner census query failed or returned no integer"
echo "  Business partners before import: ${PARTNER_COUNT}"
if [ "${PARTNER_COUNT}" -ne 0 ]; then
  gate6 FAIL "clone-not-empty" "${PARTNER_COUNT} business partners already exist in ${DB}; reclone first"
fi

# ── Run import via test_env.sh run (verified clone only) ────────────────────
echo "  → Running import-erp LIMIT=10% on ${DB}..."
bash "${ROOT}/scripts/test_env.sh" run "${DB}" -- \
  make import-erp \
    ODOO_DB_NAME="${DB}" \
    LIMIT=10% \
    ERP_SQL_SERVER="${ERP_SQL_SERVER}" \
    ERP_SQL_PORT="${ERP_SQL_PORT:-1433}" \
    ERP_SQL_DATABASE="${ERP_SQL_DATABASE}" \
    ${ERP_SQL_USER:+ERP_SQL_USER="${ERP_SQL_USER}"} \
    REPORT_PATH="${CONTAINER_SUMMARY}" \
  >"${IMPORT_LOG}" 2>&1
IMPORT_EXIT=$?
echo "  import-erp exit ${IMPORT_EXIT} (log: 05-erp-import.log)"

# ── Read the imported identities back from the clone (read-only) ────────────
printf '%s\n' "SELECT json_build_object(
  'counterparties', (SELECT COUNT(*) FROM ir_model_data d JOIN res_partner p ON p.id = d.res_id
      WHERE d.module = 'plasticos_transaction' AND d.model = 'res.partner'
        AND starts_with(d.name, 'legacy_erp_cp_')),
  'addresses', (SELECT COUNT(*) FROM ir_model_data d JOIN res_partner p ON p.id = d.res_id
      WHERE d.module = 'plasticos_transaction' AND d.model = 'res.partner'
        AND starts_with(d.name, 'legacy_erp_address_')),
  'contacts', (SELECT COUNT(*) FROM ir_model_data d JOIN res_partner p ON p.id = d.res_id
      WHERE d.module = 'plasticos_transaction' AND d.model = 'res.partner'
        AND starts_with(d.name, 'legacy_erp_contact_')
        AND NOT starts_with(d.name, 'legacy_erp_contact_role_')));" \
  | db_query "${DB}" "${LAYERS_FILE}" || rm -f "${LAYERS_FILE}"

# Field fidelity reads the clone and the same SQL source. LIMIT=10% is unchanged.
# A missing snapshot is an incomplete report, which check-erp fails closed.
echo "  → ERP native mapping fidelity..."
if ! "${REHEARSAL_PY}" "${KIT_DIR}/fidelity_run.py" --print-odoo-sql | db_query "${DB}" "${ODOO_FIDELITY}"; then
  rm -f "${ODOO_FIDELITY}"
fi
if [ -n "${STUB_DIR:-}" ] || "${REHEARSAL_PY}" -c 'import pymssql' >/dev/null 2>&1; then
  "${REHEARSAL_PY}" "${KIT_DIR}/fidelity_run.py" \
    --odoo "${ODOO_FIDELITY}" \
    --out "${FIDELITY_FILE}" \
    --coverage "${COVERAGE_FILE}" \
    --census "${SUMMARY_FILE%.json}-census.json" || true
else
  # The compose stack declares db, odoo, odoo-test and odoo-test-demo (no `web`),
  # and `exec` needs a running service. `run --rm --no-deps` starts the same
  # odoo image make import-erp uses, whose entrypoint execs python3 directly;
  # the SQL password travels in the environment (-e NAME, no value), never argv.
  docker compose -f "${ROOT}/docker-compose.yml" run --rm --no-deps -T \
    -e ERP_SQL_SERVER -e ERP_SQL_PORT -e ERP_SQL_DATABASE -e ERP_SQL_USER -e ERP_SQL_PASSWORD \
    -e FIDELITY_IN_WEB=1 \
    odoo python3 /mnt/extra-addons/tests/production-rehearsal/fidelity_run.py \
    --odoo "/mnt/extra-addons/${EVIDENCE_REL}/05-erp-fidelity-odoo.json" \
    --out "/mnt/extra-addons/${EVIDENCE_REL}/05-erp-fidelity.json" \
    --coverage "/mnt/extra-addons/${EVIDENCE_REL}/05-erp-fidelity-coverage.json" \
    --census "/mnt/extra-addons/${EVIDENCE_REL}/05-erp-summary-census.json" || true
fi
if [ ! -s "${FIDELITY_FILE}" ]; then
  printf '%s\n' '{"schema":"l9.plasticos.rehearsal.fidelity.v1","evidence":"missing","missing_reason":"fidelity checker produced no report","status":"FAIL","failed":1,"compared":0,"rows":[]}' \
    > "${FIDELITY_FILE}"
fi

if ! rlib scan-secrets "${EVIDENCE_DIR}" --env ERP_SQL_PASSWORD; then
  gate6 FAIL "evidence-secret-redacted" "the ERP reader password appeared in evidence and was redacted"
fi
# The receipt names the one execution path (target, driver, dispatcher, source,
# bounds, database, revision) and reads the driver's own trace lines from the
# import log; a log without them is a failure, never a pass.
RELEASE_SHA="$(git -C "${ROOT}" rev-parse --verify --quiet 'HEAD^{commit}' || true)"
rlib check-erp "${EVIDENCE_DIR}" \
  --summary "${SUMMARY_FILE}" \
  --import-exit "${IMPORT_EXIT}" \
  --layers "${LAYERS_FILE}" \
  --log "${IMPORT_LOG}" \
  --database "${DB}" \
  --limit "10%" \
  --release-sha "${RELEASE_SHA}" \
  --run-started "${RUN_STARTED_UTC:-}" \
  --fidelity "${FIDELITY_FILE}" \
  --snapshot "${ODOO_FIDELITY}"
