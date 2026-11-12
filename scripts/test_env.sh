#!/usr/bin/env bash
# Disposable Odoo 19 test databases cloned from an admitted template.
#
# The declared module set (config/odoo_module_order.yaml: docker_enterprise_modules
# + default_install_order) is installed once into a TEMPLATE database for a US
# company, verified, and published. Every test then gets its own clone of that
# template, so agents test on a fresh, production-equivalent database without
# reinstalling Enterprise, accounting, or PlasticOS.
#
# Usage:
#   scripts/test_env.sh template              build or reuse the template for the current inputs
#   scripts/test_env.sh clone [db]            fresh clone owned by this worktree (default: `name`)
#   scripts/test_env.sh run <db> -- <args>    assert <db> is an owned clone, then run odoo <args> on it
#                                             (a --test-enable run is the test runner below)
#   scripts/test_env.sh assert-clone <db>     verify identity and scope; exit non-zero otherwise
#   scripts/test_env.sh drop <db>             drop an owned clone (database and filestore)
#   scripts/test_env.sh status                fingerprint inputs, templates, and clones
#   scripts/test_env.sh name                  this worktree's default clone name (no Docker needed)
#
# Environment:
#   TEST_ENV_PARITY      enterprise (default) | community. community is the safety
#                        harness only. It is refused unless TEST_ENV_SAFETY_HARNESS=1.
#   ODOO_ENTERPRISE_PATH host directory mounted as /mnt/enterprise (default ./odoo-enterprise).
#   TEST_ENV_OWNER       owner identity stamped on clones (default: derived from this
#                        worktree's path, so two worktrees never share one).
#   TEST_ENV_LOCK_TIMEOUT seconds to wait for another agent's lease (default 3600).
#   TEST_ENV_ALLOW_NEW_TEMPLATE
#                        set to the fixture database name only when that database
#                        is absent and a rebuild was requested. Any other value,
#                        including 1, is refused. The rebuild does not rename
#                        another template onto the fixture name.
#   TEST_ENV_SAFETY_HARNESS
#                        set to 1 only by tests/test_test_env_safety.py. It is
#                        not an Enterprise test path.
#   TEST_ENV_EVIDENCE_DIR
#                        honoured only with TEST_ENV_SAFETY_HARNESS=1, so the
#                        safety suite never writes into a checkout's evidence.
#
# Safety model (every rule is checked before anything is dropped or replaced):
#   * Targets must match odoo_test_<suffix>; production, staging, business, system,
#     and template names are refused. Names are validated before reaching SQL.
#   * Docker must be the local daemon, the compose file and project must be this
#     repository's, and the db container must be this repository's db service.
#   * An existing database is replaced only when its comment proves it is a clone
#     owned by the caller. Anything else is refused, never dropped.
#   * Template builds and clones run under Postgres advisory locks held by a psql
#     session that dies with this process, so an interrupted run releases them.
#   * A template is built under a separate build name and renamed into place only
#     after admission. An incomplete build is never published or cloned.
#   * Enterprise tests use the database named in config/test_env_fixture.conf.
#     That database is the only template. Another template is not selected, and
#     a new one is not created unless that database is absent and
#     TEST_ENV_ALLOW_NEW_TEMPLATE equals its name. Community parity is the safety
#     suite's fingerprint-named template and is not the Enterprise fixture.
#   * The fixture is used only for the inputs it was admitted for: the Odoo
#     image, the Postgres major, the module roster, the runtime configuration,
#     and the Enterprise checkout. Different inputs, or inputs it cannot be
#     proved against, are refused; the fixture is not rebuilt or replaced.
#     PlasticOS addon source is not one of those inputs: a --test-enable run
#     upgrades every declared PlasticOS module on the clone before its tests run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$ROOT/.env"
  set +a
fi

SCHEMA="plasticos-test-env/2"
POSTGRES_USER="${POSTGRES_USER:-odoo}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-odoo}"
LOCK_TIMEOUT="${TEST_ENV_LOCK_TIMEOUT:-3600}"
CORE_ADDONS="/usr/lib/python3/dist-packages/odoo/addons"
EVIDENCE_DIR="$ROOT/.l9/runtime/test-env"
export ODOO_ENTERPRISE_PATH="${ODOO_ENTERPRISE_PATH:-./odoo-enterprise}"

die() {
  echo "❌ test-env: $*" >&2
  exit 1
}
refuse() {
  echo "❌ test-env refused: $*" >&2
  exit 2
}
sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum | cut -d' ' -f1; else shasum -a 256 | cut -d' ' -f1; fi
}
utc_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

case "${TEST_ENV_PARITY:-enterprise}" in
  enterprise) PARITY=ee ;;
  community) PARITY=ce ;;
  *) refuse "TEST_ENV_PARITY must be 'enterprise' or 'community' (got '${TEST_ENV_PARITY}')" ;;
esac
if [ "$PARITY" = "ce" ] && [ "${TEST_ENV_SAFETY_HARNESS:-}" != "1" ]; then
  refuse "TEST_ENV_PARITY=community is the safety harness, not an Enterprise test environment. Enterprise tests use config/test_env_fixture.conf"
fi
if [ "${TEST_ENV_SAFETY_HARNESS:-}" = "1" ] && [ -n "${TEST_ENV_EVIDENCE_DIR:-}" ]; then
  EVIDENCE_DIR="$TEST_ENV_EVIDENCE_DIR"
fi

# The Enterprise template name is a repository fact, not a fingerprint. The safety
# harness keeps fingerprint-named templates so a stale clone can be proved refused.
PINNED_TEMPLATE=""
load_pinned_template() {
  local line count=0 value=""
  [ -f "$1" ] || refuse "missing config/test_env_fixture.conf; the enterprise test fixture must be named there"
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      "" | \#*) continue ;;
      TEMPLATE=*)
        count=$((count + 1))
        value="${line#TEMPLATE=}"
        ;;
      *) refuse "config/test_env_fixture.conf has an unrecognized line" ;;
    esac
  done <"$1"
  [ "$count" -eq 1 ] || refuse "config/test_env_fixture.conf must contain exactly one TEMPLATE= line"
  value="$(printf '%s' "$value" | tr -d '[:space:]')"
  [[ "$value" =~ ^odoo_test_tpl_ee_[a-f0-9]{16}$ ]] ||
    refuse "TEMPLATE in config/test_env_fixture.conf must be odoo_test_tpl_ee_<16 lowercase hex> (got '${value}')"
  PINNED_TEMPLATE="$value"
}
if [ "$PARITY" = "ee" ]; then
  load_pinned_template "$ROOT/config/test_env_fixture.conf"
fi

owner_id() {
  local raw="${TEST_ENV_OWNER:-}"
  if [ -z "$raw" ]; then
    raw="w$(printf '%s' "$ROOT" | sha256 | cut -c1-10)"
  fi
  [[ "$raw" =~ ^[a-z0-9]{1,16}$ ]] || refuse "TEST_ENV_OWNER must be 1-16 lowercase letters or digits (got '$raw')"
  echo "$raw"
}
OWNER="$(owner_id)"
DEFAULT_CLONE="odoo_test_${OWNER}"

# ---------------------------------------------------------------------------
# Target identity
# ---------------------------------------------------------------------------
validate_clone_name() {
  local name="$1"
  [[ "$name" =~ ^odoo_test_[a-z0-9_]{1,48}$ ]] ||
    refuse "'$name' is not a disposable test database name (odoo_test_<suffix>: lowercase letters, digits, _)"
  case "$name" in
    odoo_test_tpl_* | odoo_test_bld_*) refuse "'$name' is a template name; templates are never a clone target" ;;
    *prod* | *staging*) refuse "'$name' names a production or staging database" ;;
  esac
  if [ "$name" = "${POSTGRES_DB:-odoo}" ] || [ "$name" = "${ODOO_DB_NAME:-odoo}" ]; then
    refuse "'$name' is the business database"
  fi
}

# Only characters that are safe inside a single-quoted SQL literal reach a comment.
marker_safe() { printf '%s' "$1" | tr -cd 'A-Za-z0-9._:=/+-'; }

# ---------------------------------------------------------------------------
# Docker endpoint, compose project, and db container
# ---------------------------------------------------------------------------
COMPOSE_FILE_HERE="$ROOT/docker-compose.yml"
PROJECT_DECLARED="$(sed -n 's/^name:[[:space:]]*\([A-Za-z0-9_-]*\)[[:space:]]*$/\1/p' "$COMPOSE_FILE_HERE" | head -1)"
[ -n "$PROJECT_DECLARED" ] || refuse "docker-compose.yml declares no project name"
PROJECT="${ODOO_COMPOSE_PROJECT:-$PROJECT_DECLARED}"

compose() { docker compose -f "$COMPOSE_FILE_HERE" -p "$PROJECT" "$@"; }

verify_docker_endpoint() {
  local host="${DOCKER_HOST:-}"
  if [ -z "$host" ]; then
    host="$(docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null || true)"
  fi
  case "$host" in
    unix://* | npipe://*) ;;
    *)
      if [ -z "$host" ] || [ "${TEST_ENV_DOCKER_HOST_AUTHORIZED:-}" != "$host" ]; then
        refuse "Docker endpoint '${host:-unknown}' is not the local daemon (set TEST_ENV_DOCKER_HOST_AUTHORIZED=<endpoint> to authorize it)"
      fi
      ;;
  esac
  if [ -n "${COMPOSE_FILE:-}" ] && [ "$(realpath "$COMPOSE_FILE" 2>/dev/null)" != "$(realpath "$COMPOSE_FILE_HERE")" ]; then
    refuse "COMPOSE_FILE is not this repository's docker-compose.yml"
  fi
  if [ "$PROJECT" != "$PROJECT_DECLARED" ]; then
    refuse "compose project '$PROJECT' is not this repository's stack '$PROJECT_DECLARED'"
  fi
  docker info >/dev/null 2>&1 || die "the Docker daemon at '$host' is not reachable"
}

