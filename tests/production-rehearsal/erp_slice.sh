#!/usr/bin/env bash
# Gate 6 — ERP 10% slice import.
# Called by run.sh; writes summary to $EVIDENCE_DIR/05-erp-summary.json.
# Usage: bash erp_slice.sh <plasticos_root> <db> <evidence_dir>
set -euo pipefail

ROOT="${1:?plasticos_root required}"
DB="${2:?db name required}"
EVIDENCE_DIR="${3:?evidence_dir required}"

SUMMARY_FILE="${EVIDENCE_DIR}/05-erp-summary.json"

echo "→ [Gate 6] ERP 10% slice import on ${DB}"

# ── Credential guard ─────────────────────────────────────────────────────────
if [ -z "${ERP_SQL_SERVER:-}" ] || [ -z "${ERP_SQL_DATABASE:-}" ]; then
  echo "  ❌ BLOCKED: ERP_SQL_SERVER or ERP_SQL_DATABASE is unset."
  echo '{"gate":6,"result":"blocked","reason":"ERP_SQL_SERVER or ERP_SQL_DATABASE not set"}' > "${SUMMARY_FILE}"
  exit 1
fi
echo "  ✅ ERP credentials present (not printed)"

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
  make -C /mnt/extra-addons import-erp \
    ODOO_DB_NAME="${DB}" \
    LIMIT=10% \
    ERP_SQL_SERVER="${ERP_SQL_SERVER}" \
    ERP_SQL_DATABASE="${ERP_SQL_DATABASE}" \
    ${ERP_SQL_USER:+ERP_SQL_USER="${ERP_SQL_USER}"} \
    ${ERP_SQL_PASSWORD:+ERP_SQL_PASSWORD="${ERP_SQL_PASSWORD}"} \
    REPORT_PATH="${SUMMARY_FILE}" \
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
