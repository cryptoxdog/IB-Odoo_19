#!/usr/bin/env bash
# Rebuild Odoo database from scratch with NO demo/dummy data (Option B).
# Drops the target database, then runs Odoo init with --without-demo=all.
# Use this for a clean slate (no preloaded contacts, users, companies).
#
# Configuration: from .env (see .env.example). Fallbacks used if .env missing.
# Usage: ./scripts/rebuild-odoo-no-demo.sh [database_name]
#
# Requires: Docker running, docker-compose project (ODOO_COMPOSE_PROJECT).
# After run: Start Odoo normally; the DB will be clean (no demo data).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Load .env if present (no hardcoded credentials or DB names)
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

# Module list: from ODOO_REBUILD_MODULES or default (topological order from config/odoo_module_order.yaml)
_DEFAULT_MODULES="$(python3 "$ROOT/scripts/get_odoo_module_order.py" 2>/dev/null)"
MODULES="${ODOO_REBUILD_MODULES:-${_DEFAULT_MODULES:-plasticos_accounting,plasticos_base,plasticos_material_profile,plasticos_inference_engine,plasticos_logistics,plasticos_facility_profile,plasticos_intake,plasticos_product,plasticos_transaction,plasticos_documents,plasticos_matching,plasticos_offer,plasticos_claims,plasticos_automation,plasticos_intake_normalizer,plasticos_buyer_match_engine,plasticos_partner_import,plasticos_geolocalize,plasticos_enrichment,plasticos_security_base}}"

echo "Rebuilding database '$DB_NAME' with NO demo data (--without-demo=all)"
echo "Modules: $MODULES"
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

echo "Dropping database '$DB_NAME'..."
docker compose -p "$ODOO_COMPOSE_PROJECT" exec -T db psql -U "$POSTGRES_USER" -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" 2>/dev/null || true
sleep 1
docker compose -p "$ODOO_COMPOSE_PROJECT" exec -T db psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$DB_NAME\";" 2>/dev/null || true

echo "Initializing '$DB_NAME' with modules (no demo data)..."
docker compose -p "$ODOO_COMPOSE_PROJECT" run --rm \
  -e MODULES="$MODULES" \
  odoo-test \
  --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
  -d "$DB_NAME" \
  --db_host="$ODOO_DB_HOST" \
  --db_port="$ODOO_DB_PORT" \
  --db_user="$POSTGRES_USER" \
  --db_password="$POSTGRES_PASSWORD" \
  -i "$MODULES" \
  --without-demo=all \
  --log-level=info \
  --stop-after-init

echo ""
echo "Done. Database '$DB_NAME' is ready with no demo data."
echo "To run Odoo against this DB, start your app with -d $DB_NAME and without -i (so it does not reinstall)."