# The db container must be this project's db service, on this project's data
# volume, started from a checkout of this same repository (a worktree counts).
verify_db_container() {
  local cid="$1" inspect reason
  inspect="$(docker inspect "$cid")" || refuse "cannot inspect db container $cid"
  reason="$(printf '%s' "$inspect" | python3 -c '
import json, os, subprocess, sys

project, root = sys.argv[1:]
info = json.load(sys.stdin)[0]
labels = info["Config"].get("Labels") or {}

def fail(reason):
    print(reason)
    raise SystemExit(1)

if labels.get("com.docker.compose.project") != project:
    fail("container does not belong to compose project " + project)
if labels.get("com.docker.compose.service") != "db":
    fail("container is not the db service")
volumes = {m.get("Name") for m in info.get("Mounts") or [] if m.get("Destination") == "/var/lib/postgresql/data"}
if volumes != {project + "_odoo_pgdata"}:
    fail("db data volume is not " + project + "_odoo_pgdata")

def common_dir(path):
    try:
        out = subprocess.run(["git", "-C", path, "rev-parse", "--path-format=absolute", "--git-common-dir"],
                             capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return os.path.realpath(out)

workdir = labels.get("com.docker.compose.project.working_dir") or ""
if os.path.realpath(workdir) != os.path.realpath(root):
    mine, theirs = common_dir(root), common_dir(workdir) if os.path.isdir(workdir) else None
    if not mine or mine != theirs:
        fail("db container was started from " + workdir + ", which is not a checkout of this repository")
' "$PROJECT" "$ROOT" 2>&1)" || refuse "db container $cid: $reason"
}

DB_CID=""
ensure_db_service() {
  verify_docker_endpoint
  # --no-recreate: never replace a db container another agent is using, even if
  # this worktree's compose file differs.
  compose up -d --no-recreate db >/dev/null 2>&1 || die "could not start the $PROJECT db service"
  DB_CID="$(compose ps -q db)"
  [ -n "$DB_CID" ] || die "the $PROJECT db service has no container"
  verify_db_container "$DB_CID"
  for _ in $(seq 1 60); do
    docker exec "$DB_CID" pg_isready -U "$POSTGRES_USER" -d postgres >/dev/null 2>&1 && return 0
    sleep 1
  done
  die "PostgreSQL in $DB_CID did not become ready"
}

psql_admin() { docker exec "$DB_CID" psql -X -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -qtA -c "$1"; }
psql_on() { docker exec "$DB_CID" psql -X -U "$POSTGRES_USER" -d "$1" -v ON_ERROR_STOP=1 -qtA -F '|' -c "$2"; }
db_exists() { [ "$(psql_admin "SELECT 1 FROM pg_database WHERE datname = '$1'")" = "1" ]; }
db_comment() { psql_admin "SELECT coalesce(shobj_description(oid, 'pg_database'), '') FROM pg_database WHERE datname = '$1'"; }
set_comment() { psql_admin "COMMENT ON DATABASE \"$1\" IS '$2'" >/dev/null; }
field() { printf '%s\n' "$1" | tr ' ' '\n' | sed -n "s/^$2=//p" | head -1; }
is_ours() { [ "${1%% *}" = "$SCHEMA" ]; }

# ---------------------------------------------------------------------------
# Leases: Postgres advisory locks held by one psql session per run. If this
# process dies, the session's stdin closes, psql exits, and the locks go.
# ---------------------------------------------------------------------------
LEASE_DIR=""
LEASE_PID=""
lease_open() {
  [ -n "$LEASE_PID" ] && return 0
  LEASE_DIR="$(mktemp -d)"
  mkfifo "$LEASE_DIR/in"
  : >"$LEASE_DIR/out"
  docker exec -i -e "PGAPPNAME=plasticos-test-env:$OWNER:$$" "$DB_CID" \
    psql -X -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -qtA <"$LEASE_DIR/in" >"$LEASE_DIR/out" 2>&1 &
  LEASE_PID=$!
  exec 9>"$LEASE_DIR/in"
  trap lease_close EXIT
  trap 'exit 130' INT TERM
}
# shellcheck disable=SC2329 # invoked by the EXIT trap set in lease_open
lease_close() {
  if [ -n "$LEASE_PID" ]; then
    exec 9>&- || true
    wait "$LEASE_PID" 2>/dev/null || true
    rm -rf "$LEASE_DIR"
    LEASE_PID=""
  fi
}
lease_holders() {
  psql_admin "SELECT string_agg(DISTINCT a.application_name, ', ') FROM pg_locks l JOIN pg_stat_activity a USING (pid)
              WHERE l.locktype = 'advisory' AND l.granted AND a.application_name LIKE 'plasticos-test-env:%'"
}
# lease <key> exclusive|shared — blocks until granted or TEST_ENV_LOCK_TIMEOUT.
# An uncontended grant arrives within milliseconds, so the first checks are
# close together. The pauses (centiseconds) add up to exactly 2s, where a
# still-waiting run reports who holds the lease, and then repeat at 1s as a
# held lease always has. The limit is measured on the wall clock (SECONDS),
# not by counting sleeps. SECONDS has whole-second resolution, so the wait ends
# only once the difference exceeds the limit: never earlier than LOCK_TIMEOUT,
# at most ~2s later.
lease() {
  local key="$1" fn="pg_advisory_lock" token start="$SECONDS" slept=0 step=0 cs
  local -a pause=(5 10 20 40 80 45 100)
  [ "$2" = "shared" ] && fn="pg_advisory_lock_shared"
  lease_open
  token="granted-$RANDOM$RANDOM"
  printf "SELECT %s(hashtextextended('%s:%s', 0)); SELECT '%s';\n" "$fn" "$SCHEMA" "$key" "$token" >&9
  until grep -qx "$token" "$LEASE_DIR/out"; do
    kill -0 "$LEASE_PID" 2>/dev/null || die "lease session ended: $(cat "$LEASE_DIR/out")"
    if [ "$slept" -eq 200 ]; then
      echo "→ waiting for lease '$key' (held by: $(lease_holders))"
    fi
    [ $((SECONDS - start)) -gt "$LOCK_TIMEOUT" ] && die "timed out after ${LOCK_TIMEOUT}s waiting for lease '$key'"
    cs="${pause[$step]}"
    sleep "$((cs / 100)).$((cs % 100 / 10))$((cs % 10))"
    slept=$((slept + cs))
    if [ "$step" -lt $((${#pause[@]} - 1)) ]; then
      step=$((step + 1))
    fi
  done
}
unlease() {
  local key="$1" fn="pg_advisory_unlock" token
  [ "$2" = "shared" ] && fn="pg_advisory_unlock_shared"
  token="released-$RANDOM$RANDOM"
  printf "SELECT %s(hashtextextended('%s:%s', 0)); SELECT '%s';\n" "$fn" "$SCHEMA" "$key" "$token" >&9
  until grep -qx "$token" "$LEASE_DIR/out"; do sleep 0.2; done
}

# ---------------------------------------------------------------------------
# Inputs and fingerprint
# ---------------------------------------------------------------------------
module_list() {
  local custom enterprise
  custom="$(python3 scripts/get_odoo_module_order.py)"
  if [ "$PARITY" = "ee" ]; then
    enterprise="$(python3 scripts/get_odoo_module_order.py --section docker_enterprise_modules)"
    echo "${enterprise},${custom}"
  else
    echo "$custom"
  fi
}

addons_path() {
  if [ "$PARITY" = "ee" ]; then
    echo "/mnt/extra-addons,/mnt/enterprise,$CORE_ADDONS"
  else
    echo "/mnt/extra-addons,$CORE_ADDONS"
  fi
}

# Content digest of files: git-listed (tracked + untracked, not ignored) under
# the given pathspecs of a repository, or every file of a plain directory.
content_digest() {
  python3 - "$@" <<'PY'
import hashlib, os, subprocess, sys

mode, base, *specs = sys.argv[1:]
digest = hashlib.sha256()
if mode in ("git", "untracked"):
    which = "-co" if mode == "git" else "-o"
    out = subprocess.run(["git", "-C", base, "ls-files", "-z", which, "--exclude-standard", "--", *specs],
                         capture_output=True, check=True).stdout
    paths = sorted({p for p in out.decode().split("\0") if p})
else:
    paths = sorted(os.path.relpath(os.path.join(d, f), base) for d, dirs, files in os.walk(base)
                   if ".git" not in d.split(os.sep) for f in files)
for rel in paths:
    full = os.path.join(base, rel)
    if not os.path.isfile(full):
        continue
    digest.update(rel.encode() + b"\0")
    with open(full, "rb") as handle:
        digest.update(hashlib.sha256(handle.read()).digest())
print(digest.hexdigest())
PY
}

enterprise_dir() { realpath "$ODOO_ENTERPRISE_PATH" 2>/dev/null || true; }

enterprise_revision() {
  local dir
  dir="$(enterprise_dir)"
  [ -n "$dir" ] && [ -d "$dir" ] || {
    echo "absent"
    return
  }
  if git -C "$dir" rev-parse --verify -q HEAD >/dev/null 2>&1 && [ "$(git -C "$dir" rev-parse --show-toplevel)" = "$dir" ]; then
    if [ -z "$(git -C "$dir" status --porcelain)" ]; then
      echo "git:$(git -C "$dir" rev-parse HEAD)"
    else
      echo "git:$(git -C "$dir" rev-parse HEAD)+dirty:$({
        git -C "$dir" diff --binary HEAD
        content_digest untracked "$dir"
      } | sha256 | cut -c1-16)"
    fi
  else
    echo "tree:$(enterprise_tree_digest "$dir")"
  fi
}

# A broken Enterprise gitdir used to hash every file on each invocation.
# Reuse the digest while the newest file mtime is unchanged. A changed tree
# still changes the fingerprint, and the pinned template then needs
# `make test-env-rebuild`.
enterprise_tree_digest() {
  local dir="$1" cache newest digest recorded_dir recorded_mtime recorded_digest
  cache="$EVIDENCE_DIR/enterprise-tree.cache"
  newest="$(python3 - "$dir" <<'PY'
import os
import sys

root = sys.argv[1]
newest = 0
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [name for name in dirnames if name != ".git"]
    for name in filenames:
        try:
            newest = max(newest, os.stat(os.path.join(dirpath, name)).st_mtime_ns)
        except OSError:
            continue
print(newest)
PY
)"
  if [ -f "$cache" ]; then
    IFS=$'\t' read -r recorded_dir recorded_mtime recorded_digest <"$cache"
    if [ "$recorded_dir" = "$dir" ] && [ "$recorded_mtime" = "$newest" ] && [ -n "$recorded_digest" ]; then
      printf '%s' "$recorded_digest"
      return 0
    fi
  fi
  digest="$(content_digest tree "$dir")"
  mkdir -p "$EVIDENCE_DIR"
  printf '%s\t%s\t%s\n' "$dir" "$newest" "$digest" >"$cache"
  printf '%s' "$digest"
}

ODOO_IMAGE=""
ensure_odoo_image() {
  # The odoo service builds from the Dockerfile; compose names that image
  # <project>-odoo unless the service sets `image:`. (`config --images odoo`
  # also lists the db dependency's image, in no fixed order.)
  ODOO_IMAGE="$(compose config --format json | python3 -c 'import json, sys
print(json.load(sys.stdin)["services"]["odoo"].get("image") or "")')"
  ODOO_IMAGE="${ODOO_IMAGE:-${PROJECT}-odoo}"
  # A cached build is a no-op; a changed Dockerfile, requirement, or base image rebuilds.
  local out
  out="$(compose build --quiet odoo 2>&1)" || die "building $ODOO_IMAGE failed: $out"
}
# Layers plus the runtime identity. Compose project labels and the Compose
# version are not part of it: a Compose upgrade must not abandon an admitted
# template. Not .Id: with the containerd image store every cached rebuild gets
# a new index digest (provenance timestamps) for byte-identical content.
# A non-JSON inspect result (the safety stub) is hashed as-is.
image_id() {
  local digest
  digest="$(docker image inspect --format '{{json .RootFS.Layers}}{{json .Config}}' "$ODOO_IMAGE" | python3 -c '
import hashlib
import json
import sys

raw = sys.stdin.read()
decoder = json.JSONDecoder()
try:
    layers, index = decoder.raw_decode(raw)
    config, _ = decoder.raw_decode(raw, index)
    payload = json.dumps(
        {
            "layers": layers,
            "entrypoint": config.get("Entrypoint"),
            "cmd": config.get("Cmd"),
            "env": config.get("Env"),
            "user": config.get("User"),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
except json.JSONDecodeError:
    payload = raw
print(hashlib.sha256(payload.encode()).hexdigest())
')"
  echo "content:$digest"
}

fingerprint_inputs() {
  echo "schema=$SCHEMA"
  echo "recipe=us-company-before-accounting"
  echo "parity=$PARITY"
  echo "image=$(image_id)"
  echo "postgres=$(psql_admin "SELECT current_setting('server_version_num')::int / 10000")"
  echo "modules=$(module_list)"
  echo "config=$(content_digest git "$ROOT" config/odoo.conf config/odoo_module_order.yaml docker-compose.yml Dockerfile requirements.txt constraints.txt scripts/get_odoo_module_order.py)"
  if [ "$PARITY" = "ee" ]; then echo "enterprise=$(enterprise_revision)"; fi
}

FP=""
TEMPLATE_DB=""
BUILD_DB=""
compute_fingerprint() {
  FP="$(fingerprint_inputs | sha256)"
  if [ -n "$PINNED_TEMPLATE" ]; then
    TEMPLATE_DB="$PINNED_TEMPLATE"
  else
    TEMPLATE_DB="odoo_test_tpl_${PARITY}_${FP:0:16}"
  fi
  # The build name keeps the fingerprint suffix. Retirement and stage containers
  # identify a build by those 16 characters; a fixed suffix would miss them.
  BUILD_DB="odoo_test_bld_${PARITY}_${FP:0:16}"
}

template_ready() {
  local comment
  db_exists "$TEMPLATE_DB" || return 1
  comment="$(db_comment "$TEMPLATE_DB")"
  is_ours "$comment" && [ "$(field "$comment" role)" = "template" ] && [ "$(field "$comment" state)" = "ready" ] &&
    [ "$(field "$comment" parity)" = "$PARITY" ] && [ "$(field "$comment" fp)" = "$FP" ]
}

# Evidence directories: this run, then every worktree of this repository.
evidence_dirs() {
  echo "$EVIDENCE_DIR"
  if [ "$EVIDENCE_DIR" = "$ROOT/.l9/runtime/test-env" ]; then
    git -C "$ROOT" worktree list --porcelain 2>/dev/null | sed -n 's/^worktree \(.*\)$/\1\/.l9\/runtime\/test-env/p'
  fi
}

# Recorded inputs file of $TEMPLATE_DB from this run's evidence or any checkout
# of this repository (a worktree counts) whose content hashes to the fp on the
# database, or "". A file that hashes to that fp is the one the build recorded.
fixture_evidence() {
  local stored="$1" dir file
  while IFS= read -r dir; do
    file="$dir/${TEMPLATE_DB}.inputs.txt"
    if [ -f "$file" ] && [ "$(sha256 <"$file")" = "$stored" ]; then
      echo "$file"
      return 0
    fi
  done < <(evidence_dirs)
}

# The inputs file for this template name, even when it hashes to an older
# generation than the comment. It is a diff baseline, not admission proof.
surviving_inputs() {
  local dir file
  while IFS= read -r dir; do
    file="$dir/${TEMPLATE_DB}.inputs.txt"
    if [ -f "$file" ]; then
      echo "$file"
      return 0
    fi
  done < <(evidence_dirs)
}

changed_input_keys() {
  diff <(grep -v '^addons=' "$1") <(printf '%s\n' "$2") | sed -n 's/^[<>] \([^=]*\)=.*/\1/p' | sort -u | paste -sd, - || true
}

# The pinned fixture exists but its fp is not the current fingerprint. It was
# admitted either for other inputs or before addon source left the fingerprint.
# It is re-stamped only on proof: a recorded inputs file that hashes to its fp
# and, apart from the old addons= line, equals the current inputs line for line.
# Otherwise it is refused, naming what changed. It is never rebuilt here.
certify_pinned_fixture() {
  local comment stored evidence changed current survivor
  comment="$(db_comment "$TEMPLATE_DB")"
  is_ours "$comment" && [ "$(field "$comment" role)" = "template" ] && [ "$(field "$comment" state)" = "ready" ] &&
    [ "$(field "$comment" parity)" = "$PARITY" ] ||
    refuse "$TEMPLATE_DB exists but is not an admitted template (comment: '$comment'); not touching it"
  stored="$(field "$comment" fp)"
  evidence="$(fixture_evidence "$stored")"
  # One reading of the inputs decides, stamps, and is recorded; it must be the
  # reading FP was computed from.
  current="$(fingerprint_inputs)"
  [ "$(printf '%s\n' "$current" | sha256)" = "$FP" ] ||
    refuse "the runtime inputs changed while this run was checking $TEMPLATE_DB; run it again"
  if [ -z "$evidence" ]; then
    # A surviving file that does not hash to the comment is not proof and
    # cannot re-stamp. When its lines differ, name the keys. Either way the
    # database is left untouched.
    survivor="$(surviving_inputs)"
    if [ -n "$survivor" ]; then
      changed="$(changed_input_keys "$survivor" "$current")"
      if [ -n "$changed" ]; then
        refuse "$TEMPLATE_DB is incompatible with the current inputs: ${changed} changed since the surviving record (recorded in ${survivor#"$ROOT"/}; it does not hash to fp ${stored:0:16}). The fixture is not rebuilt or replaced. Run: make test-env-rebuild"
      fi
    fi
    refuse "$TEMPLATE_DB is unproven for the current inputs: it was admitted for fp ${stored:0:16}, current inputs are ${FP:0:16}, and no recorded inputs file in a checkout of this repository hashes to its fp. The fixture is not rebuilt or replaced. Run: make test-env-rebuild"
  fi
  if [ "$(grep -v '^addons=' "$evidence")" != "$current" ]; then
    changed="$(changed_input_keys "$evidence" "$current")"
    refuse "$TEMPLATE_DB is incompatible with the current inputs: ${changed:-the recorded inputs} changed since it was admitted (recorded in ${evidence#"$ROOT"/}). The fixture is not rebuilt or replaced. Run: make test-env-rebuild"
  fi
  set_comment "$TEMPLATE_DB" "$(printf '%s' "$comment" | sed "s| fp=[^ ]*| fp=$FP|")"
  mkdir -p "$EVIDENCE_DIR"
  printf '%s\n' "$current" >"$EVIDENCE_DIR/${TEMPLATE_DB}.inputs.txt"
  echo "✅ $TEMPLATE_DB matches the current inputs (proved by ${evidence#"$ROOT"/}); fp re-stamped ${stored:0:16} → ${FP:0:16}"
}

# ---------------------------------------------------------------------------
# Odoo stages: detached, named containers awaited from here. If this shell
# dies, the container finishes; the next run waits on it and picks up its exit
# status instead of starting the stage again.
# ---------------------------------------------------------------------------
odoo_stage() {
  local stage="$1" cname rc
  shift
  cname="${PROJECT}-test-env-${FP:0:16}-${stage}"
  mkdir -p "$EVIDENCE_DIR"
  if [ -n "$(docker ps -aq --filter "name=^${cname}$")" ]; then
    echo "→ $cname was started earlier; waiting for it"
  else
    local out
    out="$(compose run -d --no-deps --name "$cname" odoo odoo "$@" 2>&1)" || die "could not start $cname: $out"
  fi
  rc="$(docker wait "$cname")"
  docker logs "$cname" >"$EVIDENCE_DIR/${cname}.log" 2>&1 || true
  grep -E " (ERROR|CRITICAL) " "$EVIDENCE_DIR/${cname}.log" | tail -20 || true
  # Keep a successful clone stage until its database has been stamped.
  # It is the recovery witness if the caller dies after duplication.
  if [ "$rc" != "0" ] || [[ "$stage" != clone-* ]]; then
    docker rm "$cname" >/dev/null 2>&1 || true
  fi
  [ "$rc" = "0" ] || die "$cname exited with status $rc (log: ${EVIDENCE_DIR#"$ROOT"/}/${cname}.log)"
}

# `odoo db <command>`: Odoo's filestore-aware database manager. It runs without
# config/odoo.conf on purpose: that file's `db_name = odoo` limits the manager
# to the business database, which is exactly the one it must never touch here.
db_manager_args() {
  echo "db -c /dev/null --db_host db --db_port 5432 -r $POSTGRES_USER -w $POSTGRES_PASSWORD --addons-path $1"
}
odoo_db() {
  local stage="$1"
  shift
  # shellcheck disable=SC2046 # word-split the fixed manager arguments
  odoo_stage "$stage" $(db_manager_args "$(addons_path)") "$@"
}

# A database dropped outside Odoo can leave its filestore behind; a new clone
# under that name must not inherit it. Names are validated before this runs.
clear_filestore() {
  compose run --rm --no-deps --entrypoint rm odoo -rf "/var/lib/odoo/.local/share/Odoo/filestore/$1" >/dev/null
}

# Fail closed before building: every declared module must exist on an addons path.
preflight_modules() {
  local modules="$1" core missing="" module ent
  if [ "$PARITY" = "ee" ]; then
    ent="$(enterprise_dir)"
    if [ -z "$ent" ] || [ ! -f "$ent/web_enterprise/__manifest__.py" ]; then
      die "no Odoo Enterprise checkout at ODOO_ENTERPRISE_PATH=$ODOO_ENTERPRISE_PATH.
   The production-parity template requires it; Odoo would otherwise skip /mnt/enterprise
   with a warning and build a Community database. Point ODOO_ENTERPRISE_PATH at the
   Enterprise checkout, or set TEST_ENV_PARITY=community for a separately named,
   non-production template."
    fi
  fi
  core="$(docker run --rm --entrypoint ls "$ODOO_IMAGE" "$CORE_ADDONS")"
  for module in ${modules//,/ }; do
    if [ -f "$ROOT/$module/__manifest__.py" ] || grep -qx "$module" <<<"$core"; then
      continue
    fi
    if [ "$PARITY" = "ee" ] && [ -f "$ent/$module/__manifest__.py" ]; then
      continue
    fi
    missing="$missing $module"
  done
  [ -z "$missing" ] || die "declared modules not found on any addons path:$missing"
}

# Admission: the build must prove what it claims before it can be published.
# Prints the evidence; returns non-zero with the failed checks listed.
admit() {
  local db="$1" modules="$2" failures=() company declared_accounts declared_terms
  q() { psql_on "$db" "$1"; }

  local missing pending demo
  missing="$(q "SELECT string_agg(m, ',' ORDER BY m) FROM unnest(string_to_array('$modules', ',')) AS m
                WHERE m NOT IN (SELECT name FROM ir_module_module WHERE state = 'installed')")"
  pending="$(q "SELECT string_agg(name || ':' || state, ',') FROM ir_module_module
                WHERE state IN ('to install', 'to upgrade', 'to remove')")"
  demo="$(q "SELECT count(*) FROM ir_module_module WHERE demo")"
  [ -z "$missing" ] || failures+=("declared modules not installed: $missing")
  [ -z "$pending" ] || failures+=("modules left mid-transition: $pending")
  [ "$demo" = "0" ] || failures+=("$demo modules carry demo data")

  local companies
  companies="$(q "SELECT count(*) FROM res_company")"
  [ "$companies" = "1" ] || failures+=("expected one company, found $companies")
  company="$(q "SELECT co.id, pc.code, fc.code, cur.name, co.chart_template,
                       (co.account_sale_tax_id IS NOT NULL), (co.account_purchase_tax_id IS NOT NULL)
                FROM res_company co
                JOIN res_partner p ON p.id = co.partner_id
                LEFT JOIN res_country pc ON pc.id = p.country_id
                LEFT JOIN res_country fc ON fc.id = co.account_fiscal_country_id
                JOIN res_currency cur ON cur.id = co.currency_id
                ORDER BY co.id LIMIT 1")"
  local cid country fiscal currency chart sale_tax purchase_tax
  IFS='|' read -r cid country fiscal currency chart sale_tax purchase_tax <<<"$company"
  [ "$country" = "US" ] || failures+=("company country is '${country}', not US")
  [ "$fiscal" = "US" ] || failures+=("company fiscal country is '${fiscal}', not US")
  [ "$currency" = "USD" ] || failures+=("company currency is '${currency}', not USD")
  [ "$chart" = "us" ] || failures+=("company chart template is '${chart}', not the l10n_us_account 'us' template")
  [ "$sale_tax" = "t" ] && [ "$purchase_tax" = "t" ] || failures+=("company default sale/purchase taxes are not set")

  local journals taxes receivable payable
  journals="$(q "SELECT string_agg(type || '=' || n, ',' ORDER BY type) FROM
                (SELECT type, count(*) n FROM account_journal WHERE company_id = $cid AND active GROUP BY type) j")"
  for type in sale purchase bank general; do
    [[ ",$journals," == *",$type="* ]] || failures+=("no active $type journal")
  done
  taxes="$(q "SELECT string_agg(type_tax_use || '=' || n, ',' ORDER BY type_tax_use) FROM
             (SELECT type_tax_use, count(*) n FROM account_tax WHERE company_id = $cid AND active GROUP BY 1) t")"
  [[ ",$taxes," == *",sale="* && ",$taxes," == *",purchase="* ]] || failures+=("sale and purchase taxes missing ($taxes)")
  receivable="$(q "SELECT count(*) FROM account_account WHERE account_type = 'asset_receivable'")"
  payable="$(q "SELECT count(*) FROM account_account WHERE account_type = 'liability_payable'")"
  [ "$receivable" -ge 1 ] && [ "$payable" -ge 1 ] || failures+=("receivable/payable accounts missing")

  # Every PlasticOS accounting seed the module declares must be present.
  declared_accounts="$(grep -c 'model="account.account"' plasticos_accounting/data/accounts.xml)"
  declared_terms="$(grep -c 'model="account.payment.term"' plasticos_accounting/data/payment_terms.xml)"
  local seeded_accounts seeded_terms
  seeded_accounts="$(q "SELECT count(*) FROM ir_model_data d JOIN account_account a ON a.id = d.res_id
                        WHERE d.module = 'plasticos_accounting' AND d.model = 'account.account'")"
  seeded_terms="$(q "SELECT count(*) FROM ir_model_data d JOIN account_payment_term t ON t.id = d.res_id
                     WHERE d.module = 'plasticos_accounting' AND d.model = 'account.payment.term'")"
  [ "$seeded_accounts" = "$declared_accounts" ] ||
    failures+=("plasticos_accounting accounts: $seeded_accounts seeded of $declared_accounts declared")
  [ "$seeded_terms" = "$declared_terms" ] ||
    failures+=("plasticos_accounting payment terms: $seeded_terms seeded of $declared_terms declared")

  local base_version installed accounts
  base_version="$(q "SELECT latest_version FROM ir_module_module WHERE name = 'base'")"
  installed="$(q "SELECT count(*) FROM ir_module_module WHERE state = 'installed'")"
  accounts="$(q "SELECT count(*) FROM account_account")"

  ADMISSION="odoo=$(marker_safe "$base_version") installed=$installed country=$country fiscal=$fiscal currency=$currency chart=$chart accounts=$accounts plasticos_accounts=$seeded_accounts/$declared_accounts terms=$seeded_terms/$declared_terms journals=$journals taxes=$taxes"
  echo "  admission: $ADMISSION"
  q "SELECT name FROM ir_module_module WHERE state = 'installed' ORDER BY name" >"$EVIDENCE_DIR/${db}.installed-modules.txt"
  if [ "${#failures[@]}" -gt 0 ]; then
    printf '   ✗ %s\n' "${failures[@]}" >&2
    return 1
  fi
}

# Fixture identity. The addon source digest is not part of it: a PlasticOS edit
# upgrades the clone under test and must not abandon the admitted template.
fixture_inputs() {
  fingerprint_inputs | grep -v '^addons='
}

# Rename one already admitted template onto the current fixture name when its
# recorded inputs match. The database is kept; it is not reinstalled.
adopt_admitted_template() {
  local name comment stored current renamed
  current="$(fixture_inputs)"
  renamed=""
  for name in $(psql_admin "SELECT datname FROM pg_database
                            WHERE datname LIKE 'odoo_test\_tpl\_${PARITY}\_%'
                              AND datname <> '$TEMPLATE_DB'
                            ORDER BY datname"); do
    comment="$(db_comment "$name")"
    is_ours "$comment" || continue
    [ "$(field "$comment" role)" = "template" ] || continue
    [ "$(field "$comment" state)" = "ready" ] || continue
    [ "$(field "$comment" parity)" = "$PARITY" ] || continue
    [ -f "$EVIDENCE_DIR/${name}.inputs.txt" ] || continue
    stored="$(grep -v '^addons=' "$EVIDENCE_DIR/${name}.inputs.txt")"
    [ "$stored" = "$current" ] || continue
    echo "→ adopting admitted template $name as the permanent fixture $TEMPLATE_DB"
    psql_admin "ALTER DATABASE \"$name\" WITH IS_TEMPLATE false ALLOW_CONNECTIONS true" >/dev/null
    psql_admin "ALTER DATABASE \"$name\" RENAME TO \"$TEMPLATE_DB\"" >/dev/null
    psql_admin "ALTER DATABASE \"$TEMPLATE_DB\" WITH ALLOW_CONNECTIONS false IS_TEMPLATE true" >/dev/null
    set_comment "$TEMPLATE_DB" "$(printf '%s' "$comment" | sed "s| fp=[^ ]*| fp=$FP|")"
    fixture_inputs >"$EVIDENCE_DIR/${TEMPLATE_DB}.inputs.txt"
    renamed="$name"
    break
  done
  [ -n "$renamed" ]
}

# ---------------------------------------------------------------------------
# Template lifecycle
# ---------------------------------------------------------------------------
build_template() {
  local modules comment state started
  lease "tpl:$TEMPLATE_DB" exclusive
  if template_ready; then
    if [ -n "$PINNED_TEMPLATE" ]; then
      echo "✅ $TEMPLATE_DB is the canonical enterprise fixture; reusing it"
    else
      echo "✅ $TEMPLATE_DB is current (fingerprint ${FP:0:16}); reusing it"
    fi
    unlease "tpl:$TEMPLATE_DB" exclusive
    retire_own_templates
    return 0
  fi
  if [ -n "$PINNED_TEMPLATE" ] && db_exists "$TEMPLATE_DB"; then
    certify_pinned_fixture
    unlease "tpl:$TEMPLATE_DB" exclusive
    retire_own_templates
    return 0
  fi
  if db_exists "$TEMPLATE_DB"; then
    refuse "$TEMPLATE_DB exists but is not an admitted template (comment: '$(db_comment "$TEMPLATE_DB")'); not touching it"
  fi
  if [ -n "$PINNED_TEMPLATE" ] && [ "${TEST_ENV_ALLOW_NEW_TEMPLATE:-}" != "$PINNED_TEMPLATE" ]; then
    refuse "$TEMPLATE_DB is the canonical enterprise fixture and it is not an admitted template. Other test templates are not used. A new template is not created unless that database is absent and TEST_ENV_ALLOW_NEW_TEMPLATE equals its name"
  fi
  # A pinned rebuild installs the named database. It does not rename another
  # template onto that name.
  if [ -z "$PINNED_TEMPLATE" ] && adopt_admitted_template; then
    echo "✅ $TEMPLATE_DB adopted (fingerprint ${FP:0:16}); the installed database was kept"
    unlease "tpl:$TEMPLATE_DB" exclusive
    retire_own_templates
    return 0
  fi
  modules="$(module_list)"
  require_declared_template_source
  # The source is named when the build starts: that is what Odoo installs. A change to
  # the addon source before the stamp is refused below rather than recorded.
  BUILD_SOURCE_MARKER="$(template_source_marker)"
  BUILD_SOURCE_DIGEST="$(addon_source)"
  preflight_modules "$modules"
  mkdir -p "$EVIDENCE_DIR"
  fingerprint_inputs >"$EVIDENCE_DIR/${TEMPLATE_DB}.inputs.txt"
  echo "→ Building $TEMPLATE_DB (parity=$PARITY, fingerprint ${FP:0:16}) via $BUILD_DB"

  state=""
  if db_exists "$BUILD_DB"; then
    comment="$(db_comment "$BUILD_DB")"
    is_ours "$comment" && [ "$(field "$comment" role)" = "build" ] && [ "$(field "$comment" fp)" = "$FP" ] ||
      refuse "$BUILD_DB exists without this build's marker (comment: '$comment'); not touching it"
    state="$(field "$comment" state)"
    if [ "$state" = "rejected" ] || [ "$state" = "creating" ]; then
      echo "→ Discarding the earlier $state build $BUILD_DB"
      odoo_db drop drop "$BUILD_DB"
      state=""
    else
      echo "→ Resuming $BUILD_DB from state '$state'"
    fi
  fi
  started="$(utc_now)"
  local marker="$SCHEMA role=build owner=$OWNER parity=$PARITY fp=$FP started=$started"
  if [ -z "$state" ]; then
    # Odoo's own initializer creates the US company. It runs on the core
    # addons only: with the repo on the path, the auto-install bundle
    # (plasticos_odoo_standard_apps) installs `account` before the initializer
    # sets the country, and the company is left on the generic chart.
    # shellcheck disable=SC2046 # word-split the fixed manager arguments
    odoo_stage init $(db_manager_args "$CORE_ADDONS") init "$BUILD_DB" --country US --language en_US
    set_comment "$BUILD_DB" "$marker state=initialized"
    state="initialized"
  fi
  if [ "$state" = "initialized" ]; then
    echo "→ Installing $(tr ',' '\n' <<<"$modules" | wc -l | tr -d ' ') declared modules"
    odoo_stage install -d "$BUILD_DB" --addons-path="$(addons_path)" -i "$modules" \
      --without-demo=all --stop-after-init --workers=0 --max-cron-threads=0 --no-http --log-level=warn
    set_comment "$BUILD_DB" "$marker state=installed"
    state="installed"
  fi
  if [ "$state" = "installed" ]; then
    # The chart template can load after plasticos_accounting and drop its
    # seeded accounts; updating the module re-applies its own declared data.
    echo "→ Re-applying the plasticos_accounting seed"
    odoo_stage reseed -d "$BUILD_DB" --addons-path="$(addons_path)" -u plasticos_accounting \
      --stop-after-init --workers=0 --max-cron-threads=0 --no-http --log-level=warn
    set_comment "$BUILD_DB" "$marker state=reseeded"
    state="reseeded"
  fi

  echo "→ Admission checks on $BUILD_DB"
  if ! admit "$BUILD_DB" "$modules"; then
    set_comment "$BUILD_DB" "$marker state=rejected"
    die "$BUILD_DB failed admission and was not published"
  fi
  [ "$(addon_source)" = "$BUILD_SOURCE_DIGEST" ] ||
    die "PlasticOS addon source changed while $BUILD_DB was built; it is not the source that was installed (not published)"
  # Stamp ready on the build name, then rename: the template name only ever
  # exists for an admitted database.
  set_comment "$BUILD_DB" "$SCHEMA role=template state=ready parity=$PARITY fp=$FP builder=$OWNER built=$(utc_now) enterprise=$(marker_safe "$(enterprise_revision)") $BUILD_SOURCE_MARKER $ADMISSION"
  odoo_db publish rename "$BUILD_DB" "$TEMPLATE_DB"
  psql_admin "ALTER DATABASE \"$TEMPLATE_DB\" WITH ALLOW_CONNECTIONS false IS_TEMPLATE true" >/dev/null
  db_comment "$TEMPLATE_DB" >"$EVIDENCE_DIR/${TEMPLATE_DB}.admission.txt"
  echo "✅ $TEMPLATE_DB admitted and published"
  unlease "tpl:$TEMPLATE_DB" exclusive
  retire_own_templates
}

# Databases cloned from a template, whoever owns them, plus a clone stage of
# that template that was interrupted before its database was stamped.
template_references() {
  local refs stages builds=""
  refs="$(psql_admin "SELECT string_agg(datname, ',' ORDER BY datname) FROM pg_database
                      WHERE shobj_description(oid, 'pg_database') ~ (' template=' || '$1' || '( |$)')")" || return 1
  stages="$(docker ps -a --format '{{.Names}}' --filter "name=^${PROJECT}-test-env-${1: -16}-clone-" | paste -sd, -)" || return 1
  if [[ "$1" == odoo_test_bld_* ]]; then
    builds="$(docker ps -a --format '{{.Names}}' \
      --filter "name=^${PROJECT}-test-env-${1: -16}-(init|install|reseed)$" | paste -sd, -)" || return 1
  fi
  stages="${stages}${stages:+${builds:+,}}${builds}"
  printf '%s' "${refs}${refs:+${stages:+,}}${stages}"
}

# Templates and unfinished builds this owner made for other inputs are retired,
# unless someone is using them right now (their lease is tried, not awaited).
# Both share the template's lease key, so a build in progress is never touched.
retire_own_templates() {
  local name comment token key references
  for name in $(psql_admin "SELECT datname FROM pg_database
                            WHERE (datname LIKE 'odoo_test\_tpl\_${PARITY}\_%' OR datname LIKE 'odoo_test\_bld\_${PARITY}\_%')
                              AND datname NOT IN ('$TEMPLATE_DB', '$BUILD_DB')"); do
    comment="$(db_comment "$name")"
    is_ours "$comment" || continue
    [ "$(field "$comment" builder)$(field "$comment" owner)" = "$OWNER" ] || continue
    key="tpl:odoo_test_tpl_${PARITY}_${name: -16}"
    token="tried-$RANDOM$RANDOM"
    printf "SELECT 'busy' WHERE NOT pg_try_advisory_lock(hashtextextended('%s:%s', 0)); SELECT '%s';\n" "$SCHEMA" "$key" "$token" >&9
    until grep -qx "$token" "$LEASE_DIR/out"; do sleep 0.2; done
    if tail -2 "$LEASE_DIR/out" | grep -qx busy; then
      echo "→ keeping $name (in use)"
      continue
    fi
    # Holding the template's exclusive lease, no clone of it can start or be
    # stamped (cloning holds the shared lease until its clone is stamped), so
    # the references read here are final for this retirement.
    references="$(template_references "$name")" ||
      die "cannot inspect references for $name; refusing retirement"
    if [ -n "$references" ]; then
      echo "→ keeping $name (referenced by: $references)"
      unlease "$key" exclusive
      continue
    fi
    psql_admin "ALTER DATABASE \"$name\" WITH IS_TEMPLATE false ALLOW_CONNECTIONS true" >/dev/null
    odoo_db "retire-${name: -16}" drop "$name"
    echo "→ retired $name ($(field "$comment" role) for superseded inputs)"
    unlease "$key" exclusive
  done
}

# Drop one database this owner admitted, and only that role. A foreign comment
# is refused. This is the recovery `make test-env-rebuild` uses; `template`
# itself never drops an existing pinned database.
drop_pinned_database() {
  local name="$1" role="$2" comment
  db_exists "$name" || return 0
  comment="$(db_comment "$name")"
  is_ours "$comment" ||
    refuse "$name exists and is not a test-env database (comment: '$comment'); not dropping it"
  [ "$(field "$comment" role)" = "$role" ] ||
    refuse "$name role is '$(field "$comment" role)', not $role; not dropping it"
  psql_admin "ALTER DATABASE \"$name\" WITH IS_TEMPLATE false ALLOW_CONNECTIONS true" >/dev/null
  psql_admin "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$name' AND pid <> pg_backend_pid()" >/dev/null
  odoo_db "drop-${name: -16}" drop "$name"
  rm -f "$EVIDENCE_DIR/${name}.inputs.txt"
}

# Operator recovery when image, Postgres, roster, config, or Enterprise drift
# leaves the pinned template unproven. Refuses when the template is already
# admitted for the current inputs. Drops only that template and the build
# database for the current fingerprint, then admits it again.
rebuild_pinned_template() {
  [ -n "$PINNED_TEMPLATE" ] ||
    refuse "make test-env-rebuild is the enterprise fixture; there is no pinned community template"
  if template_ready; then
    refuse "$TEMPLATE_DB is already admitted for the current inputs; not rebuilding it"
  fi
  lease "tpl:$TEMPLATE_DB" exclusive
  drop_pinned_database "$TEMPLATE_DB" template
  drop_pinned_database "$BUILD_DB" build
  unlease "tpl:$TEMPLATE_DB" exclusive
  TEST_ENV_ALLOW_NEW_TEMPLATE="$PINNED_TEMPLATE"
  export TEST_ENV_ALLOW_NEW_TEMPLATE
  build_template
}

# ---------------------------------------------------------------------------
# Clones
# ---------------------------------------------------------------------------
assert_owned_or_absent() {
  local target="$1" comment
  db_exists "$target" || return 0
  comment="$(db_comment "$target")"
  if ! is_ours "$comment" || [ "$(field "$comment" role)" != "clone" ]; then
    refuse "$target exists and is not a test-env clone (comment: '${comment}'); not touching it"
  fi
  if [ "$(field "$comment" owner)" != "$OWNER" ]; then
    refuse "$target is owned by '$(field "$comment" owner)', not '$OWNER'; another agent's database is never replaced"
  fi
}

drop_owned_clone() {
  local target="$1"
  assert_owned_or_absent "$target"
  db_exists "$target" || return 0
  psql_admin "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$target' AND pid <> pg_backend_pid()" >/dev/null
  odoo_db "drop-$target" drop "$target"
}

clone_template() {
  local target="$1" attempt stage cname
  validate_clone_name "$target"
  lease "db:$target" exclusive
  # The stage name carries the owner: if an earlier run of this owner was killed
  # after Odoo created the clone but before it was stamped, the finished stage
  # container is the proof that the unstamped database is that run's clone.
  stage="clone-${OWNER}-${target}"
  cname="${PROJECT}-test-env-${FP:0:16}-${stage}"
  if db_exists "$target" && [ -z "$(db_comment "$target")" ] &&
    [ -n "$(docker ps -aq --filter "name=^${cname}$")" ]; then
    echo "→ resuming the interrupted clone of $target"
    lease "tpl:$TEMPLATE_DB" shared
    template_ready || refuse "$TEMPLATE_DB is not an admitted template"
    odoo_db "$stage" duplicate "$TEMPLATE_DB" "$target"
    set_comment "$target" "$SCHEMA role=clone owner=$OWNER parity=$PARITY template=$TEMPLATE_DB fp=$FP created=$(utc_now)"
    docker rm "$cname" >/dev/null ||
      die "could not retire stamped clone stage $cname"
    unlease "tpl:$TEMPLATE_DB" shared
    unlease "db:$target" exclusive
    echo "✅ $target is a fresh clone of $TEMPLATE_DB (owner $OWNER, parity $PARITY; resumed)"
    return 0
  fi
  assert_owned_or_absent "$target"
  # A prior run may have stamped this clone before being interrupted
  # during successful stage cleanup.
  if [ -n "$(docker ps -aq --filter "name=^${cname}$")" ]; then
    docker rm "$cname" >/dev/null ||
      die "could not clear completed clone stage $cname"
  fi
  for attempt in 1 2; do
    template_ready || build_template
    lease "tpl:$TEMPLATE_DB" shared
    if template_ready; then
      break
    fi
    unlease "tpl:$TEMPLATE_DB" shared
    [ "$attempt" = 2 ] && die "$TEMPLATE_DB disappeared twice while waiting to clone it"
  done
  drop_owned_clone "$target"
  clear_filestore "$target"
  odoo_db "$stage" duplicate "$TEMPLATE_DB" "$target"
  set_comment "$target" "$SCHEMA role=clone owner=$OWNER parity=$PARITY template=$TEMPLATE_DB fp=$FP created=$(utc_now)"
  docker rm "$cname" >/dev/null ||
    die "could not retire stamped clone stage $cname"
  unlease "tpl:$TEMPLATE_DB" shared
  unlease "db:$target" exclusive
  echo "✅ $target is a fresh clone of $TEMPLATE_DB (owner $OWNER, parity $PARITY)"
}

# `run <db> -- ...` accepts three forms and binds each to <db> and this
# repository's compose project:
#   <odoo args>                                    e.g. -- --test-enable -u m, or -- shell
#   docker compose run [--rm|-T|-w D|-e K=V] odoo [odoo] <odoo args>
#                                                  the Makefile test recipes, verbatim
#   make import-erp ODOO_DB_NAME=<db> [ERP_*|LIMIT|DRY|...=V]
#                                                  the Makefile ERP import, verbatim
#   make import-vanillasoft ODOO_DB_NAME=<db> VANILLASOFT_CALL_FLOOR=.. VANILLASOFT_CONTACT_FLOOR=..
#                                                  the rolling window, both floors explicit
#   make import-vanillasoft ODOO_DB_NAME=<db> VANILLASOFT_HISTORY_CENSUS=.. _CENSUS_SHA256=.. _CHECKPOINT=..
#                                                  the historical cohort (2026-11-07): the census
#                                                  selects it, a floor beside it is refused, the
#                                                  optional _MAX_IDS / _FAILURE_BUDGET are integers
# A production permit (ERP_PRODUCTION_PERMIT, VANILLASOFT_PRODUCTION_PERMIT) is
# never forwarded: the verified clone is never a production target.
# Anything that would point Odoo, Postgres, or compose elsewhere is refused.
RUN_MODE=""
RUN_OPTS=()
RUN_ARGS=()
parse_run() {
  local target="$1" arg name test_form=""
  shift
  RUN_MODE="odoo"
  RUN_OPTS=()
  RUN_ARGS=()
  [ "${1:-}" = "--" ] && shift
  case "${1:-}" in
    make | gmake | */make)
      RUN_MODE="make"
      RUN_ARGS=("$1")
      shift
      [ "${1:-}" = "import-erp" ] || [ "${1:-}" = "import-vanillasoft" ] ||
        refuse "run accepts only 'make import-erp' or 'make import-vanillasoft', not 'make ${1:-}'"
      import_target="$1"
      RUN_ARGS+=("$1")
      shift
      local vs_history="" vs_floor=""
      for arg in "$@"; do
        name="${arg%%=*}"
        case "$arg" in
          ODOO_DB_NAME=*)
            [ "${arg#ODOO_DB_NAME=}" = "$target" ] || refuse "'$arg' would redirect the import away from the verified clone $target"
            ;;
          ERP_PRODUCTION_PERMIT=* | VANILLASOFT_PRODUCTION_PERMIT=*)
            refuse "'$name=' is not forwarded: the verified clone is never a production target"
            ;;
          *=*)
            if [ "$import_target" = "import-erp" ]; then
              [[ "$name" =~ ^(ERP_[A-Z_]+|LIMIT|DRY|PAYLOAD_ROOT|REPORT_PATH|PARTNERS_ONLY|LAYER)$ ]] ||
                refuse "'$name=' is not an ERP import setting; run does not forward it"
            else
              [[ "$name" =~ ^VANILLASOFT_(CALL_FLOOR|CONTACT_FLOOR|REPORT_PATH|HISTORY_(CENSUS|CENSUS_SHA256|CHECKPOINT|MAX_IDS|FAILURE_BUDGET))$ ]] ||
                refuse "'$name=' is not a VanillaSoft import setting; run does not forward it"
              [ -n "${arg#*=}" ] || refuse "'$name=' must name an explicit value"
              case "$name" in
                VANILLASOFT_HISTORY_*) vs_history=1 ;;
                VANILLASOFT_CALL_FLOOR | VANILLASOFT_CONTACT_FLOOR) vs_floor=1 ;;
              esac
              case "$name" in
                VANILLASOFT_HISTORY_MAX_IDS | VANILLASOFT_HISTORY_FAILURE_BUDGET)
                  [[ "${arg#*=}" =~ ^[1-9][0-9]*$ ]] || refuse "'$name=' must be a positive integer"
                  ;;
              esac
            fi
            ;;
          *) refuse "'$arg' is not accepted after 'make $import_target'" ;;
        esac
        RUN_ARGS+=("$arg")
      done
      [[ " ${RUN_ARGS[*]} " == *" ODOO_DB_NAME=$target "* ]] || refuse "make $import_target must name ODOO_DB_NAME=$target"
      if [ "$import_target" = "import-vanillasoft" ]; then
        if [ -n "$vs_history" ]; then
          # The historical cohort: one mode, every identity input explicit, no window.
          [ -z "$vs_floor" ] ||
            refuse "import-vanillasoft history mode refuses VANILLASOFT_CALL_FLOOR / VANILLASOFT_CONTACT_FLOOR; the rolling window is another import"
          for name in VANILLASOFT_HISTORY_CENSUS VANILLASOFT_HISTORY_CENSUS_SHA256 VANILLASOFT_HISTORY_CHECKPOINT; do
            [[ " ${RUN_ARGS[*]} " == *" $name="* ]] ||
              refuse "import-vanillasoft history mode requires $name"
          done
        else
          [[ " ${RUN_ARGS[*]} " == *" VANILLASOFT_CALL_FLOOR="* ]] ||
            refuse "import-vanillasoft requires VANILLASOFT_CALL_FLOOR (rolling window) or VANILLASOFT_HISTORY_CENSUS (historical cohort)"
          [[ " ${RUN_ARGS[*]} " == *" VANILLASOFT_CONTACT_FLOOR="* ]] ||
            refuse "import-vanillasoft requires VANILLASOFT_CONTACT_FLOOR"
        fi
      fi
      return 0
      ;;
    docker)
      [ "${2:-}" = "compose" ] && [ "${3:-}" = "run" ] || refuse "run accepts 'docker compose run ... odoo', not '$*'"
      shift 3
      while [ $# -gt 0 ] && [ "$1" != "odoo" ]; do
        case "$1" in
          --rm | -T | --no-deps) shift ;;
          -w)
            RUN_OPTS+=("$1" "${2:?-w needs a directory}")
            shift 2
            ;;
          -e)
            [[ "${2:-}" =~ ^[A-Z][A-Z0-9_]*= ]] || refuse "-e needs KEY=VALUE"
            [[ "${2%%=*}" =~ ^(ERP_[A-Z_]+|GATE_URL|L9_[A-Z_]+|VANILLASOFT_(CALL_FLOOR|CONTACT_FLOOR|REPORT_PATH))$ ]] ||
              refuse "-e ${2%%=*} is not forwarded: it could redirect the database or runtime"
            RUN_OPTS+=("$1" "$2")
            shift 2
            ;;
          *) refuse "compose option '$1' is not accepted by run" ;;
        esac
      done
      [ "${1:-}" = "odoo" ] || refuse "run executes only the odoo service"
      shift
      [ "${1:-}" = "odoo" ] && shift
      ;;
  esac
  while [ $# -gt 0 ]; do
    case "$1" in
      -d | --database)
        [ "${2:-}" = "$target" ] || refuse "'$1 ${2:-}' would redirect the run away from the verified clone $target"
        shift 2
        ;;
      --database=*)
        [ "${1#--database=}" = "$target" ] || refuse "'$1' would redirect the run away from the verified clone $target"
        shift
        ;;
      -d*)
        [ "${1#-d}" = "$target" ] || refuse "'$1' would redirect the run away from the verified clone $target"
        shift
        ;;
      # Odoo's option parser accepts any unambiguous prefix of a long option
      # (--db_h is --db_host, --datab is --database) and glued short values
      # (-cFILE), so whole prefixes are refused, not only the full spellings.
      --db* | --dat* | --pg* | --ad* | --con* | -r* | -w* | -c* | -D*)
        refuse "'$1' would redirect the run away from the verified clone $target"
        ;;
      # Any of these starts Odoo's tests (test tags alone enable them), so the
      # run belongs to the test runner, which accepts only its own spellings.
      --test* | -t*)
        test_form=1
        RUN_ARGS+=("$1")
        shift
        ;;
      *)
        RUN_ARGS+=("$1")
        shift
        ;;
    esac
  done
  if [ -n "$test_form" ]; then
    parse_test_args
  fi
}

