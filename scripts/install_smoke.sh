#!/usr/bin/env bash
# Local Odoo install-smoke gate — fail closed before GitHub.
#
# Builds the Docker image (xmlsec + requirements), ensures enterprise addons
# are available, drops a dedicated DB, installs the configured module set with
# --stop-after-init, and exits non-zero on install failure or ERROR/CRITICAL/
# Traceback in the log.
#
# Usage:
#   ./scripts/install_smoke.sh
#   ODOO_ENTERPRISE_MODULES=none ./scripts/install_smoke.sh   # custom-only (faster)
#   make install-smoke
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$ROOT/.env"
  set +a
fi

export PATH="/usr/local/bin:/opt/homebrew/bin:${PATH}"

POSTGRES_USER="${POSTGRES_USER:-odoo}"
POSTGRES_DB="${POSTGRES_DB:-odoo}"
ODOO_DB_HOST="${ODOO_DB_HOST:-db}"
ODOO_DB_PORT="${ODOO_DB_PORT:-5432}"
ODOO_COMPOSE_PROJECT="${ODOO_COMPOSE_PROJECT:-odoo19}"
SMOKE_DB="${ODOO_INSTALL_SMOKE_DB:-odoo_install_smoke}"
LOG_DIR="${ODOO_INSTALL_SMOKE_LOG_DIR:-/tmp}"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/odoo-install-smoke-$(date +%Y%m%d_%H%M%S).log"

# Never embed a password literal here (GitGuardian). Prefer env/.env; else the
# compose `db` service definition already used by local Docker.
if [ -z "${POSTGRES_PASSWORD:-}" ]; then
  # Ignore compose failures here (daemon down) — fall through to the unset check.
  # Use python -c (stdin only): pipe + heredoc trips shellcheck SC2259.
  set +e
  POSTGRES_PASSWORD="$(
    docker compose -p "$ODOO_COMPOSE_PROJECT" config 2>/dev/null | python3 -c "
import re
import sys

text = sys.stdin.read()
match = re.search(r'(?ms)^  db:\n(.*?)(?=^  [a-zA-Z]|\Z)', text)
block = match.group(1) if match else text
pwd = re.search(r'POSTGRES_PASSWORD:\s*(.+)', block)
print(pwd.group(1).strip().strip(chr(34) + chr(39)) if pwd else '', end='')
"
  )"
  set -e
fi
if [ -z "${POSTGRES_PASSWORD:-}" ]; then
  echo "❌ POSTGRES_PASSWORD is unset. Export it or put it in .env (see .env.example)." >&2
  echo "   (Also ensure Docker is running if you rely on compose defaults.)" >&2
  exit 1
fi

# --- Enterprise mount -------------------------------------------------------
if [ ! -e "$ROOT/odoo-enterprise" ]; then
  CANDIDATE="${ODOO_ENTERPRISE_PATH:-$HOME/Dropbox/Repo_Dropbox_IB/IB-Odoo_19/odoo-enterprise}"
  if [ -d "$CANDIDATE" ]; then
    ln -s "$CANDIDATE" "$ROOT/odoo-enterprise"
    echo "→ Linked odoo-enterprise → $CANDIDATE"
  else
    echo "❌ odoo-enterprise missing. Symlink local enterprise addons:" >&2
    echo "   ln -s \"\$HOME/Dropbox/Repo_Dropbox_IB/IB-Odoo_19/odoo-enterprise\" odoo-enterprise" >&2
    exit 1
  fi
fi

# --- Module lists ------------------------------------------------------------
# Default: ordered core + every other installable plasticos_* (minus excluded).
# Override with ODOO_REBUILD_MODULES=... or ODOO_INSTALL_SMOKE_SCOPE=ordered.
_SCOPE="${ODOO_INSTALL_SMOKE_SCOPE:-all}"
if [ "$_SCOPE" = "ordered" ]; then
  _CUSTOM="$(python3 "$ROOT/scripts/get_odoo_module_order.py" 2>/dev/null || true)"
else
  _CUSTOM="$(python3 "$ROOT/scripts/get_odoo_module_order.py" --all-installable 2>/dev/null || true)"
fi
CUSTOM_MODULES="${ODOO_REBUILD_MODULES:-${_CUSTOM}}"
if [ -z "$CUSTOM_MODULES" ]; then
  echo "❌ Could not resolve custom module list from config/odoo_module_order.yaml" >&2
  exit 1
fi

_ENTERPRISE="$(python3 "$ROOT/scripts/get_odoo_module_order.py" --section docker_enterprise_modules 2>/dev/null || true)"
ENTERPRISE_MODULES="${ODOO_ENTERPRISE_MODULES:-${_ENTERPRISE:-none}}"

if [ -n "$ENTERPRISE_MODULES" ] && [ "$ENTERPRISE_MODULES" != "none" ]; then
  ALL_MODULES="${ENTERPRISE_MODULES},${CUSTOM_MODULES}"
