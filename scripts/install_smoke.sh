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
#   ./scripts/install_smoke.sh --resolve    # effective lists only; no Docker
#   ./scripts/install_smoke.sh --recheck    # live evidence; no install
#   ODOO_ENTERPRISE_MODULES=none ./scripts/install_smoke.sh   # custom-only; writes no publication evidence
#   ODOO_INSTALL_SMOKE_NETWORK=host ./scripts/install_smoke.sh # sandbox bridge fallback
#   make install-smoke
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SMOKE_MODE="install"
case "${1:-}" in
  --resolve) SMOKE_MODE="resolve" ;;
  --recheck) SMOKE_MODE="recheck" ;;
  "") ;;
  *)
    echo "❌ install-smoke: unknown argument '${1}'" >&2
    exit 2
    ;;
esac

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$ROOT/.env"
  set +a
fi

# Effective lists are resolved only here, after .env. Callers must not re-parse
# the shell environment and treat that as the installer's configuration.
resolve_module_lists() {
  local scope canon_custom
  scope="${ODOO_INSTALL_SMOKE_SCOPE:-all}"
  CANON_CUSTOM="$(python3 "$ROOT/scripts/get_odoo_module_order.py" --all-installable 2>/dev/null || true)"
  if [ "$scope" = "ordered" ]; then
    canon_custom="$(python3 "$ROOT/scripts/get_odoo_module_order.py" 2>/dev/null || true)"
  else
    # The default scope is the canonical list itself; resolve it once.
    canon_custom="$CANON_CUSTOM"
  fi
  CANON_ENTERPRISE="$(python3 "$ROOT/scripts/get_odoo_module_order.py" --section docker_enterprise_modules 2>/dev/null || true)"
  CUSTOM_MODULES="${ODOO_REBUILD_MODULES:-${canon_custom}}"
  ENTERPRISE_MODULES="${ODOO_ENTERPRISE_MODULES:-${CANON_ENTERPRISE:-none}}"
  if [ -z "$CUSTOM_MODULES" ]; then
    echo "❌ Could not resolve custom module list from config/odoo_module_order.yaml" >&2
    exit 1
  fi
  # Match the actual Compose mount. Never validate a different repository symlink.
  ENTERPRISE_REALPATH=""
  if [ -n "$ENTERPRISE_MODULES" ] && [ "$ENTERPRISE_MODULES" != "none" ]; then
    ENTERPRISE_REALPATH="$(python3 - "$ROOT" "${ODOO_ENTERPRISE_PATH:-./odoo-enterprise}" <<'PY'
import os
import sys
from pathlib import Path
root, value = sys.argv[1:]
path = Path(value)
if not path.is_absolute():
    path = Path(root) / path
try:
    path = path.resolve(strict=True)
    if not path.is_dir() or not os.access(path, os.R_OK | os.X_OK):
        raise OSError("unreadable checkout")
    # An empty mount is not evidence that Enterprise is available.
    with (path / "web_enterprise" / "__manifest__.py").open("rb") as handle:
        handle.read(1)
except OSError:
    raise SystemExit("enterprise checkout is not readable or has no web_enterprise manifest")
print(path)
PY
)" || return 1
    export ODOO_ENTERPRISE_PATH="$ENTERPRISE_REALPATH"
  fi
}

lists_are_canonical() {
  [ -n "$CANON_CUSTOM" ] && [ "$CUSTOM_MODULES" = "$CANON_CUSTOM" ] \
    && [ -n "$CANON_ENTERPRISE" ] && [ "$ENTERPRISE_MODULES" = "$CANON_ENTERPRISE" ] \
    && [ "$ENTERPRISE_MODULES" != "none" ]
}

