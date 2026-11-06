#!/usr/bin/env bash
# Gate 6 — ERP 10% slice import.
# Called by run.sh; writes summary to $EVIDENCE_DIR/05-erp-summary.json.
# Usage: bash erp_slice.sh <plasticos_root> <db> <evidence_dir>
set -euo pipefail

ROOT="${1:?plasticos_root required}"
DB="${2:?db name required}"
EVIDENCE_DIR="${3:?evidence_dir required}"

SUMMARY_FILE="${EVIDENCE_DIR}/05-erp-summary.json"
# The Odoo container sees the repo at /mnt/extra-addons. The summary must be
# written there so the host evidence folder receives it through the bind mount.
EVIDENCE_REL="${EVIDENCE_DIR#"${ROOT}/"}"
CONTAINER_SUMMARY="/mnt/extra-addons/${EVIDENCE_REL}/05-erp-summary.json"
PROOF_DIR="${HOME}/.l9/erp-proof"
PROOF_PW="${PROOF_DIR}/reader.pw"
PROOF_DB="${PROOF_DIR}/database"

echo "→ [Gate 6] ERP 10% slice import on ${DB}"

# The restored database and its reader login already exist. A .bak is not
# opened here, and nothing is written to .env.local. An exported server and
# database still win. The password stays in the environment, never on argv.
if [ -z "${ERP_SQL_SERVER:-}" ] && [ -z "${ERP_SQL_DATABASE:-}" ]; then
  if [ ! -s "${PROOF_PW}" ] || [ ! -s "${PROOF_DB}" ]; then
    echo "  ❌ BLOCKED: ${PROOF_DIR} is missing the reader password or database name, and ERP_SQL_SERVER / ERP_SQL_DATABASE are unset."
    echo '{"gate":6,"result":"blocked","reason":"existing ERP proof files missing"}' > "${SUMMARY_FILE}"
    exit 1
  fi
  ERP_SQL_SERVER="host.docker.internal"
  ERP_SQL_PORT="14330"
  ERP_SQL_DATABASE="$(tr -d '[:space:]' < "${PROOF_DB}")"
  ERP_SQL_USER="erp_reader"
  ERP_SQL_PASSWORD="$(cat "${PROOF_PW}")"
elif [ -z "${ERP_SQL_SERVER:-}" ] || [ -z "${ERP_SQL_DATABASE:-}" ]; then
  echo "  ❌ BLOCKED: ERP_SQL_SERVER and ERP_SQL_DATABASE must both be set."
  echo '{"gate":6,"result":"blocked","reason":"ERP_SQL_SERVER and ERP_SQL_DATABASE must both be set"}' > "${SUMMARY_FILE}"
  exit 1
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

# ── Safety guards ─────────────────────────────────────────────────────────────
if [ "${ODOO_STAGE:-}" = "production" ]; then
  echo "  ❌ BLOCKED: ODOO_STAGE=production — refusing rehearsal import against production."
  exit 1
fi
# ERP_PRODUCTION_PERMIT is intentionally not set
# ERP_REQUIRE_EMPTY is left at default (1) — the clone must have no business partners

# ── Partner census before import ──────────────────────────────────────────────
echo "  → Partner census before import..."
PARTNER_COUNT=$(docker compose -f "${ROOT}/docker-compose.yml" \
  exec -T db \
  psql -U odoo -t -c \
  "SELECT COUNT(*) FROM res_partner WHERE (customer_rank > 0 OR supplier_rank > 0) AND active = true;" \
  "${DB}" 2>/dev/null | tr -d '[:space:]')
echo "  Business partners before import: ${PARTNER_COUNT}"
if [ "${PARTNER_COUNT:-0}" -gt 0 ] && [ "${ERP_REQUIRE_EMPTY:-1}" = "1" ]; then
  echo "  ❌ BLOCKED: ${PARTNER_COUNT} business partners already exist in ${DB}. Reclone before ERP import."
  echo "{\"gate\":6,\"result\":\"blocked\",\"reason\":\"${PARTNER_COUNT} business partners already present\"}" > "${SUMMARY_FILE}"
  exit 1
fi

# ── Run import via test_env.sh run ────────────────────────────────────────────
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
  2>&1

IMPORT_EXIT=$?
if [ "${IMPORT_EXIT}" -ne 0 ]; then
  echo "  ❌ Gate 6 FAILED: import-erp exited ${IMPORT_EXIT}"
  echo "{\"gate\":6,\"result\":\"failed\",\"exit_code\":${IMPORT_EXIT}}" >> "${SUMMARY_FILE}"
  exit 1
fi

# ── Validate summary ──────────────────────────────────────────────────────────
if [ ! -f "${SUMMARY_FILE}" ]; then
  echo "  ❌ Gate 6 FAILED: no summary JSON written."
  exit 1
fi

python3 - "${SUMMARY_FILE}" <<'EOF'
import json, os, sys

with open(sys.argv[1]) as f:
    s = json.load(f)

seen = s.get("records_seen", 0)
created = s.get("records_created", 0)
updated = s.get("records_updated", 0)
unchanged = s.get("records_unchanged", 0)
rejected = s.get("records_rejected", 0)
dups = s.get("duplicates", 0)

total = created + updated + unchanged + rejected
ok = True
if seen != total:
    print(f"  ❌ Census mismatch: seen={seen} != created+updated+unchanged+rejected={total}")
    ok = False
if dups != 0:
    print(f"  ❌ Duplicates found: {dups}")
    ok = False
if created == 0:
    print("  ❌ No records created — import may have been a no-op.")
    ok = False

census_file = os.path.splitext(sys.argv[1])[0] + "-census.json"
try:
    with open(census_file) as census_handle:
        census = json.load(census_handle)
except OSError as exc:
    print(f"  ❌ Census missing: {census_file} ({exc})")
    ok = False
else:
    kind = census.get("payload_kind")
    if kind != "database":
        print(f"  ❌ ERP source is {kind!r}; Gate 6 accepts only payload_kind database")
        ok = False

if ok:
    print(f"  ✅ ERP summary valid: seen={seen} created={created} updated={updated} unchanged={unchanged} rejected={rejected} dups={dups}")
    sys.exit(0)
else:
    sys.exit(1)
EOF

echo "  ✅ Gate 6 PASSED"