# Identity and scope check before any test, import, or upgrade touches a database.
assert_clone() {
  local target="$1" comment template tcomment
  validate_clone_name "$target"
  db_exists "$target" || refuse "$target does not exist; run: scripts/test_env.sh clone $target"
  comment="$(db_comment "$target")"
  is_ours "$comment" && [ "$(field "$comment" role)" = "clone" ] ||
    refuse "$target is not a test-env clone (comment: '$comment')"
  [ "$(field "$comment" owner)" = "$OWNER" ] ||
    refuse "$target is owned by '$(field "$comment" owner)', not '$OWNER'"
  [ "$(field "$comment" parity)" = "$PARITY" ] ||
    refuse "$target was cloned with parity '$(field "$comment" parity)'; this run requires '$PARITY'"
  if [ "$(field "$comment" fp)" != "$FP" ]; then
    if [ -n "$PINNED_TEMPLATE" ]; then
      refuse "$target is stale: cloned for inputs $(field "$comment" fp | cut -c1-16), current inputs are ${FP:0:16}. Reclone it from $TEMPLATE_DB. Do not create a template"
    fi
    refuse "$target is stale: cloned for inputs $(field "$comment" fp | cut -c1-16), current inputs are ${FP:0:16}; run: scripts/test_env.sh clone $target"
  fi
  template="$(field "$comment" template)"
  [ "$template" = "$TEMPLATE_DB" ] || refuse "$target was cloned from $template, not the current template $TEMPLATE_DB"
  local migrated_from
  migrated_from="$(field "$comment" migrated_from)"
  if [ -n "$migrated_from" ]; then
    template_admitted_for "$migrated_from" ||
      refuse "$target was migrated from inputs ${migrated_from:0:16}; $template is not the template admitted for them"
  else
    template_ready || refuse "$target's template $template is not an admitted template for the current inputs"
  fi
  tcomment="$(db_comment "$template")"
  echo "✓ $target: clone of $template (parity $PARITY, owner $OWNER, $(field "$tcomment" odoo), chart $(field "$tcomment" chart), $(field "$tcomment" installed) modules)"
}