# Resolve the service that actually runs, not a caller-selected evidence image.
# Only a digest leaves this function; effective configuration may contain secrets.
runtime_binding() {
  docker compose -p "$ODOO_COMPOSE_PROJECT" config --format json | python3 -c '
import hashlib, json, os, sys
from pathlib import Path
config = json.load(sys.stdin)
service = config["services"]["odoo-test"]
name = service.get("image") or (config["name"] + "-odoo-test:latest")
override = os.environ.get("ODOO_SMOKE_IMAGE")
if override and override != name:
    raise SystemExit("ODOO_SMOKE_IMAGE differs from the actual Compose installer image")
if os.environ.get("ODOO_ENTERPRISE_PATH"):
    mounts = [m for m in service.get("volumes", []) if m.get("target") == "/mnt/enterprise"]
    if len(mounts) != 1 or Path(mounts[0]["source"]).resolve() != Path(os.environ["ODOO_ENTERPRISE_PATH"]):
        raise SystemExit("effective Compose Enterprise mount differs from resolved checkout")
print(name)
print(hashlib.sha256(json.dumps(service, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
'
}

# input_snapshot [binding] — a caller that has just resolved runtime_binding for
# the same moment may pass it; otherwise the snapshot resolves its own.
input_snapshot() {
  local binding="${1:-}"
  if [ -z "$binding" ]; then
    binding="$(runtime_binding)" || return 2
  fi
  python3 - "$ROOT" "$CUSTOM_MODULES" "$ENTERPRISE_MODULES" "$ENTERPRISE_REALPATH" \
    "$binding" "$SMOKE_NETWORK_MODE" "$ODOO_DB_HOST" "$ODOO_DB_PORT" <<'PY'
import hashlib
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
digest = hashlib.sha256()
for value in sys.argv[2:]:
    digest.update(value.encode() + b"\0")
# These are metadata/output directories, not addon inputs. Every other file,
# including untracked or ignored source files and binary assets, is byte-hashed.
excluded = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
def add_file(path, label):
    digest.update(label.encode() + b"\0")
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1048576), b""):
            digest.update(block)
    digest.update(b"\0")

def add_tree(directory, label, ancestors=()):
    real = directory.resolve(strict=True)
    if real in ancestors:
        raise ValueError("cyclic source-directory symlink")
    for path in sorted(directory.iterdir()):
        if path.name in excluded:
            continue
        child = label + "/" + path.name
        if path.is_dir():
            add_tree(path, child, (*ancestors, real))
        elif path.is_file():
            add_file(path, child)
        else:
            raise ValueError("unreadable or unsupported source entry: " + child)

try:
    for mod in sorted(root.glob("plasticos_*")):
        if mod.is_dir():
            add_tree(mod, mod.name)
    if (root / "config").is_dir():
        add_tree(root / "config", "config")
    for rel in (".env", "requirements.txt", "constraints.txt", "docker-compose.yml",
                "docker-compose.yaml", "Dockerfile", "scripts/install_smoke.sh",
                "scripts/get_odoo_module_order.py"):
        path = root / rel
        digest.update((rel + (":present" if path.exists() else ":absent")).encode() + b"\0")
        if path.exists():
            add_file(path, rel)
    if sys.argv[4]:
        add_tree(Path(sys.argv[4]), "enterprise")
except (OSError, ValueError) as exc:
    raise SystemExit("cannot fingerprint installation inputs: " + str(exc))
print(digest.hexdigest())
PY
}

EVIDENCE_FILE="$ROOT/.cache/pr-check/install-smoke.sha"

acquire_smoke_lock() {
  local wait="${SMOKE_LOCK_WAIT:-30}" daemon
  # All worktrees for this account and daemon use one resource lock. A worktree
  # path is deliberately NOT part of the lock key. Python fcntl supports macOS.
  daemon="$(docker info --format '{{.ID}}')" || refuse_smoke "cannot identify Docker daemon"
  [ -n "$daemon" ] || refuse_smoke "Docker daemon identity is empty"
  SMOKE_LOCK_FILE="$(python3 - "$daemon" "$ODOO_COMPOSE_PROJECT" "$SMOKE_DB_ALLOWED" <<'PY'
import hashlib
import os
import sys
from pathlib import Path
key = hashlib.sha256("\0".join(sys.argv[1:]).encode()).hexdigest()
root = Path.home() / ".local" / "state" / "plasticos" / "smoke-locks"
root.mkdir(parents=True, exist_ok=True, mode=0o700)
path = root / (key + ".lock")
if path.is_symlink():
    raise SystemExit("refusing symlinked smoke lock")
print(path)
PY
)" || refuse_smoke "cannot establish shared lock path"
  exec 9>"$SMOKE_LOCK_FILE"
  if ! python3 - "$wait" <<'PY'
import fcntl
import sys
import time
wait = float(sys.argv[1])
if not 0 <= wait <= 3600:
    raise SystemExit("SMOKE_LOCK_WAIT must be between 0 and 3600 seconds")
deadline = time.monotonic() + wait
while True:
    try:
        fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)
        break
    except BlockingIOError:
        if time.monotonic() >= deadline:
            raise SystemExit(1)
        time.sleep(0.05)
