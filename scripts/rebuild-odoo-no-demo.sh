#!/usr/bin/env bash
# Rebuild Odoo database from scratch with NO demo/dummy data.
# Drops the target database, then installs all modules (enterprise + custom)
# in one pass using the odoo-test service from docker-compose.yml.
#
# docker-compose.yml is the source of truth for addons paths and volumes:
#   - /mnt/extra-addons  → repo root (custom plasticos_* modules)
#   - /mnt/enterprise    → ./odoo-enterprise (Enterprise modules, parity with Odoo.sh)
#   - Odoo core          → /usr/lib/python3/dist-packages/odoo/addons (baked into image)
#
# Configuration: from .env (see .env.example). Fallbacks used if .env missing.
# Usage: ./scripts/rebuild-odoo-no-demo.sh [database_name]
#
# Set ODOO_REBUILD_MODULES to override the default module list.
# Set ODOO_ENTERPRISE_MODULES=none to skip enterprise modules (faster, less parity).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Load .env if present
if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$ROOT/.env"
  set +a
fi

POSTGRES_USER="${POSTGRES_USER:-odoo}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-odoo}"
POSTGRES_DB="${POSTGRES_DB:-odoo}"
ODOO_DB_HOST="${ODOO_DB_HOST:-db}"
ODOO_DB_PORT="${ODOO_DB_PORT:-5432}"
ODOO_COMPOSE_PROJECT="${ODOO_COMPOSE_PROJECT:-odoo19}"
ODOO_DB_NAME_DEFAULT="${ODOO_DB_NAME:-odoo}"

DB_NAME="${1:-$ODOO_DB_NAME_DEFAULT}"

# --- Module lists (from config/odoo_module_order.yaml) ----------------------

_CUSTOM="$(python3 "$ROOT/scripts/get_odoo_module_order.py" 2>/dev/null)"
CUSTOM_MODULES="${ODOO_REBUILD_MODULES:-${_CUSTOM:-plasticos_accounting,plasticos_base,plasticos_material_profile,plasticos_logistics,plasticos_facility_profile,plasticos_intake,plasticos_product,plasticos_order_lines,plasticos_transaction,plasticos_documents,plasticos_offer,plasticos_claims,plasticos_automation,plasticos_intake_normalizer,plasticos_partner_import,plasticos_geolocalize,plasticos_security_base}}"

_ENTERPRISE="$(python3 "$ROOT/scripts/get_odoo_module_order.py" --section docker_enterprise_modules 2>/dev/null)"
ENTERPRISE_MODULES="${ODOO_ENTERPRISE_MODULES:-$_ENTERPRISE}"

# Combine into one list — Odoo handles dependency ordering internally
if [ -n "$ENTERPRISE_MODULES" ] && [ "$ENTERPRISE_MODULES" != "none" ]; then
  ALL_MODULES="${ENTERPRISE_MODULES},${CUSTOM_MODULES}"
else
  ALL_MODULES="${CUSTOM_MODULES}"
fi

# ----------------------------------------------------------------------------

echo "Rebuilding '$DB_NAME' — no demo data"
echo "Modules: $ALL_MODULES"
echo ""

# Ensure DB is running
if ! docker compose -p "$ODOO_COMPOSE_PROJECT" ps db --status running 2>/dev/null | grep -q "running"; then
  echo "Starting PostgreSQL..."
  docker compose -p "$ODOO_COMPOSE_PROJECT" up -d db
  sleep 5
fi

echo "Waiting for PostgreSQL..."
for _ in {1..30}; do
  if docker compose -p "$ODOO_COMPOSE_PROJECT" exec -T db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" 2>/dev/null; then
    break
  fi
  sleep 1
done

echo "Dropping '$DB_NAME'..."
docker compose -p "$ODOO_COMPOSE_PROJECT" exec -T db psql -U "$POSTGRES_USER" -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" 2>/dev/null || true
sleep 1
docker compose -p "$ODOO_COMPOSE_PROJECT" exec -T db psql -U "$POSTGRES_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS \"$DB_NAME\";" 2>/dev/null || true

# Single install pass — addons-path, volumes, and enterprise mount are defined
# in docker-compose.yml; no overrides needed here.
echo "Installing modules..."
docker compose -p "$ODOO_COMPOSE_PROJECT" run --rm \
  odoo-test \
  -d "$DB_NAME" \
  --db_host="$ODOO_DB_HOST" \
  --db_port="$ODOO_DB_PORT" \
  --db_user="$POSTGRES_USER" \
  --db_password="$POSTGRES_PASSWORD" \
  -i "$ALL_MODULES" \
  --without-demo=all \
  --log-level=info \
  --stop-after-init

echo ""
echo "Done. '$DB_NAME' is ready."
echo "Start Odoo: docker compose -p $ODOO_COMPOSE_PROJECT up odoo"