TEST_ROSTER=""
TEST_SCOPE=""
TEST_TAGS=""
TEST_EXCLUDED=""
# An installable module named under excluded_modules in config/odoo_module_order.yaml.
# It is never named in -u; Odoo installs some of them on the Enterprise fixture anyway
# (auto_install). Its tests are admitted only when the fixture has it installed, which
# require_excluded_installed proves after Docker. Reads files only; prints nothing for
# any other name.
excluded_installable() {
  python3 - "$1" <<'PY'
import ast, pathlib, re, sys
name = sys.argv[1]
if not re.fullmatch(r"plasticos_[a-z0-9_]+", name):
    sys.exit(0)
listed, inside = set(), False
for line in pathlib.Path("config/odoo_module_order.yaml").read_text(encoding="utf-8").splitlines():
    if re.match(r"^excluded_modules:\s*$", line):
        inside = True
        continue
    if inside:
        item = re.match(r"^\s+-\s+([a-z0-9_]+)", line)
        if item:
            listed.add(item.group(1))
        elif line.strip() and not line.startswith((" ", "#")):
            inside = False
manifest = pathlib.Path(name) / "__manifest__.py"
if name in listed and manifest.is_file():
    if ast.literal_eval(manifest.read_text(encoding="utf-8")).get("installable", True):
        print(name)
PY
}