PY
  then
    refuse_smoke "lock busy for ${ODOO_COMPOSE_PROJECT}/${SMOKE_DB_ALLOWED}"
  fi
}

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

resolve_module_lists

if [ "$SMOKE_MODE" = "resolve" ]; then
  if ! lists_are_canonical; then
    echo "❌ effective module lists are not the full canonical install set" >&2
    echo "   custom=${CUSTOM_MODULES}" >&2
    echo "   enterprise=${ENTERPRISE_MODULES}" >&2
    exit 1
  fi
  if [ ! -d "$ENTERPRISE_REALPATH" ]; then
    echo "❌ enterprise checkout is not readable" >&2
    exit 1
  fi
  echo "custom=${CUSTOM_MODULES}"
  echo "enterprise=${ENTERPRISE_MODULES}"
  exit 0
fi

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
  # Docker Compose otherwise auto-merges docker-compose.override.yml, which
  # could silently change the database endpoint after static identity checks.
  export COMPOSE_FILE="$ROOT/docker-compose.yml"
  if [ "$ODOO_COMPOSE_PROJECT" != "$COMPOSE_PROJECT_DECLARED" ]; then
    refuse_smoke "compose project '$ODOO_COMPOSE_PROJECT' is not this repo's disposable stack '$COMPOSE_PROJECT_DECLARED'"
  fi
  if [[ ! "$requested" =~ ^[A-Za-z0-9_]+$ ]]; then
    refuse_smoke "database name contains unsafe SQL characters"
  fi
  case "$requested" in
    odoo|postgres|template0|template1|production|Production|ERP|erp)
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
      ;;
  esac
  # DOCKER_HOST is not the only way to select a remote daemon. An active
  # Docker context (or DOCKER_CONTEXT override) can silently use SSH/TCP.
  # No Docker call occurs until static database and endpoint checks pass.
  local context_host
  context_host="$(docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null)" \
    || refuse_smoke "cannot verify the active Docker context endpoint"
  case "$context_host" in
    unix:///*) ;;
    *) refuse_smoke "Docker context endpoint is not a local Unix socket" ;;
  esac
  if [ "$SMOKE_NETWORK_MODE" = "host" ] && ! prove_host_db_endpoint; then
    refuse_smoke "host-network database identity is not a proven disposable loopback container; host mode is blocked"
  fi
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

if [ -n "$ENTERPRISE_MODULES" ] && [ "$ENTERPRISE_MODULES" != "none" ]; then
  ALL_MODULES="${ENTERPRISE_MODULES},${CUSTOM_MODULES}"
else
  ALL_MODULES="${CUSTOM_MODULES}"
fi

# The smoke database is shared by every worktree on this daemon, and the image
# ID is identical across worktrees. Its pg_database OID changes on every
# DROP/CREATE, so another worktree's reinstall invalidates this receipt.
smoke_db_oid() {
  docker compose -p "$ODOO_COMPOSE_PROJECT" exec -T db psql -X -v ON_ERROR_STOP=1 \
    -U "$POSTGRES_USER" -d postgres -t -A -c \
    "SELECT oid FROM pg_database WHERE datname = 'odoo_install_smoke';" 2>/dev/null | tr -d '\r'
}

