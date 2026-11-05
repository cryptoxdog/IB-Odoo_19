#!/usr/bin/env bash
# Gate 5 — Web lead e2e: POST proven HOT body, assert HOT intake + crm.lead.
# Called by run.sh; writes results to $EVIDENCE_DIR/04-weblead-result.json.
# Usage: bash weblead_e2e.sh <plasticos_root> <db> <rehearsal_port> <evidence_dir>
set -euo pipefail

ROOT="${1:?plasticos_root required}"
DB="${2:?db name required}"
PORT="${3:?rehearsal_port required}"
EVIDENCE_DIR="${4:?evidence_dir required}"

PAYLOAD="$(dirname "$0")/payloads/cognito_hot.json"
RESULT_FILE="${EVIDENCE_DIR}/04-weblead-result.json"

echo "→ [Gate 5] Web lead e2e on ${DB}:${PORT}"

# ── 1. Fetch the bearer token from the clone's ICP ──────────────────────────
echo "  → Fetching bearer token from clone ICP (not printed)..."
BEARER=$(docker compose -f "${ROOT}/docker-compose.yml" run --rm \
  -e ODOO_DB="${DB}" \
  odoo-test \
  python3 -c "
import sys, os
sys.path.insert(0, '/mnt/extra-addons')
os.environ.setdefault('ODOO_DB', '${DB}')
import odoo
odoo.tools.config.parse_config(['--config=/etc/odoo/odoo.conf', '-d', '${DB}'])
with odoo.api.Environment.manage():
    from odoo import registry
    reg = registry('${DB}')
    with reg.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        icp = env['ir.config_parameter']
        key = icp.sudo().get_param('plasticos.web_lead.api_key', default='')
        print(key)
" 2>/dev/null | tr -d '[:space:]')

if [ -z "${BEARER}" ]; then
  echo "  ❌ No bearer token in ICP for ${DB}; copying from compose 'odoo' database..."
  BEARER=$(docker compose -f "${ROOT}/docker-compose.yml" run --rm \
    odoo-test \
    python3 -c "
import sys, os
sys.path.insert(0, '/mnt/extra-addons')
os.environ.setdefault('ODOO_DB', 'odoo')
import odoo
odoo.tools.config.parse_config(['--config=/etc/odoo/odoo.conf', '-d', 'odoo'])
with odoo.api.Environment.manage():
    from odoo import registry
    try:
        reg = registry('odoo')
        with reg.cursor() as cr:
            env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
            icp = env['ir.config_parameter']
            key = icp.sudo().get_param('plasticos.web_lead.api_key', default='')
            print(key)
    except Exception:
        print('')
" 2>/dev/null | tr -d '[:space:]')
fi

if [ -z "${BEARER}" ]; then
  echo "  ❌ BLOCKED: no API key found. Set plasticos.web_lead.api_key ICP in ${DB} or in the odoo DB." | tee "${RESULT_FILE}"
  exit 1
fi

# ── 2. Start Odoo HTTP on rehearsal port ────────────────────────────────────
echo "  → Starting Odoo HTTP on 127.0.0.1:${PORT} with database ${DB}..."
docker compose -f "${ROOT}/docker-compose.yml" run --rm -d \
  --name "odoo_rehearsal_${PORT}" \
  -p "127.0.0.1:${PORT}:8069" \
  odoo-test \
  --http-port=8069 \
  --no-database-list \
  -d "${DB}" \
  --without-demo=all \
  --dev=none \
  --workers=0 \
  2>/dev/null || true

echo "  → Waiting 20 s for Odoo to be ready..."
sleep 20

# ── 3. POST the proven HOT body ──────────────────────────────────────────────
echo "  → POSTing cognito_hot.json..."
RESPONSE=$(curl -s -w "\n%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${BEARER}" \
  "http://127.0.0.1:${PORT}/api/v1/cognito-webhook" \
  --data-binary @"${PAYLOAD}")

HTTP_CODE=$(echo "${RESPONSE}" | tail -1)
BODY=$(echo "${RESPONSE}" | sed '$d')

echo "${BODY}" > "${RESULT_FILE}"
echo "  HTTP ${HTTP_CODE}"

if [ "${HTTP_CODE}" != "200" ]; then
  echo "  ❌ Gate 5 FAILED: HTTP ${HTTP_CODE}" | tee -a "${RESULT_FILE}"
  docker stop "odoo_rehearsal_${PORT}" 2>/dev/null || true
  exit 1
fi

DECISION=$(echo "${BODY}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('decision','?'))")
INTAKE_ID=$(echo "${BODY}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('intake_id',''))")
LEAD_ID=$(echo "${BODY}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('lead_id',''))")
WEB_LEAD_ID=$(echo "${BODY}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('web_lead_id',''))")

echo "  decision=${DECISION}  intake_id=${INTAKE_ID}  lead_id=${LEAD_ID}  web_lead_id=${WEB_LEAD_ID}"

if [ "${DECISION}" != "HOT" ]; then
  echo "  ❌ Gate 5 FAILED: decision=${DECISION} (expected HOT). Do not mock evaluate_economic_opportunity." | tee -a "${RESULT_FILE}"
  docker stop "odoo_rehearsal_${PORT}" 2>/dev/null || true
  exit 1
fi

if [ -z "${INTAKE_ID}" ] || [ "${INTAKE_ID}" = "None" ] || [ "${INTAKE_ID}" = "null" ]; then
  echo "  ❌ Gate 5 FAILED: intake_id is empty." | tee -a "${RESULT_FILE}"
  docker stop "odoo_rehearsal_${PORT}" 2>/dev/null || true
  exit 1
fi

if [ -z "${LEAD_ID}" ] || [ "${LEAD_ID}" = "None" ] || [ "${LEAD_ID}" = "null" ]; then
  echo "  ❌ Gate 5 FAILED: lead_id is empty (crm.lead not created)." | tee -a "${RESULT_FILE}"
  docker stop "odoo_rehearsal_${PORT}" 2>/dev/null || true
  exit 1
fi

# ── 4. Idempotency check: POST the same body again ──────────────────────────
echo "  → Idempotency: POSTing same body again..."
RESPONSE2=$(curl -s -w "\n%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${BEARER}" \
  "http://127.0.0.1:${PORT}/api/v1/cognito-webhook" \
  --data-binary @"${PAYLOAD}")
HTTP_CODE2=$(echo "${RESPONSE2}" | tail -1)
BODY2=$(echo "${RESPONSE2}" | sed '$d')
if [ "${HTTP_CODE2}" != "200" ]; then
  echo "  ❌ Gate 5 FAILED: idempotency POST returned HTTP ${HTTP_CODE2}" | tee -a "${RESULT_FILE}"
  docker stop "odoo_rehearsal_${PORT}" 2>/dev/null || true
  exit 1
fi
WEB_LEAD_ID2=$(echo "${BODY2}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('web_lead_id',''))")

if [ "${WEB_LEAD_ID}" != "${WEB_LEAD_ID2}" ]; then
  echo "  ❌ Gate 5 FAILED: idempotency broken — web_lead_id changed on second POST (${WEB_LEAD_ID} != ${WEB_LEAD_ID2})."
  docker stop "odoo_rehearsal_${PORT}" 2>/dev/null || true
  exit 1
fi
echo "  ✅ Idempotency: same web_lead_id=${WEB_LEAD_ID} on second POST"

# ── 5. Stop rehearsal HTTP ───────────────────────────────────────────────────
docker stop "odoo_rehearsal_${PORT}" 2>/dev/null || true

echo "  ✅ Gate 5 PASSED: HOT lead → intake=${INTAKE_ID} → crm.lead=${LEAD_ID}"
echo "  Wired end: crm.lead created. Blockers beyond this end: see expected/blockers.yaml"