# The scope is checked before Docker: declared PlasticOS modules, or the roster.
# An installable excluded module is admitted provisionally here and refused after
# Docker unless the admitted fixture has it installed.
test_scope() {
  local m modules=()
  TEST_SCOPE="$1"
  TEST_ROSTER="$(python3 scripts/get_odoo_module_order.py)"
  [ -n "$TEST_ROSTER" ] || refuse "scripts/get_odoo_module_order.py declared no PlasticOS modules"
  read -r -a modules <<<"${TEST_SCOPE:-${TEST_ROSTER//,/ }}"
  TEST_TAGS=""
  TEST_EXCLUDED=""
  for m in ${modules[@]+"${modules[@]}"}; do
    if [[ ",$TEST_ROSTER," != *",$m,"* ]]; then
      [ "$(excluded_installable "$m")" = "$m" ] ||
        refuse "'$m' is not a declared PlasticOS module (config/odoo_module_order.yaml); the fixture does not install it"
      TEST_EXCLUDED="${TEST_EXCLUDED}${TEST_EXCLUDED:+ }$m"
    fi
    TEST_TAGS="${TEST_TAGS}${TEST_TAGS:+,}/$m"
  done
  [ -n "$TEST_TAGS" ] || refuse "the test scope '$TEST_SCOPE' names no module"
}

