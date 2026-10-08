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
#   ODOO_INSTALL_SMOKE_NETWORK=host ./scripts/install_smoke.sh # sandbox bridge fallback
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

# Keep a caller-supplied docker (tests stub it) ahead of the Homebrew/system paths.
if ! command -v docker >/dev/null 2>&1; then
  export PATH="/usr/local/bin:/opt/homebrew/bin:${PATH}"
fi

POSTGRES_USER="${POSTGRES_USER:-odoo}"
POSTGRES_DB="${POSTGRES_DB:-odoo}"
SMOKE_NETWORK_MODE="${ODOO_INSTALL_SMOKE_NETWORK:-compose}"
case "$SMOKE_NETWORK_MODE" in
  compose)
    ODOO_DB_HOST="${ODOO_DB_HOST:-db}"
    ODOO_DB_PORT="${ODOO_DB_PORT:-5432}"
    ;;
  host)
    ODOO_DB_HOST="${ODOO_DB_HOST:-127.0.0.1}"
    ODOO_DB_PORT="${ODOO_DB_PORT:-5433}"
    ;;
  *)
    echo "❌ ODOO_INSTALL_SMOKE_NETWORK must be 'compose' or 'host' (got '$SMOKE_NETWORK_MODE')." >&2
    exit 2
    ;;
esac

# The only database this script may terminate or drop. An environment value is
# not authorization; it must match this name after the endpoint is proven.
SMOKE_DB_ALLOWED="odoo_install_smoke"

refuse_smoke() {
  echo "❌ install-smoke refused: $*" >&2
  exit 2
}

# Static compose identity from THIS repo's file. Env project/host/db settings
# cannot certify a disposable server by themselves.
compose_identity="$(
  python3 - "$ROOT/docker-compose.yml" <<'PY'
import pathlib
import re
import sys

text = pathlib.Path(sys.argv[1]).read_text()
name = re.search(r"(?m)^name:\s*(\S+)\s*$", text)
match = re.search(r"(?ms)^  db:\n(.*?)(?=^  [a-zA-Z]|\Z)", text)
block = match.group(1) if match else ""
database = re.search(r"(?m)^\s*POSTGRES_DB:\s*(\S+)\s*$", block)
port = re.search(r'(?m)^\s*-\s*"?(?:127\.0\.0\.1:|\[::1\]:)?(\d+):\d+"?\s*$', block)
if not name or not database or not port:
    raise SystemExit(1)
print(name.group(1))
print(database.group(1))
print(port.group(1))
PY
)" || refuse_smoke "this repo's docker-compose.yml does not declare a disposable db service"
COMPOSE_PROJECT_DECLARED="$(printf '%s\n' "$compose_identity" | sed -n '1p')"
COMPOSE_BUSINESS_DB="$(printf '%s\n' "$compose_identity" | sed -n '2p')"
COMPOSE_HOST_PORT="$(printf '%s\n' "$compose_identity" | sed -n '3p')"
ODOO_COMPOSE_PROJECT="${ODOO_COMPOSE_PROJECT:-$COMPOSE_PROJECT_DECLARED}"

prove_host_db_endpoint() {
  local cid inspect_file rc
  cid="$(docker compose -p "$ODOO_COMPOSE_PROJECT" ps -q db 2>/dev/null || true)"
  if [ -z "$cid" ]; then
    echo "host mode: db container is not running, so its endpoint cannot be proven" >&2
    return 1
  fi
  inspect_file="$(mktemp)"
  if ! docker inspect "$cid" >"$inspect_file"; then
    rm -f "$inspect_file"
    return 1
  fi
  python3 - "$inspect_file" "$ROOT" "$ODOO_DB_PORT" "$ODOO_COMPOSE_PROJECT" <<'PY'
import json
import os
import sys

inspect_path, root, port, project = sys.argv[1:]
with open(inspect_path, encoding="utf-8") as handle:
    payload = json.load(handle)
if not isinstance(payload, list) or not payload:
    raise SystemExit(1)
info = payload[0]
labels = (info.get("Config") or {}).get("Labels") or {}
if labels.get("com.docker.compose.project") != project:
    raise SystemExit(1)
if labels.get("com.docker.compose.service") != "db":
    raise SystemExit(1)
workdir = os.path.realpath(labels.get("com.docker.compose.project.working_dir") or "")
if workdir != os.path.realpath(root):
    raise SystemExit(1)
bindings = (info.get("HostConfig") or {}).get("PortBindings") or {}
hosts = bindings.get("5432/tcp") or []
for item in hosts:
    ip = item.get("HostIp") or ""
    host_port = item.get("HostPort") or ""
    if ip in {"127.0.0.1", "::1"} and host_port == port:
        raise SystemExit(0)
raise SystemExit(1)
PY
  rc=$?
  rm -f "$inspect_file"
  return "$rc"
}

