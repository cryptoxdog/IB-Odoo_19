#!/usr/bin/env bash
# Gate 5 — Web lead e2e: POST the proven HOT body, then read the clone back.
#
# Passing needs the controller receipt AND the stored chain: exactly one web
# lead, its intake, and one unassigned, non-Won crm.lead opportunity bound to
# that intake, no partner created, and a replay that changes nothing.
#
# Called by run.sh. Writes $EVIDENCE_DIR/gate-5.json (rehearsal_lib.py) and
# 04-weblead-*.json evidence. Exit 0 only on PASS.
# Usage: bash weblead_e2e.sh <plasticos_root> <db> <rehearsal_port> <evidence_dir>
set -uo pipefail
umask 077

ROOT="${1:?plasticos_root required}"
DB="${2:?db name required}"
PORT="${3:?rehearsal_port required}"
EVIDENCE_DIR="${4:?evidence_dir required}"
KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=rehearsal_common.sh source-path=SCRIPTDIR
. "${KIT_DIR}/rehearsal_common.sh"

PAYLOAD="${KIT_DIR}/payloads/cognito_hot.json"
RESULT_FILE="${EVIDENCE_DIR}/04-weblead-result.json"
REPLAY_FILE="${EVIDENCE_DIR}/04-weblead-replay.json"
RUNTIME_LOG="${EVIDENCE_DIR}/04-weblead-runtime.log"
CONTAINER="odoo_rehearsal_${PORT}"
STARTED=0
FINISHED=0
BEARER=""
PRIVATE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/rehearsal-weblead.XXXXXX")" || exit 1
HEADER_FILE="${PRIVATE_DIR}/auth.header"

mkdir -p "${EVIDENCE_DIR}"
echo "→ [Gate 5] Web lead e2e on ${DB}:${PORT}"

# Only this run's container and temp files are removed. A container that was
# already there is someone else's and is never touched.
# shellcheck disable=SC2329  # invoked by trap
cleanup() {
  if [ "${STARTED}" = "1" ]; then
    docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
    STARTED=0
  fi
  rm -rf "${PRIVATE_DIR}"
}
# shellcheck disable=SC2329  # invoked by trap
on_signal() {
  if [ "${FINISHED}" != "1" ]; then
    FINISHED=1
    cleanup
    rlib gate-write "${EVIDENCE_DIR}" 5 FAIL "interrupted" --detail "Gate 5 interrupted" --side-effects || true
  fi
  exit 130
}
trap cleanup EXIT
trap on_signal INT TERM

# finish <STATE> <reason> [detail] — scan evidence for the bearer, write the receipt, exit.
finish() {
  local state="$1" reason="$2" detail="${3:-}"
  cleanup
  if ! REHEARSAL_BEARER_SCAN="${BEARER}" rlib scan-secrets "${EVIDENCE_DIR}" --env REHEARSAL_BEARER_SCAN; then
    state="FAIL"
    reason="evidence-secret-redacted"
    detail="the web-lead bearer appeared in evidence and was redacted"
  fi
  FINISHED=1
  rlib gate-write "${EVIDENCE_DIR}" 5 "${state}" "${reason}" --detail "${detail}" --side-effects
  echo "  ❌ Gate 5 ${state}: ${reason}${detail:+ — ${detail}}"
  exit 1
}

fail_gate5() {
  finish FAIL "$1" "${2:-}"
}

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
" 2>>"${RUNTIME_LOG}" | tr -d '[:space:]'
}

# snapshot <out> — global counts the POSTs may change.
snapshot() {
  printf '%s\n' "SELECT json_build_object(
      'web_leads', (SELECT COUNT(*) FROM plasticos_web_lead),
      'intakes', (SELECT COUNT(*) FROM plasticos_intake),
      'crm_leads', (SELECT COUNT(*) FROM crm_lead),
      'partners', (SELECT COUNT(*) FROM res_partner));" | db_query "${DB}" "$1"
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
  fail_gate5 "weblead-key-missing" "plasticos.web.lead.config.api_key is empty on ${DB}"