# After assert_clone: each provisionally admitted excluded module must be installed
# in the fixture. The admitted template refuses connections, so its state is read
# from the verified clone, a copy of that template. Read only.
require_excluded_installed() {
  local target="$1" m state
  for m in $TEST_EXCLUDED; do
    state="$(psql_on "$target" "SELECT state FROM ir_module_module WHERE name = '$m'")"
    [ "$state" = "installed" ] ||
      refuse "'$m' is excluded from the roster and is not installed in the admitted fixture (state: ${state:-absent}); its tests cannot run here"
  done
}

# A --test-enable run is the test runner. It accepts the Makefile test recipes'
# arguments and one -u list, which becomes the test scope. The runner sets the
# upgrade, the test tags, and the log level itself; anything else is refused.
parse_test_args() {
  local scope="" seen=""
  set -- ${RUN_ARGS[@]+"${RUN_ARGS[@]}"}
  while [ $# -gt 0 ]; do
    case "$1" in
      --test-enable | --stop-after-init | --log-level=test) shift ;;
      -u | --update | --update=*)
        [ -z "$seen" ] || refuse "a test run takes one -u list"
        seen=1
        if [ "$1" = "${1#--update=}" ]; then
          scope="${2:-}"
          shift $(($# > 1 ? 2 : 1))
        else
          scope="${1#--update=}"
          shift
        fi
        [ -n "$scope" ] || refuse "-u needs a module"
        ;;
      *) refuse "'$1' is not accepted in a test run: the runner sets the upgrade, the test tags, and the log level itself" ;;
    esac
  done
  RUN_MODE="test"
  test_scope "${scope//,/ }"
}

# Odoo tests on an owned clone. Without -u, Odoo runs at_install and post_install
# tests for every loaded module (core and Enterprise included) against whatever
# schema the fixture was built with. Here every declared PlasticOS module is
# upgraded on the clone, so the source on disk is what is tested; Odoo also
# upgrades the PlasticOS modules that depend on them, and nothing else. Tests are
# restricted to the roster, or to one module. Odoo's own summary line is the
# evidence: a missing line, a failure, an error, or zero tests fails the run.
# The fingerprint leaves addon source out, so the receipt names the source that
# was tested: its digest, the Git head, and whether the worktree differs from
# that head. Source that changes during the run was not the source tested, and
# gets no receipt.
run_tests() {
  local target="$1" scope="${TEST_SCOPE// /,}" log receipt rc=0 summary failed errors total head changes dirty=false
  mkdir -p "$EVIDENCE_DIR"
  log="$EVIDENCE_DIR/${target}.test.log"
  receipt="$EVIDENCE_DIR/${target}.test-receipt.json"
  rm -f "$receipt"
  head="$(git -C "$ROOT" rev-parse --verify -q HEAD)" || die "cannot name the Git head of $ROOT; a receipt must name the tested revision"
  changes="$(git -C "$ROOT" --no-optional-locks status --porcelain)" || die "cannot read the worktree state of $ROOT"
  [ -z "$changes" ] || dirty=true
  echo "→ Upgrading $(tr ',' '\n' <<<"$TEST_ROSTER" | wc -l | tr -d ' ') PlasticOS modules on $target; tests: ${scope:-the PlasticOS roster}"
  compose run --rm --no-deps -T ${RUN_OPTS[@]+"${RUN_OPTS[@]}"} odoo odoo --test-enable --stop-after-init --log-level=test \
    -u "$TEST_ROSTER" --test-tags "$TEST_TAGS" -d "$target" --addons-path="$(addons_path)" </dev/null 2>&1 |
    tee "$log" || rc=$?
  [ "$(addon_source)" = "$TEST_SOURCE" ] ||
    die "PlasticOS addon source changed during the run on $target; it is not the source that was tested (no receipt written)"
  summary="$(grep -E "odoo\.tests\.result: [0-9]+ failed, [0-9]+ error\(s\) of [0-9]+ tests when loading database '$target'" "$log" | tail -1 || true)"
  [ -n "$summary" ] ||
    die "no Odoo test summary for $target (exit $rc); the run is not evidence of anything (log: ${log#"$ROOT"/})"
  read -r failed errors total < <(sed -E 's/.*: ([0-9]+) failed, ([0-9]+) error\(s\) of ([0-9]+) tests .*/\1 \2 \3/' <<<"$summary")
  printf '{"database": "%s", "template": "%s", "fingerprint": "%s", "head": "%s", "dirty": %s, "source": "%s", "scope": "%s", "upgraded": "%s", "tests": %d, "failed": %d, "errors": %d, "exit": %d, "log": "%s"}\n' \
    "$target" "$TEMPLATE_DB" "$FP" "$head" "$dirty" "$TEST_SOURCE" "${scope:-roster}" "$TEST_ROSTER" "$total" "$failed" "$errors" "$rc" "${log#"$ROOT"/}" >"$receipt"
  echo "tests: $total run, $failed failed, $errors error(s) on $target (scope ${scope:-roster}; receipt ${receipt#"$ROOT"/})"
  [ "$total" -gt 0 ] || die "zero tests ran for ${scope:-the PlasticOS roster}; an empty run is a failure"
  [ "$failed" -eq 0 ] && [ "$errors" -eq 0 ] || die "$failed failed, $errors error(s) of $total tests"
  [ "$rc" -eq 0 ] || die "odoo exited with status $rc after $total passing tests (log: ${log#"$ROOT"/})"
  stamp_upgraded "$target" "$TEST_SOURCE"
}

