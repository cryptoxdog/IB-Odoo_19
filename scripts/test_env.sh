#!/usr/bin/env bash
# Pristine Odoo test environment — enterprise + custom modules, no demo data.
#
# The full module set installs once into a TEMPLATE database. Every test run
# then clones that template with CREATE DATABASE ... TEMPLATE (seconds), so
# agents test on a fresh, production-parity database instead of rebuilding one.
#
# The template is keyed by a fingerprint of config/odoo_module_order.yaml and
# every __manifest__.py in the repo (stored as the template's database
# comment). A changed module list or version rebuilds the template.
#
# Usage:
#   scripts/test_env.sh template            # build or refresh odoo_test_template
#   scripts/test_env.sh clone [db_name]     # fresh clone (default: $ODOO_TEST_DB or odoo_test)
#   scripts/test_env.sh status              # template fingerprint vs working tree
#
# Env: ODOO_COMPOSE_PROJECT (odoo19), POSTGRES_USER (odoo), ODOO_TEST_TEMPLATE_DB
# (odoo_test_template), ODOO_ENTERPRISE_MODULES (list, or `none`),
# ODOO_ENTERPRISE_PATH (host dir mounted as /mnt/enterprise; default ./odoo-enterprise —
# worktrees and secondary clones point it at the one checkout that has it).
#
# Fail-closed: the build refuses to start without an enterprise checkout and
# refuses to publish a template in which any requested module is not installed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$ROOT/.env"
  set +a
fi

POSTGRES_USER="${POSTGRES_USER:-odoo}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-odoo}"
PROJECT="${ODOO_COMPOSE_PROJECT:-odoo19}"
TEMPLATE_DB="${ODOO_TEST_TEMPLATE_DB:-odoo_test_template}"
DEFAULT_CLONE="${ODOO_TEST_DB:-odoo_test}"
export ODOO_ENTERPRISE_PATH="${ODOO_ENTERPRISE_PATH:-./odoo-enterprise}"

compose() { docker compose -p "$PROJECT" "$@"; }
psql_admin() { compose exec -T db psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -tAc "$1"; }

ensure_db_service() {
  if ! compose ps db --status running 2>/dev/null | grep -q running; then
    compose up -d db >/dev/null
  fi
  for _ in $(seq 1 30); do
    compose exec -T db pg_isready -U "$POSTGRES_USER" -d postgres >/dev/null 2>&1 && return 0
    sleep 1
  done
  echo "❌ PostgreSQL did not become ready" >&2
  exit 1
}

fingerprint() {
  { cat config/odoo_module_order.yaml; cat plasticos_*/__manifest__.py; echo "enterprise=${ODOO_ENTERPRISE_MODULES:-default}"; } \
    | shasum -a 256 | cut -c1-16
}

template_fingerprint() {
  psql_admin "SELECT coalesce(shobj_description(oid, 'pg_database'), '') FROM pg_database WHERE datname = '$TEMPLATE_DB'" 2>/dev/null || true
}

module_list() {
  local custom enterprise
  custom="$(python3 scripts/get_odoo_module_order.py)"
  enterprise="${ODOO_ENTERPRISE_MODULES:-$(python3 scripts/get_odoo_module_order.py --section docker_enterprise_modules)}"
  if [ -n "$enterprise" ] && [ "$enterprise" != "none" ]; then
    echo "${enterprise},${custom}"
  else
    echo "$custom"
  fi
}

enterprise_wanted() {
  [ "${ODOO_ENTERPRISE_MODULES:-x}" != "none" ]
}

require_enterprise_checkout() {
  enterprise_wanted || return 0
  if [ ! -f "$ODOO_ENTERPRISE_PATH/account_accountant/__manifest__.py" ]; then
    echo "❌ No Odoo Enterprise checkout at ODOO_ENTERPRISE_PATH=$ODOO_ENTERPRISE_PATH" >&2
    echo "   Staging runs enterprise; a template built without it is not a valid test environment." >&2
    echo "   Point ODOO_ENTERPRISE_PATH at a checkout (e.g. the main clone's odoo-enterprise/)" >&2
    echo "   or set ODOO_ENTERPRISE_MODULES=none to build a community-only template deliberately." >&2
    exit 1
  fi
}