fi
if [ "${KEY_ON_CUTOVER}" -eq 0 ]; then
  echo "  → Writing that key onto ${DB} plasticos.web.lead.config so the webhook can read it..."
  # `-e NAME` with no value: docker copies it from this process environment,
  # so the bearer never appears on argv.
  if ! WEB_LEAD_BEARER="${BEARER}" docker compose -f "${ROOT}/docker-compose.yml" run --rm \
    -e ODOO_DB="${DB}" \
    -e WEB_LEAD_BEARER \
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
" >>"${RUNTIME_LOG}" 2>&1; then
    fail_gate5 "weblead-key-write-failed" "the cutover config row was not updated"
  fi
fi
printf 'Authorization: Bearer %s\n' "${BEARER}" >"${HEADER_FILE}"

# ── 2. Start Odoo HTTP on the rehearsal port (this run's container only) ───
if docker container inspect "${CONTAINER}" >/dev/null 2>&1; then
  fail_gate5 "rehearsal-container-in-use" "container ${CONTAINER} already exists; it is not this run's to remove"
fi
if curl -s -o /dev/null --max-time 2 "http://127.0.0.1:${PORT}/" 2>/dev/null; then
  fail_gate5 "rehearsal-port-in-use" "127.0.0.1:${PORT} already answers"
fi
echo "  → Starting Odoo HTTP on 127.0.0.1:${PORT} with database ${DB}..."
if ! docker compose -f "${ROOT}/docker-compose.yml" run --rm -d \
  --name "${CONTAINER}" \
  -p "127.0.0.1:${PORT}:8069" \
  odoo-test \
  --http-port=8069 \
  --no-database-list \
  -d "${DB}" \
  --without-demo=all \
  --dev=none \
  --workers=0 \
  >>"${RUNTIME_LOG}" 2>&1; then
  fail_gate5 "rehearsal-http-start-failed" "docker compose run failed; see 04-weblead-runtime.log"
fi
STARTED=1

echo "  → Waiting for /api/v1/web-lead/health..."
READY=0
HEALTH_CODE=""
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
  docker logs "${CONTAINER}" >>"${RUNTIME_LOG}" 2>&1 || true
  fail_gate5 "weblead-health-not-ready" "last HTTP ${HEALTH_CODE}"
fi

# post_lead <out_body> — prints the HTTP code. The bearer is read by curl from
# a private header file, not passed on argv.
post_lead() {
  curl -s -o "$1" -w "%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "@${HEADER_FILE}" \
    "http://127.0.0.1:${PORT}/api/v1/cognito-webhook" \
    --data-binary @"${PAYLOAD}" || echo "000"
}

json_field() {
  python3 -c "import sys,json
try:
    d=json.load(open(sys.argv[1]))
except Exception:
    d={}
v=d.get(sys.argv[2]) if isinstance(d,dict) else None
print('' if v is None else v)" "$1" "$2"
}

# ── 3. Snapshot, then POST the proven HOT body ───────────────────────────────
snapshot "${EVIDENCE_DIR}/04-weblead-before.json" || fail_gate5 "weblead-snapshot-failed" "before-POST census failed"
echo "  → POSTing cognito_hot.json..."
HTTP_CODE="$(post_lead "${RESULT_FILE}")"
echo "  HTTP ${HTTP_CODE}"
if [ "${HTTP_CODE}" != "200" ]; then
  fail_gate5 "weblead-http-${HTTP_CODE}" "the webhook did not accept the HOT body"
fi

# Field names and values are the controller receipt in web_lead_api.py:
# decision is the selection value "hot", lead_id is the web-lead identity
# string, and a finished HOT lead has state "intake_created".
STATUS="$(json_field "${RESULT_FILE}" status)"
DECISION="$(json_field "${RESULT_FILE}" decision)"
STATE="$(json_field "${RESULT_FILE}" state)"
ERROR="$(json_field "${RESULT_FILE}" error)"
INTAKE_ID="$(json_field "${RESULT_FILE}" intake_id)"
WEB_LEAD_ID="$(json_field "${RESULT_FILE}" web_lead_id)"
LEAD_ID="$(json_field "${RESULT_FILE}" lead_id)"
echo "  status=${STATUS} decision=${DECISION} state=${STATE} intake_id=${INTAKE_ID} web_lead_id=${WEB_LEAD_ID} lead_id=${LEAD_ID}"