# A clone starts with the fixture's PlasticOS schema and data, not the source on
# disk. Before an import or any other Odoo command runs on it, the declared
# roster is upgraded, once per addon source digest; the digest is stamped on
# the clone as src=. The upgrade reads no stdin: a piped shell script is for
# the command that follows, not for this stage.
TEST_SOURCE=""
addon_source() { content_digest git "$ROOT" 'plasticos_*'; }
stamp_upgraded() {
  local comment
  comment="$(db_comment "$1")"
  set_comment "$1" "$(printf '%s' "$comment" | sed 's| src=[^ ]*||') src=$2"
}
ensure_clone_upgraded() {
  local target="$1" roster
  [ "$(field "$(db_comment "$target")" src)" = "$TEST_SOURCE" ] && return 0
  roster="$(python3 scripts/get_odoo_module_order.py)"
  echo "→ Upgrading $(tr ',' '\n' <<<"$roster" | wc -l | tr -d ' ') PlasticOS modules on $target to the source on disk"
  compose run --rm --no-deps -T odoo odoo -u "$roster" --stop-after-init --workers=0 --max-cron-threads=0 --no-http \
    -d "$target" --addons-path="$(addons_path)" </dev/null ||
    die "upgrading the PlasticOS roster on $target failed; nothing else ran on it"
  stamp_upgraded "$target" "$TEST_SOURCE"
}

# ---------------------------------------------------------------------------
# Export campaign S6 (2026-11-12): template source, cross-tree migration, backup and restore
# ---------------------------------------------------------------------------
# F4. The fixture installs the PlasticOS source on disk and its fingerprint leaves
# that source out, so a template admitted from an edited tree silently carries the
# edit. The admission is refused while a plasticos_* path differs from the Git head,
# and the ready marker names that head and the addon digest; `status` shows them.
require_declared_template_source() {
  local head changes
  head="$(git -C "$ROOT" rev-parse --verify -q HEAD)" ||
    refuse "cannot name the Git head of $ROOT; a template is admitted only from a committed tree"
  changes="$(git -C "$ROOT" --no-optional-locks status --porcelain -- 'plasticos_*')" ||
    refuse "cannot read the worktree state of $ROOT"
  [ -z "$changes" ] ||
    refuse "PlasticOS addon source in $ROOT differs from its Git head ${head:0:12}; the template installs the source on disk and its fingerprint leaves that source out. Admit it from a clean checkout"
}
BUILD_SOURCE_MARKER=""
BUILD_SOURCE_DIGEST=""
template_source_marker() {
  echo "srchead=$(git -C "$ROOT" rev-parse --verify -q HEAD) srcdigest=$(addon_source)"
}

# An admitted template whose recorded fp is exactly $1 (the fp the clone was made for).
template_admitted_for() {
  local comment
  db_exists "$TEMPLATE_DB" || return 1
  comment="$(db_comment "$TEMPLATE_DB")"
  is_ours "$comment" && [ "$(field "$comment" role)" = "template" ] && [ "$(field "$comment" state)" = "ready" ] &&
    [ "$(field "$comment" parity)" = "$PARITY" ] && [ "$(field "$comment" fp)" = "$1" ]
}

# Content digest of the fingerprint's config files as they are at Git revision $1.
config_digest_at() {
  local rev="$1" tmp listed
  local -a paths=()
  tmp="$(mktemp -d)"
  listed="$(git -C "$ROOT" ls-tree -r --name-only "$rev" -- "${MIGRATE_CONFIG_FILES[@]}")" || {
    rm -rf "$tmp"
    return 1
  }
  local path
  # bash 3.2 (macOS /bin/bash) has no mapfile.
  while IFS= read -r path; do
    [ -z "$path" ] || paths+=("$path")
  done <<<"$listed"
  if [ "${#paths[@]}" -gt 0 ]; then
    git -C "$ROOT" archive "$rev" -- "${paths[@]}" | tar -x -C "$tmp"
  fi
  content_digest dir "$tmp"
  rm -rf "$tmp"
}
MIGRATE_CONFIG_FILES=(config/odoo.conf config/odoo_module_order.yaml docker-compose.yml Dockerfile requirements.txt constraints.txt scripts/get_odoo_module_order.py)

# Content digest of the PlasticOS addon source as it is at Git revision $1, in the same
# form as addon_source (relative path and content of every file under plasticos_*).
addon_digest_at() {
  local rev="$1" tmp
  tmp="$(mktemp -d)"
  if ! git -C "$ROOT" archive "$rev" -- 'plasticos_*' | tar -x -C "$tmp"; then
    rm -rf "$tmp"
    return 1
  fi
  content_digest dir "$tmp"
  rm -rf "$tmp"
}

# config/odoo_module_order.yaml at Git revision $1 against the working tree: every
# top-level key holds the same list, except default_install_order, which may only gain
# entries at its end. Comments are ignored. Prints nothing; exit status is the verdict.
module_order_append_only() {
  local rev="$1" old
  old="$(git -C "$ROOT" show "$rev:config/odoo_module_order.yaml")" || return 1
  python3 - "$ROOT/config/odoo_module_order.yaml" "$old" <<'PY'
import re, sys

def parse(text):
    keys, key = {}, None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line:
            continue
        top = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if top:
            key = top.group(1)
            keys[key] = [top.group(2)] if top.group(2) else []
            continue
        item = re.match(r"^\s+-\s+(\S+)\s*$", line)
        if item and key is not None:
            keys[key].append(item.group(1))
        elif key is not None:
            keys[key].append(line.strip())
    return keys

new = parse(open(sys.argv[1], encoding="utf-8").read())
old = parse(sys.argv[2])
if set(new) != set(old):
    sys.exit(1)
for key, items in old.items():
    if key == "default_install_order":
        if new[key][: len(items)] != items:
            sys.exit(1)
    elif new[key] != items:
        sys.exit(1)
PY
}

# F8. `migrate <db> <from-rev>` upgrades an owned clone that was cloned in another
# checkout of this repository (a clean Staging tree) to the source on disk, when the
# two trees differ only by PlasticOS modules appended to the roster. Every other
# fingerprint input must be the same, proved against the template's recorded inputs.
# The clone keeps its template; it is stamped migrated_from=<its old fp>, and later
# runs check it against the template admitted for those inputs. The Odoo log is the
# migration evidence.
migrate_clone() {
  local target="$1" rev="$2" comment old evidence current changed old_modules new_modules added roster existing
  local log rc pending missing head
  [[ "$rev" =~ ^[0-9a-f]{7,40}$ ]] || refuse "migrate needs the source revision the clone was made from (a Git sha)"
  rev="$(git -C "$ROOT" rev-parse --verify -q "${rev}^{commit}")" || refuse "'$2' is not a commit of this repository"
  comment="$(db_comment "$target")"
  is_ours "$comment" && [ "$(field "$comment" role)" = "clone" ] ||
    refuse "$target is not a test-env clone (comment: '$comment')"
  [ "$(field "$comment" owner)" = "$OWNER" ] || refuse "$target is owned by '$(field "$comment" owner)', not '$OWNER'"
  [ "$(field "$comment" parity)" = "$PARITY" ] || refuse "$target was cloned with parity '$(field "$comment" parity)'"
  [ "$(field "$comment" template)" = "$TEMPLATE_DB" ] || refuse "$target was not cloned from $TEMPLATE_DB"
  [ -z "$(field "$comment" migrated_from)" ] || refuse "$target was already migrated; clone again to migrate again"
  old="$(field "$comment" fp)"
  [ "$old" != "$FP" ] || refuse "$target already matches the current inputs; nothing to migrate (use upgrade)"
  template_admitted_for "$old" || refuse "$TEMPLATE_DB is not the template admitted for $target's inputs ${old:0:16}"
  evidence="$(fixture_evidence "$old")"
  [ -n "$evidence" ] || refuse "no recorded inputs of $TEMPLATE_DB hash to ${old:0:16}; the migration source is unproven"
  [ "$(sed -n 's/^config=//p' "$evidence")" = "$(config_digest_at "$rev")" ] ||
    refuse "the recorded config digest of ${old:0:16} is not the config at ${rev:0:12}"
  current="$(fingerprint_inputs)"
  changed="$(changed_input_keys "$evidence" "$current")"
  case "$changed" in
    config,modules | modules) ;;
    *) refuse "inputs other than the module roster changed since ${old:0:16} (${changed:-none})" ;;
  esac
  local -a others=()
  local file
  for file in "${MIGRATE_CONFIG_FILES[@]}"; do
    [ "$file" = config/odoo_module_order.yaml ] || others+=("$file")
  done
  git -C "$ROOT" diff --quiet "$rev" -- "${others[@]}" ||
    refuse "a fingerprint config file other than config/odoo_module_order.yaml differs from ${rev:0:12}"
  old_modules="$(sed -n 's/^modules=//p' "$evidence")"
  new_modules="$(printf '%s\n' "$current" | sed -n 's/^modules=//p')"
  case "$new_modules" in
    "$old_modules",?*) added="${new_modules#"$old_modules",}" ;;
    *) refuse "the roster is not the recorded roster with modules appended" ;;
  esac
  module_order_append_only "$rev" ||
    refuse "config/odoo_module_order.yaml changed beyond entries appended to default_install_order since ${rev:0:12}"
  local module
  for module in ${added//,/ }; do
    [[ "$module" =~ ^[a-z0-9_]+$ ]] || refuse "'$module' is not a module name"
  done
  # The fingerprint leaves addon source out, so <from-rev> is bound to the source the
  # template installed: its recorded srcdigest, or, for a template admitted before that
  # was recorded, an explicit acknowledgement naming the full revision (PR #480 review).
  local tcomment srcdigest atrev binding
  tcomment="$(db_comment "$TEMPLATE_DB")"
  srcdigest="$(field "$tcomment" srcdigest)"
  if [ -n "$srcdigest" ]; then
    atrev="$(addon_digest_at "$rev")" || refuse "cannot read the PlasticOS addon source at ${rev:0:12}"
    [ "$atrev" = "$srcdigest" ] ||
      refuse "the PlasticOS addon source at ${rev:0:12} is not the source $TEMPLATE_DB was admitted from (srcdigest ${srcdigest:0:16}, at ${rev:0:12}: ${atrev:0:16})"
    binding="source bound: the addon digest at $rev equals the template srcdigest $srcdigest"
  else
    [ "${TEST_ENV_MIGRATE_SOURCE_ACK:-}" = "$rev" ] ||
      refuse "$TEMPLATE_DB records no addon source (admitted before the source was recorded). Name the tree it was admitted from: TEST_ENV_MIGRATE_SOURCE_ACK=<full 40-character sha of ${rev:0:12}>"
    binding="source bound by acknowledgement: TEST_ENV_MIGRATE_SOURCE_ACK=$rev (the template records no addon source)"
  fi
  roster="$(python3 scripts/get_odoo_module_order.py)"
  existing="$(tr ',' '\n' <<<"$roster" | grep -vxF -f <(tr ',' '\n' <<<"$added") | paste -sd, -)"
  head="$(git -C "$ROOT" rev-parse --verify -q HEAD)"
  TEST_SOURCE="$(addon_source)"
  mkdir -p "$EVIDENCE_DIR"
  log="$EVIDENCE_DIR/${target}.migrate.log"
  echo "→ Migrating $target from ${rev:0:12} (inputs ${old:0:16}) to ${head:0:12} (inputs ${FP:0:16}): -u existing roster, -i $added"
  echo "→ $binding" | tee "$log"
  rc=0
  compose run --rm --no-deps -T odoo odoo -u "$existing" -i "$added" --stop-after-init --workers=0 \
    --max-cron-threads=0 --no-http --log-level=info -d "$target" --addons-path="$(addons_path)" </dev/null 2>&1 |
    tee -a "$log" || rc=$?
  [ "$(addon_source)" = "$TEST_SOURCE" ] || die "PlasticOS addon source changed during the migration of $target"
  [ "$rc" -eq 0 ] || die "the migration of $target failed (exit $rc; log: ${log#"$ROOT"/}); its marker is unchanged"
  pending="$(psql_on "$target" "SELECT string_agg(name || ':' || state, ',') FROM ir_module_module
                                WHERE state IN ('to install', 'to upgrade', 'to remove')")"
  [ -z "$pending" ] || die "modules left mid-transition on $target: $pending"
  missing="$(psql_on "$target" "SELECT string_agg(m, ',') FROM unnest(string_to_array('$added', ',')) AS m
                                WHERE m NOT IN (SELECT name FROM ir_module_module WHERE state = 'installed')")"
  [ -z "$missing" ] || die "added modules not installed on $target: $missing"
  set_comment "$target" "$(printf '%s' "$comment" | sed "s| fp=[^ ]*| fp=$FP|; s| src=[^ ]*||") migrated_from=$old fromrev=$rev migrated=$(utc_now) src=$TEST_SOURCE"
  echo "✅ $target migrated to ${head:0:12} (inputs ${FP:0:16}; log ${log#"$ROOT"/})"
}

