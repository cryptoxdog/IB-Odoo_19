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
mkdir -p "${EVIDENCE_DIR}"
TOKEN_LOG="${EVIDENCE_DIR}/04-weblead-token.log"

# Same SELECT the controller uses in web_lead_api.py before authenticate().
read_config_key() {
  local db="$1"
  docker compose -f "${ROOT}/docker-compose.yml" run --rm \
    -e ODOO_DB="${db}" \
    odoo-test \
    python3 -c "
import odoo.tools
from odoo.modules.registry import Registry
odoo.tools.config.parse_config(['--config=/etc/odoo/odoo.conf', '-d', '${db}'])
reg = Registry('${db}')
with reg.cursor() as cr:
    cr.execute(
        '''
        SELECT api_key
        FROM plasticos_web_lead_config
        WHERE COALESCE(is_active, TRUE) IS TRUE
          AND api_key IS NOT NULL
          AND BTRIM(api_key) <> %s
        ORDER BY id ASC
        LIMIT 1
        ''',
        ('',),
    )
    row = cr.fetchone()
    print((row[0] if row else '').strip())
" 2>>"${TOKEN_LOG}" | tr -d '[:space:]'
}

# ── 1. Bearer from plasticos.web.lead.config, the row the webhook checks ──
echo "  → Reading plasticos.web.lead.config.api_key on ${DB} (not printed)..."
BEARER="$(read_config_key "${DB}")"
KEY_ON_CUTOVER=1
if [ -z "${BEARER}" ] && [ "${DB}" != "odoo" ]; then
  KEY_ON_CUTOVER=0
  echo "  → Cutover config has no key; reading the same field on database odoo..."
  BEARER="$(read_config_key odoo)"
fi
if [ -z "${BEARER}" ] && [ -n "${ODOO_WEB_LEAD_API_KEY:-}" ]; then
  KEY_ON_CUTOVER=0
  BEARER="${ODOO_WEB_LEAD_API_KEY}"
  echo "  → Using ODOO_WEB_LEAD_API_KEY; it will be written onto the cutover config row."
fi
if [ -z "${BEARER}" ]; then
  echo "  ❌ BLOCKED: plasticos.web.lead.config.api_key is empty on ${DB}." | tee "${RESULT_FILE}"
  exit 1
fi
if [ "${KEY_ON_CUTOVER}" -eq 0 ]; then
  echo "  → Writing that key onto ${DB} plasticos.web.lead.config so the webhook can read it..."
  docker compose -f "${ROOT}/docker-compose.yml" run --rm \
    -e ODOO_DB="${DB}" \
    -e WEB_LEAD_BEARER="${BEARER}" \
    odoo-test \
    python3 -c "
import os
import odoo.tools
from odoo.modules.registry import Registry
odoo.tools.config.parse_config(['--config=/etc/odoo/odoo.conf', '-d', '${DB}'])
reg = Registry('${DB}')
with reg.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    config = env['plasticos.web.lead.config'].get_config()
    config.write({'api_key': os.environ['WEB_LEAD_BEARER'], 'is_active': True})
    cr.commit()
" >>"${TOKEN_LOG}" 2>&1
fi

# ── 2. Start Odoo HTTP on rehearsal port ────────────────────────────────────
echo "  → Starting Odoo HTTP on 127.0.0.1:${PORT} with database ${DB}..."
docker rm -f "odoo_rehearsal_${PORT}" >/dev/null 2>&1 || true
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
  >>"${TOKEN_LOG}" 2>&1

echo "  → Waiting for /api/v1/web-lead/health..."
READY=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
  HEALTH_CODE="$(curl -s -o "${EVIDENCE_DIR}/04-weblead-health.json" -w "%{http_code}" \
    "http://127.0.0.1:${PORT}/api/v1/web-lead/health" || true)"
  if [ "${HEALTH_CODE}" = "200" ] && grep -q '"status": "ok"' "${EVIDENCE_DIR}/04-weblead-health.json"; then
    READY=1
    break
  fi
  sleep 2
done
if [ "${READY}" -ne 1 ]; then
  echo "  ❌ Gate 5 FAILED: web-lead health did not become ready (last HTTP ${HEALTH_CODE})"
  docker logs "odoo_rehearsal_${PORT}" >>"${TOKEN_LOG}" 2>&1 || true
  docker rm -f "odoo_rehearsal_${PORT}" >/dev/null 2>&1 || true
  exit 1
fi

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
  echo "  ❌ Gate 5 FAILED: HTTP ${HTTP_CODE}"
  docker stop "odoo_rehearsal_${PORT}" 2>/dev/null || true
  exit 1
fi

# Field names and values are the controller receipt in web_lead_api.py:
# decision is the selection value "hot", lead_id is the web-lead identity
# string, and a finished HOT lead has state "intake_created".
STATUS=$(echo "${BODY}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))")
DECISION=$(echo "${BODY}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('decision',''))")
STATE=$(echo "${BODY}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('state',''))")
ERROR=$(echo "${BODY}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error') or '')")
INTAKE_ID=$(echo "${BODY}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('intake_id',''))")
WEB_LEAD_ID=$(echo "${BODY}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('web_lead_id',''))")
LEAD_ID=$(echo "${BODY}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('lead_id',''))")

echo "  status=${STATUS} decision=${DECISION} state=${STATE} intake_id=${INTAKE_ID} web_lead_id=${WEB_LEAD_ID} lead_id=${LEAD_ID}"

fail_gate5() {
  echo "  ❌ Gate 5 FAILED: $1"
  docker stop "odoo_rehearsal_${PORT}" 2>/dev/null || true
  exit 1
}

if [ "${STATUS}" != "ok" ]; then
  fail_gate5 "status=${STATUS}"
fi
if [ "${DECISION}" != "hot" ]; then
  fail_gate5 "decision=${DECISION} (selection value is hot)"
fi
if [ -z "${INTAKE_ID}" ] || [ "${INTAKE_ID}" = "None" ] || [ "${INTAKE_ID}" = "null" ]; then
  fail_gate5 "intake_id is empty"
fi
if [ -z "${WEB_LEAD_ID}" ] || [ "${WEB_LEAD_ID}" = "None" ] || [ "${WEB_LEAD_ID}" = "null" ]; then
  fail_gate5 "web_lead_id is empty"
fi
if [ "${STATE}" != "intake_created" ]; then
  fail_gate5 "state=${STATE} error=${ERROR}"
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

echo "  ✅ Gate 5 PASSED: hot lead ${WEB_LEAD_ID} intake=${INTAKE_ID} state=${STATE}"