recheck_evidence() {
  local live binding image_id pg_cid pg_image states expected db_oid
  lists_are_canonical || refuse_smoke "recheck requires the full canonical module lists"
  acquire_smoke_lock
  [ -f "$EVIDENCE_FILE" ] || { echo "install-smoke evidence is absent" >&2; return 1; }
  binding="$(runtime_binding)" || return 2
  live="$(input_snapshot "$binding")" || return 2
  image_id="$(docker image inspect --format '{{.Id}}' "${binding%%$'\n'*}" 2>/dev/null || true)"
  pg_cid="$(docker compose -p "$ODOO_COMPOSE_PROJECT" ps -q db 2>/dev/null || true)"
  pg_image=""
  if [ -n "$pg_cid" ]; then
    pg_image="$(docker inspect --format '{{.Image}}' "$pg_cid" 2>/dev/null || true)"
  fi
  states="$(docker compose -p "$ODOO_COMPOSE_PROJECT" exec -T db psql -X -v ON_ERROR_STOP=1 \
    -U "$POSTGRES_USER" -d "$SMOKE_DB" -t -A -c \
    "SELECT name || '=' || state FROM ir_module_module ORDER BY name;" 2>/dev/null)" || return 1
  db_oid="$(smoke_db_oid)" || return 1
  expected="${ENTERPRISE_MODULES},${CUSTOM_MODULES}"
  python3 - "$EVIDENCE_FILE" "$live" "$image_id" "$pg_image" "$SMOKE_DB" "$db_oid" "$states" "$expected" <<'PY'
import json
import sys
from pathlib import Path
path, live, image_id, pg_image, database, db_oid, states_raw, inventory = sys.argv[1:]
try:
    record = json.loads(Path(path).read_text(encoding="utf-8"))
except (OSError, ValueError):
    raise SystemExit("install-smoke evidence miss: invalid record")
if not isinstance(record, dict):
    raise SystemExit("install-smoke evidence miss: record must be an object")
problems = []
for key, value in (("snapshot", live), ("image_id", image_id),
                   ("postgres_image_id", pg_image), ("database", database),
                   ("database_oid", db_oid)):
    if not value or record.get(key) != value:
        problems.append(key + " changed")
if record.get("evidence_version") != 3:
    problems.append("unqualified evidence version")
expected = {name: "installed" for name in inventory.split(",") if name}
if record.get("states") != expected:
    problems.append("incomplete canonical installed-state evidence")
seen = dict(line.strip().split("=", 1) for line in states_raw.splitlines() if "=" in line)
for name in expected:
    if seen.get(name) != "installed":
        problems.append(name + " is missing or not installed")
if problems:
    raise SystemExit("install-smoke evidence miss: " + "; ".join(problems))
PY
  # Recheck source inputs after the database query as well.
  [ "$(input_snapshot)" = "$live" ] || return 1
  echo "install-smoke evidence matches"
}

if [ "$SMOKE_MODE" = "recheck" ]; then
  recheck_evidence
  exit 0
fi

acquire_smoke_lock

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

# A new install invalidates any older receipt before touching the database.
rm -f "$EVIDENCE_FILE"
PRE_SNAPSHOT=""
if lists_are_canonical; then
  PRE_SNAPSHOT="$(input_snapshot)"
fi

# Rebuild image so xmlsec / requirements changes are present
echo "→ Building Odoo image (xmlsec + requirements)..."
docker compose -p "$ODOO_COMPOSE_PROJECT" build odoo-test
SMOKE_IMAGE="${ODOO_SMOKE_IMAGE:-${ODOO_COMPOSE_PROJECT}-odoo-test:latest}"
INSTALL_IMAGE_ID=""
if lists_are_canonical; then
  binding="$(runtime_binding)"
  SMOKE_IMAGE="${binding%%$'\n'*}"
  INSTALL_IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$SMOKE_IMAGE")"
  [ -n "$INSTALL_IMAGE_ID" ] || refuse_smoke "installer image identity is empty"