assert_smoke_db_disposable() {
  local requested="${ODOO_INSTALL_SMOKE_DB:-$SMOKE_DB_ALLOWED}"

  if [ -n "${DOCKER_HOST:-}" ]; then
    refuse_smoke "DOCKER_HOST is set (${DOCKER_HOST}); refusing a remote Docker endpoint"
  fi
  if [ -n "${COMPOSE_FILE:-}" ]; then
    local compose_here compose_req
    compose_here="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$ROOT/docker-compose.yml")"
    compose_req="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$COMPOSE_FILE" 2>/dev/null || true)"
    if [ "$compose_req" != "$compose_here" ]; then
      refuse_smoke "COMPOSE_FILE is not this repo's docker-compose.yml"
    fi
  fi
  if [ "$ODOO_COMPOSE_PROJECT" != "$COMPOSE_PROJECT_DECLARED" ]; then
    refuse_smoke "compose project '$ODOO_COMPOSE_PROJECT' is not this repo's disposable stack '$COMPOSE_PROJECT_DECLARED'"
  fi
  if [[ ! "$requested" =~ ^[A-Za-z0-9_]+$ ]]; then
    refuse_smoke "database name contains unsafe SQL characters"
  fi
  case "$requested" in
    odoo|postgres|template0|template1|production|Production|cieTrade|ERP|erp)
      refuse_smoke "database '$requested' is a protected business, system, production, or ERP name"
      ;;
  esac
  if [ "$requested" != "$SMOKE_DB_ALLOWED" ]; then
    refuse_smoke "database '$requested' is not the disposable smoke database '$SMOKE_DB_ALLOWED'"
  fi
  if [ "$requested" = "$COMPOSE_BUSINESS_DB" ] || [ "$requested" = "$POSTGRES_DB" ]; then
    refuse_smoke "smoke database collides with the business database"
  fi
  case "$SMOKE_NETWORK_MODE" in
    compose)
      if [ "$ODOO_DB_HOST" != "db" ] || [ "$ODOO_DB_PORT" != "5432" ]; then
        refuse_smoke "compose endpoint ${ODOO_DB_HOST}:${ODOO_DB_PORT} is not the local db service"
      fi
      ;;
    host)
      case "$ODOO_DB_HOST" in
        127.0.0.1|localhost) ;;
        *) refuse_smoke "host endpoint '$ODOO_DB_HOST' is not a loopback address" ;;
      esac
      if [ "$ODOO_DB_PORT" != "$COMPOSE_HOST_PORT" ]; then
        refuse_smoke "host port '$ODOO_DB_PORT' does not match the compose published port '$COMPOSE_HOST_PORT'"
      fi
      if ! prove_host_db_endpoint; then
        refuse_smoke "host-network database identity is not a proven disposable loopback container; host mode is blocked"
      fi
      ;;
  esac
  SMOKE_DB="$SMOKE_DB_ALLOWED"
  readonly SMOKE_DB
}

assert_smoke_db_disposable
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

# The documented custom-only path must not require private Enterprise sources.
# Full parity installs still fail closed until the local Enterprise mount exists.
if [ -n "$ENTERPRISE_MODULES" ] && [ "$ENTERPRISE_MODULES" != "none" ] && [ ! -e "$ROOT/odoo-enterprise" ]; then
  CANDIDATE="${ODOO_ENTERPRISE_PATH:-$HOME/Dropbox/Repo_Dropbox_IB/IB-Odoo_19/odoo-enterprise}"
  if [ -d "$CANDIDATE" ]; then
    ln -s "$CANDIDATE" "$ROOT/odoo-enterprise"
    echo "→ Linked odoo-enterprise → $CANDIDATE"
  else
    echo "❌ odoo-enterprise missing for Enterprise-parity install-smoke." >&2
    echo "   Full parity: ln -s \"\$HOME/Dropbox/Repo_Dropbox_IB/IB-Odoo_19/odoo-enterprise\" odoo-enterprise" >&2
    echo "   Custom-only: ODOO_ENTERPRISE_MODULES=none make install-smoke" >&2
    exit 1
  fi
fi

if [ -n "$ENTERPRISE_MODULES" ] && [ "$ENTERPRISE_MODULES" != "none" ]; then
  ALL_MODULES="${ENTERPRISE_MODULES},${CUSTOM_MODULES}"
else
  ALL_MODULES="${CUSTOM_MODULES}"
fi

