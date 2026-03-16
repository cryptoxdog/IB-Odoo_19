#!/usr/bin/env bash
# PlasticOS Odoo 19 — Docker Diagnostic Script
# Mode: READ-ONLY TRIAGE — NO CODE CHANGES
# Run when Docker daemon is running: ./scripts/docker-diagnostic-plasticos.sh

set -euo pipefail

LOG="${LOG:-/tmp/plasticos-diagnostic-$(date +%Y%m%d-%H%M%S).log}"
exec > >(tee -a "$LOG") 2>&1

echo "=== PlasticOS Odoo 19 Diagnostic — $(date -Iseconds) ==="
echo "Log: $LOG"
echo ""

# --- PHASE 0: Resolve container names ---
echo "--- PHASE 0: Resolve container names ---"
PS_OUT=$(docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "odoo|postgres|db" || true)
echo "$PS_OUT"

ODOO_CONTAINER=$(echo "$PS_OUT" | grep -E "odoo19-odoo|odoo" | head -1 | awk '{print $1}')
DB_CONTAINER=$(echo "$PS_OUT" | grep -E "odoo19-db|postgres|db" | head -1 | awk '{print $1}')

if [[ -z "$ODOO_CONTAINER" ]] || [[ -z "$DB_CONTAINER" ]]; then
  echo "ERROR: Could not resolve ODOO_CONTAINER or DB_CONTAINER. Is docker-compose -p odoo19 up?"
  echo "ODOO_CONTAINER=$ODOO_CONTAINER DB_CONTAINER=$DB_CONTAINER"
  exit 1
fi

echo "ODOO_CONTAINER=$ODOO_CONTAINER"
echo "DB_CONTAINER=$DB_CONTAINER"
echo ""

# --- PHASE 1: Live log snapshot ---
echo "--- PHASE 1: Live log snapshot (real errors only) ---"
docker logs "$ODOO_CONTAINER" --tail=500 2>&1 \
  | grep -E "ERROR|WARNING|ValueError|Field|cannot|ImportError|KeyError|AttributeError|SyntaxError|Cannot find|invalid field|Unknown field|not found" \
  | grep -v "werkzeug\|assets\|bundle\|font\|css\|js\|Less\|QWeb cache" || true
echo ""

# --- PHASE 2: Module install state ---
echo "--- PHASE 2: Module install state ---"
docker exec "$DB_CONTAINER" psql -U odoo -d odoo -c \
  "SELECT name, state, latest_version FROM ir_module_module WHERE name LIKE 'plasticos%' ORDER BY name;" || true
echo ""

# --- PHASE 3: Broken views ---
echo "--- PHASE 3: Broken views (null/empty arch) ---"
docker exec "$DB_CONTAINER" psql -U odoo -d odoo -c \
  "SELECT v.name, v.model, v.type, v.active, m.name as module
   FROM ir_ui_view v
   LEFT JOIN ir_model_data d ON d.res_id = v.id AND d.model = 'ir.ui.view'
   LEFT JOIN ir_module_module m ON m.id = (
     SELECT module_id FROM ir_model_data WHERE res_id = v.id AND model = 'ir.ui.view' LIMIT 1
   )
   WHERE v.active = true
     AND (v.arch_db IS NULL OR length(v.arch_db::text) < 10)
   ORDER BY m.name, v.model;" 2>/dev/null || true
echo ""

# --- PHASE 4: Missing fields cross-check ---
echo "--- PHASE 4a: plasticos.intake.match ---"
docker exec "$DB_CONTAINER" psql -U odoo -d odoo -c \
  "SELECT name, ttype, required FROM ir_model_fields WHERE model = 'plasticos.intake.match' ORDER BY name;" 2>/dev/null || true
echo ""

echo "--- PHASE 4b: plasticos.offer ---"
docker exec "$DB_CONTAINER" psql -U odoo -d odoo -c \
  "SELECT name, ttype, required FROM ir_model_fields WHERE model = 'plasticos.offer' ORDER BY name;" 2>/dev/null || true
echo ""

echo "--- PHASE 4c: plasticos.transaction ---"
docker exec "$DB_CONTAINER" psql -U odoo -d odoo -c \
  "SELECT name, ttype, required FROM ir_model_fields WHERE model = 'plasticos.transaction' ORDER BY name;" 2>/dev/null || true
echo ""

echo "--- PHASE 4d: plasticos.web.lead ---"
docker exec "$DB_CONTAINER" psql -U odoo -d odoo -c \
  "SELECT name, ttype, required FROM ir_model_fields WHERE model = 'plasticos.web.lead' ORDER BY name;" 2>/dev/null || true
echo ""

echo "--- PHASE 4e: plasticos.enrichment.run ---"
docker exec "$DB_CONTAINER" psql -U odoo -d odoo -c \
  "SELECT name, ttype, required FROM ir_model_fields WHERE model = 'plasticos.enrichment.run' ORDER BY name;" 2>/dev/null || true
echo ""

# --- PHASE 5: ACL gaps ---
echo "--- PHASE 5: ACL gaps (models with no access rules) ---"
docker exec "$DB_CONTAINER" psql -U odoo -d odoo -c \
  "SELECT m.model FROM ir_model m
   WHERE m.model LIKE 'plasticos.%'
     AND m.model NOT IN (
       SELECT im.model FROM ir_model_access ima
       JOIN ir_model im ON im.id = ima.model_id
     )
   ORDER BY m.model;" 2>/dev/null || true
echo ""

# --- PHASE 6: Python import health ---
echo "--- PHASE 6: Python import health ---"
docker exec "$ODOO_CONTAINER" python3 -c "
import sys
sys.path.insert(0, '/mnt/extra-addons')
mods = [
    'plasticos_intake.models.intake',
    'plasticos_intake.models.intake_match',
    'plasticos_offer.models.offer',
    'plasticos_transaction.models.transaction',
    'plasticos_matching.models.match_result',
    'plasticos_enrichment.models.enrichment_source',
    'plasticos_web_leads.models.web_lead',
]
for m in mods:
    try:
        __import__(m)
        print(f'OK      {m}')
    except Exception as e:
        print(f'FAIL    {m}: {e}')
" 2>&1 || true
echo ""

# --- PHASE 7: Config hardening ---
echo "--- PHASE 7: Config snapshot ---"
docker exec "$ODOO_CONTAINER" cat /etc/odoo/odoo.conf 2>/dev/null \
  || docker exec "$ODOO_CONTAINER" cat /mnt/config/odoo.conf 2>/dev/null \
  || docker exec "$ODOO_CONTAINER" find / -name "odoo.conf" 2>/dev/null | head -3 || true
echo ""

# --- PHASE 8: Scheduled action health ---
echo "--- PHASE 8: Scheduled action health ---"
docker exec "$DB_CONTAINER" psql -U odoo -d odoo -c \
  "SELECT name, active, state, nextcall, numbercall, doall
   FROM ir_cron
   WHERE name ILIKE '%plasticos%' OR name ILIKE '%intake%' OR name ILIKE '%match%'
   ORDER BY active DESC, nextcall;" 2>/dev/null || true
echo ""

echo "=== Diagnostic complete. Review output above and update docs/cursor-briefs/PLASTICOS-DOCKER-DIAGNOSTIC-REPORT-*.md ==="