fi

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

SMOKE_CONTAINER="${ODOO_COMPOSE_PROJECT}-install-smoke-$$-${RANDOM}"
cleanup_smoke_container() {
  docker rm -f "$SMOKE_CONTAINER" >/dev/null 2>&1 || true
}
# Unique name owned only by this invocation; cleanup never targets the DB service.
trap cleanup_smoke_container EXIT
echo "→ Installing modules (--stop-after-init)..."
set +e
# Passing CLI arguments to `docker compose run odoo-test` replaces the service
# `command`, so its --addons-path is lost and the image's odoo.conf
# (/mnt/extra-addons only) applies: Enterprise modules then install as
# "missing". The addons path is therefore always passed explicitly here.
ADDONS_PATH="/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons"
if [ -n "$ENTERPRISE_MODULES" ] && [ "$ENTERPRISE_MODULES" != "none" ]; then
  ADDONS_PATH="/mnt/extra-addons,/mnt/enterprise,/usr/lib/python3/dist-packages/odoo/addons"
fi
if [ "$SMOKE_NETWORK_MODE" = "host" ]; then
  # The official Odoo image entrypoint appends DB arguments after CLI input.
  # Set its HOST/PORT/USER/PASSWORD contract so it preserves host-network values.
  RUN_ARGS=(
    docker run --name "$SMOKE_CONTAINER" --network host
    -e "HOST=$ODOO_DB_HOST"
    -e "PORT=$ODOO_DB_PORT"
    -e "USER=$POSTGRES_USER"
    -e "PASSWORD=$POSTGRES_PASSWORD"
    -v "$ROOT:/mnt/extra-addons"
  )
  if [ -n "$ENTERPRISE_MODULES" ] && [ "$ENTERPRISE_MODULES" != "none" ]; then
    RUN_ARGS+=(-v "$ENTERPRISE_REALPATH:/mnt/enterprise:ro")
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
  docker compose -p "$ODOO_COMPOSE_PROJECT" run --no-deps --name "$SMOKE_CONTAINER" \
    odoo-test \
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
STATE_PAIRS=""
# Comma-split only for this read. A global IFS would change later unquoted expansions.
_CHECK_MODULES="$CUSTOM_MODULES"
if [ -n "$ENTERPRISE_MODULES" ] && [ "$ENTERPRISE_MODULES" != "none" ]; then
  _CHECK_MODULES="${ENTERPRISE_MODULES},${CUSTOM_MODULES}"
fi
IFS=',' read -r -a _smoke_modules <<< "${_CHECK_MODULES}"
# One query for every module's state (the shape recheck_evidence reads), not one
# docker exec per module. A failed query leaves no rows, so every required
# module is reported missing and the run fails.
ALL_STATES="$(docker compose -p "$ODOO_COMPOSE_PROJECT" exec -T db psql -X -v ON_ERROR_STOP=1 \
  -U "$POSTGRES_USER" -d "$SMOKE_DB" -t -A -c \
  "SELECT name || '=' || state FROM ir_module_module ORDER BY name;" 2>/dev/null | tr -d '\r')" || ALL_STATES=""
ALL_STATES=$'\n'"${ALL_STATES}"$'\n'
for mod in "${_smoke_modules[@]}"; do
  mod="$(echo "$mod" | xargs)"
  [ -z "$mod" ] && continue
  STATE=""
  if [[ "$ALL_STATES" == *$'\n'"${mod}=installed"$'\n'* ]]; then
    STATE="installed"
  elif [[ "$ALL_STATES" == *$'\n'"${mod}="* ]]; then
    STATE="${ALL_STATES#*$'\n'"${mod}="}"
    STATE="${STATE%%$'\n'*}"
  fi
  if [ "$STATE" = "installed" ]; then
    echo "  ✅ $mod"
    STATE_PAIRS="${STATE_PAIRS}${mod}=installed"$'\n'
  else
    echo "  ❌ $mod → '${STATE:-missing}' (expected installed)"
    FAIL=1
  fi