# F9. A coherent backup of an owned clone with Odoo's own filestore-aware manager:
# one zip holding dump.sql, the filestore and manifest.json. Its checksum, the
# clone's marker, and the code revision are recorded beside it.
BACKUP_DIR=""
backup_clone() {
  local target="$1" zip head dirty sha
  BACKUP_DIR="$EVIDENCE_DIR/backup"
  mkdir -p "$BACKUP_DIR"
  zip="$BACKUP_DIR/${target}.zip"
  head="$(git -C "$ROOT" rev-parse --verify -q HEAD)" || die "cannot name the Git head of $ROOT"
  dirty=false
  [ -z "$(git -C "$ROOT" --no-optional-locks status --porcelain)" ] || dirty=true
  # shellcheck disable=SC2046 # word-split the fixed manager arguments
  compose run --rm --no-deps -T odoo odoo $(db_manager_args "$(addons_path)") dump "$target" - </dev/null >"$zip" ||
    die "odoo db dump of $target failed"
  python3 -c 'import sys, zipfile; z = zipfile.ZipFile(sys.argv[1]); assert "dump.sql" in z.namelist()' "$zip" ||
    die "the dump of $target is not an Odoo backup zip with dump.sql"
  sha="$(sha256 <"$zip")"
  printf '{"database": "%s", "zip": "%s", "sha256": "%s", "head": "%s", "dirty": %s, "marker": "%s", "taken": "%s"}\n' \
    "$target" "${zip#"$ROOT"/}" "$sha" "$head" "$dirty" "$(db_comment "$target")" "$(utc_now)" >"$zip.json"
  echo "✅ backup of $target: ${zip#"$ROOT"/} sha256=$sha (code $head, dirty=$dirty)"
}

# Restore a backup taken by backup_clone into an absent or owned target clone. The
# zip must still hash to its recorded checksum. The target inherits the source
# clone's lineage (template, fp, migration) and records what it was restored from.
restore_clone() {
  local source="$1" target="$2" zip meta sha marker staged copy token
  BACKUP_DIR="$EVIDENCE_DIR/backup"
  zip="$BACKUP_DIR/${source}.zip"
  meta="$zip.json"
  [ -f "$zip" ] && [ -f "$meta" ] || refuse "no backup of $source under ${BACKUP_DIR#"$ROOT"/}"
  # Copy first, then verify the copy: what is loaded is exactly what was checked.
  copy="$(mktemp "$BACKUP_DIR/.restore-${target}.XXXXXX")"
  cp "$zip" "$copy"
  sha="$(sha256 <"$copy")"
  if [ "$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["sha256"])' "$meta")" != "$sha" ]; then
    rm -f "$copy"
    refuse "the backup of $source no longer matches its recorded checksum"
  fi
  marker="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["marker"])' "$meta")"
  # The marker is written into a SQL literal below: every token must already be marker-safe.
  for token in $marker; do
    if [ "$(marker_safe "$token")" != "$token" ]; then
      rm -f "$copy"
      refuse "the backup of $source carries an unsafe marker"
    fi
  done
  if ! { is_ours "$marker" && [ "$(field "$marker" role)" = "clone" ] && [ "$(field "$marker" owner)" = "$OWNER" ]; }; then
    rm -f "$copy"
    refuse "the backup of $source is not of a clone owned by $OWNER"
  fi
  assert_owned_or_absent "$target"
  drop_owned_clone "$target"
  clear_filestore "$target"
  staged="/var/lib/odoo/restore-${target}.zip"
  if ! compose run --rm --no-deps -T --entrypoint sh odoo -c "cat > '$staged'" <"$copy"; then
    rm -f "$copy"
    die "could not stage the backup for $target"
  fi
  rm -f "$copy"
  # shellcheck disable=SC2046 # word-split the fixed manager arguments
  compose run --rm --no-deps -T odoo odoo $(db_manager_args "$(addons_path)") load "$target" "$staged" </dev/null ||
    die "odoo db load into $target failed"
  compose run --rm --no-deps -T --entrypoint rm odoo -f "$staged" >/dev/null || true
  set_comment "$target" "$(printf '%s' "$marker" | sed 's| created=[^ ]*||; s| src=[^ ]*||; s| restored_from=[^ ]*||; s| backup=[^ ]*||') created=$(utc_now) restored_from=$source backup=$sha"
  echo "✅ $target restored from the backup of $source (sha256 $sha)"
}

status() {
  echo "owner:        $OWNER (default clone $DEFAULT_CLONE)"
  echo "parity:       $PARITY"
  echo "fingerprint:  $FP"
  echo "source:       $(addon_source) (PlasticOS addons; upgraded on each clone, not part of the fingerprint)"
  echo "template:     $TEMPLATE_DB ($(template_ready && echo ready || { db_exists "$TEMPLATE_DB" && echo "not admitted for the current inputs"; } || echo absent))"
  if db_exists "$TEMPLATE_DB"; then
    local tcomment
    tcomment="$(db_comment "$TEMPLATE_DB")"
    if [ -n "$(field "$tcomment" srchead)" ]; then
      echo "template src: head $(field "$tcomment" srchead), addons $(field "$tcomment" srcdigest)"
    else
      echo "template src: not recorded (admitted before the source was recorded)"
    fi
  fi
  if [ -n "$PINNED_TEMPLATE" ]; then
    echo "fixture:      canonical; a new template is refused unless this database is absent and TEST_ENV_ALLOW_NEW_TEMPLATE equals its name"
  fi
  fingerprint_inputs | sed 's/^/  input  /'
  psql_admin "SELECT datname, coalesce(shobj_description(oid, 'pg_database'), '') FROM pg_database
              WHERE datname LIKE 'odoo\_test\_%' ORDER BY datname" | while IFS='|' read -r name comment; do
    printf '  db     %-40s role=%s owner=%s parity=%s state=%s\n' "$name" "$(field "$comment" role)" \
      "$(field "$comment" owner)$(field "$comment" builder)" "$(field "$comment" parity)" "$(field "$comment" state)"
  done
}

main() {
  local command="${1:-}" target
  case "$command" in
    name)
      echo "$DEFAULT_CLONE"
      exit 0
      ;;
    smoke-name)
      echo "odoo_test_smoke_${OWNER}"
      exit 0
      ;;
    clone | drop | assert-clone | upgrade) validate_clone_name "${2:-$DEFAULT_CLONE}" ;;
    migrate | backup) validate_clone_name "${2:-}" ;;
    restore)
      validate_clone_name "${2:-}"
      validate_clone_name "${3:-}"
      [ "$2" != "$3" ] || refuse "restore needs a target other than the backed-up clone"
      ;;
    run)
      validate_clone_name "${2:-}"
      parse_run "$2" "${@:3}"
      ;;
    template | status | rebuild | identity) ;;
    *)
      echo "usage: $0 template | rebuild | clone [db] | upgrade <db> | migrate <db> <from-rev> | backup <db> | restore <db> <target> | run <db> -- <odoo args> | assert-clone <db> | drop <db> | status | identity | name | smoke-name" >&2
      exit 2
      ;;
  esac

  ensure_db_service
  ensure_odoo_image
  compute_fingerprint
  case "$command" in
    template) build_template ;;
    rebuild) rebuild_pinned_template ;;
    identity)
      echo "fingerprint=$FP"
      echo "source=$(addon_source)"
      ;;
    clone) clone_template "${2:-$DEFAULT_CLONE}" ;;
    upgrade)
      target="$2"
      lease "db:$target" exclusive
      assert_clone "$target"
      TEST_SOURCE="$(addon_source)"
      ensure_clone_upgraded "$target"
      echo "fingerprint=$FP"
      echo "source=$TEST_SOURCE"
      ;;
    assert-clone) assert_clone "$2" ;;
    migrate)
      target="$2"
      lease "db:$target" exclusive
      # The template the clone is checked against cannot be rebuilt or dropped mid-run.
      lease "tpl:$TEMPLATE_DB" shared
      db_exists "$target" || refuse "$target does not exist"
      migrate_clone "$target" "${3:-}"
      ;;
    backup)
      lease "db:$2" exclusive
      assert_clone "$2"
      backup_clone "$2"
      ;;
    restore)
      # The source is the recorded zip, not the clone, so only the target is leased.
      lease "db:$3" exclusive
      restore_clone "$2" "$3"
      ;;
    drop)
      lease "db:$2" exclusive
      db_exists "$2" || refuse "$2 does not exist"
      drop_owned_clone "$2"
      echo "✅ dropped $2"
      ;;
    run)
      target="$2"
      # The lease comes first and is held until this process exits, so the
      # clone verified below is the one the command runs on: no clone, drop,
      # or other run of it can start in between.
      lease "db:$target" exclusive
      assert_clone "$target"
      if [ "$RUN_MODE" = "test" ]; then
        require_excluded_installed "$target"
      fi
      TEST_SOURCE="$(addon_source)"
      if [ "$RUN_MODE" != "test" ]; then
        ensure_clone_upgraded "$target"
      fi
      if [ "$RUN_MODE" = "make" ]; then
        # The import's own `docker compose` is bound to this repository's
        # verified file and project. make reads MAKEFILES and MAKEFLAGS from the
        # environment, and an `override` line in a makefile named there beats
        # ODOO_DB_NAME on the command line, so both are cleared.
        # TEST_ENV_VERIFIED_CLONE makes the import recipes refuse any other
        # database and their no-Docker fallback, which targets a server none of
        # the checks above inspected.
        env -u MAKEFILES -u MAKEFLAGS -u MFLAGS -u GNUMAKEFLAGS \
          COMPOSE_FILE="$COMPOSE_FILE_HERE" COMPOSE_PROJECT_NAME="$PROJECT" TEST_ENV_VERIFIED_CLONE="$target" \
          "${RUN_ARGS[@]}"
      elif [ "$RUN_MODE" = "test" ]; then
        run_tests "$target"
      else
        local tty=()
        [ -t 0 ] || tty=(-T)
        # Subcommand (e.g. shell) first, then the verified database and addons path.
        # ${a[@]+"${a[@]}"}: bash 3.2 (macOS /bin/bash) treats an empty array as unbound
        # under set -u, and with the EXIT trap installed the script then exits 0.
        compose run --rm --no-deps ${tty[@]+"${tty[@]}"} ${RUN_OPTS[@]+"${RUN_OPTS[@]}"} \
          odoo odoo ${RUN_ARGS[@]+"${RUN_ARGS[@]}"} -d "$target" --addons-path="$(addons_path)"
      fi
      ;;
    status) status ;;
  esac
}

# One line, so editing this file while a long build runs cannot change what runs next.
main "$@"; exit $?