echo "════════════════════════════════════════════════════════"
echo " Odoo install-smoke"
echo " DB:       $SMOKE_DB"
echo " Modules:  $ALL_MODULES"
echo " Network:  $SMOKE_NETWORK_MODE ($ODOO_DB_HOST:$ODOO_DB_PORT)"
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
SMOKE_IMAGE="${ODOO_SMOKE_IMAGE:-${ODOO_COMPOSE_PROJECT}-odoo-test:latest}"

if [ "$SMOKE_DB" != "odoo_install_smoke" ]; then
  echo "❌ install-smoke refused: smoke database identity was not proven" >&2
  exit 2
fi
echo "→ Dropping smoke DB 'odoo_install_smoke'..."
docker compose -p "$ODOO_COMPOSE_PROJECT" exec -T db psql -U "$POSTGRES_USER" -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'odoo_install_smoke' AND pid <> pg_backend_pid();" \
  >/dev/null 2>&1 || true
docker compose -p "$ODOO_COMPOSE_PROJECT" exec -T db psql -U "$POSTGRES_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS \"odoo_install_smoke\";" >/dev/null

echo "→ Installing modules (--stop-after-init)..."
set +e
if [ "$SMOKE_NETWORK_MODE" = "host" ]; then
  ADDONS_PATH="/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons"
  # The official Odoo image entrypoint appends DB arguments after CLI input.
  # Set its HOST/PORT/USER/PASSWORD contract so it preserves host-network values.
  RUN_ARGS=(
    docker run --rm --network host
    -e "HOST=$ODOO_DB_HOST"
    -e "PORT=$ODOO_DB_PORT"
    -e "USER=$POSTGRES_USER"
    -e "PASSWORD=$POSTGRES_PASSWORD"
    -v "$ROOT:/mnt/extra-addons"
  )
  if [ -n "$ENTERPRISE_MODULES" ] && [ "$ENTERPRISE_MODULES" != "none" ]; then
    ADDONS_PATH="/mnt/extra-addons,/mnt/enterprise,/usr/lib/python3/dist-packages/odoo/addons"
    RUN_ARGS+=(-v "$ROOT/odoo-enterprise:/mnt/enterprise:ro")
  fi
  "${RUN_ARGS[@]}" "$SMOKE_IMAGE" \
    --addons-path="$ADDONS_PATH" \
    -d "$SMOKE_DB" \
    --db_host="$ODOO_DB_HOST" \
    --db_port="$ODOO_DB_PORT" \
    --db_user="$POSTGRES_USER" \
    --db_password="$POSTGRES_PASSWORD" \
    -i "$ALL_MODULES" \
    --without-demo=all \
    --log-level=info \
    --stop-after-init 2>&1 | tee "$LOG_FILE"
else
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
fi
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
# Registry fatals only. Exclude convert.py <delete> misses (logged as WARNING +
# Traceback ValueError on fresh DBs) — those do not abort module load.
FATAL_PATTERNS='Failed to initialize database|ParseError|odoo\.registry: Failed to load registry|Invalid field'
# External ID not found is fatal only outside convert delete-skip / cache lookup noise.
if grep -E "$FATAL_PATTERNS" "$LOG_FILE" | grep -vE "test_|Undefined substitution|Unexpected indentation" | head -40; then
  echo "" >&2
  echo "❌ install-smoke FAILED: fatal install/registry error in log" >&2
  echo "   Log: $LOG_FILE" >&2
  exit 1
fi
if grep -E "External ID not found" "$LOG_FILE" \
  | grep -vE "Skipping deletion for missing XML ID|_tag_delete|test_|Undefined substitution" \
  | grep -E "ERROR|CRITICAL|ParseError|Failed to load registry" \
  | head -40; then
  echo "" >&2
  echo "❌ install-smoke FAILED: fatal External ID error in log" >&2
  echo "   Log: $LOG_FILE" >&2
  exit 1
fi

# Verify key modules installed
echo "→ Verifying module states..."
FAIL=0
# Comma-split only for this read. A global IFS would change later unquoted expansions.
IFS=',' read -r -a _smoke_modules <<< "${CUSTOM_MODULES}"
for mod in "${_smoke_modules[@]}"; do
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
if [ "$SMOKE_NETWORK_MODE" = "host" ]; then
  docker run --rm --network host --entrypoint python3 "$SMOKE_IMAGE" -c "import xmlsec; print('xmlsec', xmlsec.__version__)"
else
  docker compose -p "$ODOO_COMPOSE_PROJECT" run --rm --entrypoint python3 odoo-test -c "import xmlsec; print('xmlsec', xmlsec.__version__)"
fi

echo ""
echo "✅ install-smoke PASSED — safe to push (modules load cleanly)"
echo "   DB=$SMOKE_DB  log=$LOG_FILE"