done

if [ "$FAIL" -ne 0 ]; then
  echo "❌ install-smoke FAILED: one or more modules not installed" >&2
  exit 1
fi

POST_SNAPSHOT=""
if lists_are_canonical; then
  POST_SNAPSHOT="$(input_snapshot)"
  if [ "$POST_SNAPSHOT" != "$PRE_SNAPSHOT" ]; then
    echo "install-smoke inputs changed during install; evidence not written" >&2
    exit 1
  fi
  actual_image="$(docker inspect --format '{{.Image}}' "$SMOKE_CONTAINER")"
  current_image="$(docker image inspect --format '{{.Id}}' "$SMOKE_IMAGE")"
  if [ "$actual_image" != "$INSTALL_IMAGE_ID" ] || [ "$current_image" != "$INSTALL_IMAGE_ID" ]; then
    echo "install-smoke actual installer image changed; evidence not written" >&2
    exit 1
  fi
fi

# Prove xmlsec import inside the image (enterprise parity)
echo "→ Proving xmlsec import in image..."
if [ "$SMOKE_NETWORK_MODE" = "host" ]; then
  docker run --rm --network host --entrypoint python3 "$SMOKE_IMAGE" -c "import xmlsec; print('xmlsec', xmlsec.__version__)"
else
  docker compose -p "$ODOO_COMPOSE_PROJECT" run --rm --entrypoint python3 odoo-test -c "import xmlsec; print('xmlsec', xmlsec.__version__)"
fi

if lists_are_canonical; then
  # The xmlsec import check also has to use the same image as installation.
  [ "$(docker image inspect --format '{{.Id}}' "$SMOKE_IMAGE")" = "$INSTALL_IMAGE_ID" ] || exit 1
  [ "$(input_snapshot)" = "$PRE_SNAPSHOT" ] || exit 1
  pg_cid="$(docker compose -p "$ODOO_COMPOSE_PROJECT" ps -q db)"
  pg_image="$(docker inspect --format '{{.Image}}' "$pg_cid")"
  db_oid="$(smoke_db_oid)"
  python3 - "$EVIDENCE_FILE" "$CUSTOM_MODULES" "$ENTERPRISE_MODULES" "$ENTERPRISE_REALPATH" "$POST_SNAPSHOT" \
    "$INSTALL_IMAGE_ID" "$pg_image" "$SMOKE_DB" "$db_oid" "$STATE_PAIRS" <<'PY'
import json
import os
import pathlib
import sys
import tempfile
path, custom, enterprise, realpath, snapshot, image_id, pg_image, database, db_oid, pairs = sys.argv[1:]
states = dict(line.split("=", 1) for line in pairs.splitlines() if "=" in line)
expected = {name: "installed" for name in (enterprise + "," + custom).split(",") if name}
if states != expected or not image_id or not pg_image or not db_oid.isdigit():
    raise SystemExit("cannot publish incomplete installation evidence")
record = {"evidence_version": 3, "custom": custom, "enterprise": enterprise,
          "enterprise_realpath": realpath, "snapshot": snapshot, "image_id": image_id,
          "postgres_image_id": pg_image, "database": database, "database_oid": db_oid,
          "states": states}
target = pathlib.Path(path)
target.parent.mkdir(parents=True, exist_ok=True)
fd, temporary = tempfile.mkstemp(prefix=".install-smoke-", dir=target.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(record, handle, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
  echo "publication evidence written"
else
  echo "→ shortened module list; publication evidence not written"
fi

echo ""
echo "✅ install-smoke PASSED — safe to push (modules load cleanly)"
echo "   DB=$SMOKE_DB  log=$LOG_FILE"