if [ "${STATUS}" != "ok" ]; then
  fail_gate5 "weblead-status" "status=${STATUS}"
fi
if [ "${DECISION}" != "hot" ]; then
  fail_gate5 "weblead-decision" "decision=${DECISION} (selection value is hot)"
fi
if [ -z "${INTAKE_ID}" ] || [ "${INTAKE_ID}" = "None" ] || [ "${INTAKE_ID}" = "null" ]; then
  fail_gate5 "weblead-intake-missing" "intake_id is empty"
fi
if [ -z "${WEB_LEAD_ID}" ] || [ "${WEB_LEAD_ID}" = "None" ] || [ "${WEB_LEAD_ID}" = "null" ]; then
  fail_gate5 "weblead-id-missing" "web_lead_id is empty"
fi
if [ "${STATE}" != "intake_created" ]; then
  fail_gate5 "weblead-state" "state=${STATE} error=${ERROR}"
fi
case "${WEB_LEAD_ID}" in
  *[!0-9]*) fail_gate5 "weblead-id-invalid" "web_lead_id is not an integer" ;;
esac
snapshot "${EVIDENCE_DIR}/04-weblead-after-first.json" || fail_gate5 "weblead-snapshot-failed" "after-POST census failed"

# ── 4. Idempotency: POST the same body again ─────────────────────────────────
echo "  → Idempotency: POSTing same body again..."
HTTP_CODE2="$(post_lead "${REPLAY_FILE}")"
if [ "${HTTP_CODE2}" != "200" ]; then
  fail_gate5 "weblead-replay-http-${HTTP_CODE2}" "idempotency POST was not accepted"
fi
snapshot "${EVIDENCE_DIR}/04-weblead-after-replay.json" || fail_gate5 "weblead-snapshot-failed" "after-replay census failed"

# ── 5. Read the stored chain back ─────────────────────────────────────────────
printf '%s\n' "\\set wl ${WEB_LEAD_ID}" "SELECT json_build_object(
  'web_lead', (SELECT row_to_json(w) FROM (
      SELECT id, lead_id, state, intake_id, crm_lead_id, partner_id
      FROM plasticos_web_lead WHERE id = :wl) w),
  'same_lead_id_rows', (SELECT COUNT(*) FROM plasticos_web_lead
      WHERE lead_id = (SELECT lead_id FROM plasticos_web_lead WHERE id = :wl)),
  'intake_exists', (SELECT COUNT(*) FROM plasticos_intake
      WHERE id = (SELECT intake_id FROM plasticos_web_lead WHERE id = :wl)),
  'crm_for_intake', (SELECT COUNT(*) FROM crm_lead
      WHERE source_intake_id = (SELECT intake_id FROM plasticos_web_lead WHERE id = :wl)),
  'crm', (SELECT row_to_json(c) FROM (
      SELECT l.id, l.type, l.user_id, l.partner_id, l.active, l.source_intake_id,
             COALESCE(s.is_won, FALSE) AS is_won
      FROM crm_lead l LEFT JOIN crm_stage s ON s.id = l.stage_id
      WHERE l.id = (SELECT crm_lead_id FROM plasticos_web_lead WHERE id = :wl)) c));" \
  | db_query "${DB}" "${EVIDENCE_DIR}/04-weblead-db.json" \
  || fail_gate5 "weblead-readback-failed" "the stored web lead, intake and crm.lead could not be read"

# ── 6. Stop HTTP, scan evidence, judge ───────────────────────────────────────
cleanup
if ! REHEARSAL_BEARER_SCAN="${BEARER}" rlib scan-secrets "${EVIDENCE_DIR}" --env REHEARSAL_BEARER_SCAN; then
  fail_gate5 "evidence-secret-redacted" "the web-lead bearer appeared in evidence and was redacted"
fi
FINISHED=1
rlib check-weblead "${EVIDENCE_DIR}" \
  --receipt "${RESULT_FILE}" \
  --replay "${REPLAY_FILE}" \
  --before "${EVIDENCE_DIR}/04-weblead-before.json" \
  --after-first "${EVIDENCE_DIR}/04-weblead-after-first.json" \
  --after-replay "${EVIDENCE_DIR}/04-weblead-after-replay.json" \
  --row "${EVIDENCE_DIR}/04-weblead-db.json"