else
  ALL_MODULES="${CUSTOM_MODULES}"
fi

echo "════════════════════════════════════════════════════════"
echo " Odoo install-smoke"
echo " DB:       $SMOKE_DB"
echo " Modules:  $ALL_MODULES"
echo " Log:      $LOG_FILE"
echo "════════════════════════════════════════════════════════"

# Static preflight — XML refs must match depends (catches logistics/security_base class)
python3 "$ROOT/ci/check_xml_module_ref_deps.py"

# DB up
if ! docker compose -p "$ODOO_COMPOSE_PROJECT" ps db --status running 2>/dev/null | grep -q "running"; then
  echo "→ Starting PostgreSQL..."
  docker compose -p "$ODOO_COMPOSE_PROJECT" up -d db
fi

echo "→ Waiting for PostgreSQL..."
PG_READY=0
for _ in $(seq 1 60); do
  if docker compose -p "$ODOO_COMPOSE_PROJECT" exec -T db \
    pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
    PG_READY=1
    break
  fi
  sleep 1
done
if [ "$PG_READY" -ne 1 ]; then
  echo "❌ PostgreSQL not ready after 60s (project=$ODOO_COMPOSE_PROJECT)" >&2
  exit 1
fi

# Rebuild image so xmlsec / requirements changes are present
echo "→ Building Odoo image (xmlsec + requirements)..."
docker compose -p "$ODOO_COMPOSE_PROJECT" build odoo-test

echo "→ Dropping smoke DB '$SMOKE_DB'..."
docker compose -p "$ODOO_COMPOSE_PROJECT" exec -T db psql -U "$POSTGRES_USER" -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$SMOKE_DB' AND pid <> pg_backend_pid();" \
  >/dev/null 2>&1 || true
docker compose -p "$ODOO_COMPOSE_PROJECT" exec -T db psql -U "$POSTGRES_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS \"$SMOKE_DB\";" >/dev/null

echo "→ Installing modules (--stop-after-init)..."
set +e
docker compose -p "$ODOO_COMPOSE_PROJECT" run --rm \
  odoo-test \
  -d "$SMOKE_DB" \
  --db_host="$ODOO_DB_HOST" \
  --db_port="$ODOO_DB_PORT" \
  --db_user="$POSTGRES_USER" \
  --db_password="$POSTGRES_PASSWORD" \
  -i "$ALL_MODULES" \
  --without-demo=all \
  --log-level=info \
  --stop-after-init 2>&1 | tee "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}
set -e

if [ "$EXIT_CODE" -ne 0 ]; then
  echo "" >&2
  echo "❌ install-smoke FAILED (odoo exit $EXIT_CODE)" >&2
  echo "   Log: $LOG_FILE" >&2
  exit "$EXIT_CODE"
fi

# Fail only on fatal install/registry failures — not application ERROR logs from
# post_init hooks (e.g. partner_import graph validation that does not abort load).
FATAL_PATTERNS='Failed to initialize database|ParseError|odoo\.registry: Failed to load registry|External ID not found|Invalid field'
if grep -E "$FATAL_PATTERNS" "$LOG_FILE" | grep -vE "test_|Undefined substitution|Unexpected indentation" | head -40; then
  echo "" >&2
  echo "❌ install-smoke FAILED: fatal install/registry error in log" >&2
  echo "   Log: $LOG_FILE" >&2
  exit 1
fi

# Verify key modules installed
echo "→ Verifying module states..."
FAIL=0
# Portable split (bash 3.2 / zsh-safe when invoked via bash)
OLD_IFS=$IFS
IFS=','
set -- $CUSTOM_MODULES
IFS=$OLD_IFS
for mod in "$@"; do
  mod="$(echo "$mod" | xargs)"
  [ -z "$mod" ] && continue
  STATE="$(docker compose -p "$ODOO_COMPOSE_PROJECT" exec -T db psql -U "$POSTGRES_USER" -d "$SMOKE_DB" -t -A -c \
    "SELECT state FROM ir_module_module WHERE name = '$mod';" 2>/dev/null | tr -d '\r' || true)"
  if [ "$STATE" = "installed" ]; then
    echo "  ✅ $mod"
  else
    echo "  ❌ $mod → '${STATE:-missing}' (expected installed)"
    FAIL=1
  fi
done

if [ "$FAIL" -ne 0 ]; then
  echo "❌ install-smoke FAILED: one or more custom modules not installed" >&2
  exit 1
fi

# Prove xmlsec import inside the image (enterprise parity)
echo "→ Proving xmlsec import in image..."
docker compose -p "$ODOO_COMPOSE_PROJECT" run --rm --entrypoint python3 odoo-test -c "import xmlsec; print('xmlsec', xmlsec.__version__)"

echo ""
echo "✅ install-smoke PASSED — safe to push (modules load cleanly)"
echo "   DB=$SMOKE_DB  log=$LOG_FILE"