# Odoo silently ignores unknown module names in -i, so installation is
# verified against ir_module_module rather than trusted.
missing_modules() {
  compose exec -T db psql -U "$POSTGRES_USER" -d "$TEMPLATE_DB" -tAc \
    "SELECT string_agg(m, ', ' ORDER BY m) FROM unnest(string_to_array('$1', ',')) AS m
     WHERE m NOT IN (SELECT name FROM ir_module_module WHERE state = 'installed')" 2>/dev/null || echo "(unreadable)"
}

assert_modules_installed() {
  local missing
  missing="$(missing_modules "$1")"
  if [ -n "$missing" ]; then
    echo "❌ template build left modules uninstalled: $missing" >&2
    drop_db "$TEMPLATE_DB"
    exit 1
  fi
}

drop_db() {
  psql_admin "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$1' AND pid <> pg_backend_pid()" >/dev/null
  psql_admin "DROP DATABASE IF EXISTS \"$1\"" >/dev/null
}

build_template() {
  local want modules
  want="$(fingerprint)"
  modules="$(module_list)"
  if [ "$(template_fingerprint)" = "$want" ]; then
    local missing
    missing="$(missing_modules "$modules")"
    if [ -z "$missing" ]; then
      echo "✅ $TEMPLATE_DB is current (fingerprint $want)"
      return 0
    fi
    echo "⚠️  $TEMPLATE_DB carries the current fingerprint but lacks: $missing — rebuilding"
  fi
  require_enterprise_checkout
  echo "→ Building $TEMPLATE_DB (fingerprint $want)"
  echo "  enterprise: $ODOO_ENTERPRISE_PATH"
  echo "  modules: $modules"
  drop_db "$TEMPLATE_DB"
  # The odoo service mounts ./config as /etc/odoo, so addons_path (incl. the
  # enterprise tier) is read from odoo.conf even though the command is replaced.
  compose run --rm odoo odoo -d "$TEMPLATE_DB" \
    --db_host=db --db_port=5432 --db_user="$POSTGRES_USER" --db_password="$POSTGRES_PASSWORD" \
    -i "$modules" --without-demo=all --stop-after-init --workers=0 --max-cron-threads=0 --log-level=warn
  # A fresh install loads the generic chart template after plasticos_accounting,
  # which drops the PlasticOS chart seed (40050/50100/50200 ...). Re-seed it so
  # the template matches an upgraded Staging database.
  compose run --rm odoo odoo -d "$TEMPLATE_DB" \
    --db_host=db --db_port=5432 --db_user="$POSTGRES_USER" --db_password="$POSTGRES_PASSWORD" \
    -u plasticos_accounting --stop-after-init --workers=0 --max-cron-threads=0 --log-level=warn
  assert_modules_installed "$modules"
  local installed accounts
  installed="$(compose exec -T db psql -U "$POSTGRES_USER" -d "$TEMPLATE_DB" -tAc "SELECT count(*) FROM ir_module_module WHERE state = 'installed'")"
  accounts="$(compose exec -T db psql -U "$POSTGRES_USER" -d "$TEMPLATE_DB" -tAc "SELECT count(*) FROM ir_model_data WHERE module = 'plasticos_accounting' AND model = 'account.account'")"
  if [ "${accounts:-0}" -lt 1 ]; then
    echo "❌ template build left no plasticos_accounting accounts" >&2
    exit 1
  fi
  psql_admin "COMMENT ON DATABASE \"$TEMPLATE_DB\" IS '$want'" >/dev/null
  echo "✅ $TEMPLATE_DB ready: $installed modules installed, $accounts PlasticOS accounts seeded"
}

clone_template() {
  local target="$1"
  if [ -z "$(template_fingerprint)" ]; then
    build_template
  elif [ "$(template_fingerprint)" != "$(fingerprint)" ]; then
    echo "⚠️  $TEMPLATE_DB is stale (module list or a manifest changed); rebuilding"
    build_template
  fi
  drop_db "$target"
  psql_admin "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$TEMPLATE_DB' AND pid <> pg_backend_pid()" >/dev/null
  psql_admin "CREATE DATABASE \"$target\" TEMPLATE \"$TEMPLATE_DB\"" >/dev/null
  echo "✅ $target is a pristine clone of $TEMPLATE_DB"
}

ensure_db_service
case "${1:-}" in
  template) build_template ;;
  clone) clone_template "${2:-$DEFAULT_CLONE}" ;;
  status)
    echo "working tree fingerprint: $(fingerprint)"
    echo "template fingerprint:     $(template_fingerprint)"
    ;;
  *)
    echo "usage: $0 template | clone [db_name] | status" >&2
    exit 2
    ;;
esac
