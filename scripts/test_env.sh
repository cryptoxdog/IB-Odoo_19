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
#   scripts/test_env.sh assert-clone <db>     verify identity and scope; exit non-zero otherwise
#   scripts/test_env.sh drop <db>             drop an owned clone (database and filestore)
#   scripts/test_env.sh status                fingerprint inputs, templates, and clones
#   scripts/test_env.sh name                  this worktree's default clone name (no Docker needed)
#
# Environment:
#   TEST_ENV_PARITY      enterprise (default) | community. community is a deliberate,
#                        separately named, non-production template; it is never used
#                        unless asked for.
#   ODOO_ENTERPRISE_PATH host directory mounted as /mnt/enterprise (default ./odoo-enterprise).
#   TEST_ENV_OWNER       owner identity stamped on clones (default: derived from this
#                        worktree's path, so two worktrees never share one).
#   TEST_ENV_LOCK_TIMEOUT seconds to wait for another agent's lease (default 3600).
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
#   * Templates are keyed by a fingerprint of the Odoo image, the Enterprise
#     checkout, the Postgres major version, the module list, every PlasticOS addon
#     file, and the runtime configuration. Different inputs use a different template.
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
lease() {
  local key="$1" fn="pg_advisory_lock" token waited=0
  [ "$2" = "shared" ] && fn="pg_advisory_lock_shared"
  lease_open
  token="granted-$RANDOM$RANDOM"
  printf "SELECT %s(hashtextextended('%s:%s', 0)); SELECT '%s';\n" "$fn" "$SCHEMA" "$key" "$token" >&9
  until grep -qx "$token" "$LEASE_DIR/out"; do
    kill -0 "$LEASE_PID" 2>/dev/null || die "lease session ended: $(cat "$LEASE_DIR/out")"
    if [ "$waited" -eq 2 ]; then
      echo "→ waiting for lease '$key' (held by: $(lease_holders))"
    fi
    [ "$waited" -ge "$LOCK_TIMEOUT" ] && die "timed out after ${LOCK_TIMEOUT}s waiting for lease '$key'"
    sleep 1
    waited=$((waited + 1))
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
    echo "tree:$(content_digest tree "$dir")"
  fi
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
# The image's layers and runtime config. Not .Id: with the containerd image
# store every cached rebuild gets a new index digest (provenance timestamps)
# for byte-identical content.
image_id() {
  echo "content:$(docker image inspect --format '{{json .RootFS.Layers}}{{json .Config}}' "$ODOO_IMAGE" | sha256)"
}

fingerprint_inputs() {
  echo "schema=$SCHEMA"
  echo "recipe=us-company-before-accounting"
  echo "parity=$PARITY"
  echo "image=$(image_id)"
  echo "postgres=$(psql_admin "SELECT current_setting('server_version_num')::int / 10000")"
  echo "modules=$(module_list)"
  echo "addons=$(content_digest git "$ROOT" 'plasticos_*')"
  echo "config=$(content_digest git "$ROOT" config/odoo.conf config/odoo_module_order.yaml docker-compose.yml Dockerfile requirements.txt constraints.txt scripts/get_odoo_module_order.py)"
  if [ "$PARITY" = "ee" ]; then echo "enterprise=$(enterprise_revision)"; fi
}

FP=""
TEMPLATE_DB=""
BUILD_DB=""
compute_fingerprint() {
  FP="$(fingerprint_inputs | sha256)"
  TEMPLATE_DB="odoo_test_tpl_${PARITY}_${FP:0:16}"
  BUILD_DB="odoo_test_bld_${PARITY}_${FP:0:16}"
}

template_ready() {
  local comment
  db_exists "$TEMPLATE_DB" || return 1
  comment="$(db_comment "$TEMPLATE_DB")"
  is_ours "$comment" && [ "$(field "$comment" role)" = "template" ] && [ "$(field "$comment" state)" = "ready" ] &&
    [ "$(field "$comment" fp)" = "$FP" ] && [ "$(field "$comment" parity)" = "$PARITY" ]
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

# ---------------------------------------------------------------------------
# Template lifecycle
# ---------------------------------------------------------------------------
build_template() {
  local modules comment state started
  lease "tpl:$TEMPLATE_DB" exclusive
  if template_ready; then
    echo "✅ $TEMPLATE_DB is current (fingerprint ${FP:0:16}); reusing it"
    unlease "tpl:$TEMPLATE_DB" exclusive
    retire_own_templates
    return 0
  fi
  if db_exists "$TEMPLATE_DB"; then
    refuse "$TEMPLATE_DB exists but is not an admitted template (comment: '$(db_comment "$TEMPLATE_DB")'); not touching it"
  fi
  modules="$(module_list)"
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
  # Stamp ready on the build name, then rename: the template name only ever
  # exists for an admitted database.
  set_comment "$BUILD_DB" "$SCHEMA role=template state=ready parity=$PARITY fp=$FP builder=$OWNER built=$(utc_now) enterprise=$(marker_safe "$(enterprise_revision)") $ADMISSION"
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
# Anything that would point Odoo, Postgres, or compose elsewhere is refused.
RUN_MODE=""
RUN_OPTS=()
RUN_ARGS=()
parse_run() {
  local target="$1" arg name
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
      [ "${1:-}" = "import-erp" ] || refuse "run accepts only 'make import-erp', not 'make ${1:-}'"
      RUN_ARGS+=("$1")
      shift
      for arg in "$@"; do
        name="${arg%%=*}"
        case "$arg" in
          ODOO_DB_NAME=*)
            [ "${arg#ODOO_DB_NAME=}" = "$target" ] || refuse "'$arg' would redirect the import away from the verified clone $target"
            ;;
          *=*)
            [[ "$name" =~ ^(ERP_[A-Z_]+|LIMIT|DRY|PAYLOAD_ROOT|REPORT_PATH|PARTNERS_ONLY|LAYER)$ ]] ||
              refuse "'$name=' is not an ERP import setting; run does not forward it"
            ;;
          *) refuse "'$arg' is not accepted after 'make import-erp'" ;;
        esac
        RUN_ARGS+=("$arg")
      done
      [[ " ${RUN_ARGS[*]} " == *" ODOO_DB_NAME=$target "* ]] || refuse "make import-erp must name ODOO_DB_NAME=$target"
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
            [[ "${2%%=*}" =~ ^(ERP_[A-Z_]+|GATE_URL|L9_[A-Z_]+)$ ]] ||
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
      --db-filter* | --db_host* | --db_port* | --db_user* | --db_password* | -r | -w | --pg_path* | \
        --addons-path* | -c | --config* | -D | --data-dir*)
        refuse "'$1' would redirect the run away from the verified clone $target"
        ;;
      *)
        RUN_ARGS+=("$1")
        shift
        ;;
    esac
  done
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
  [ "$(field "$comment" fp)" = "$FP" ] ||
    refuse "$target is stale: cloned for inputs $(field "$comment" fp | cut -c1-16), current inputs are ${FP:0:16}; run: scripts/test_env.sh clone $target"
  template="$(field "$comment" template)"
  [ "$template" = "$TEMPLATE_DB" ] || refuse "$target was cloned from $template, not the current template $TEMPLATE_DB"
  template_ready || refuse "$target's template $template is not an admitted template for the current inputs"
  tcomment="$(db_comment "$template")"
  echo "✓ $target: clone of $template (parity $PARITY, owner $OWNER, $(field "$tcomment" odoo), chart $(field "$tcomment" chart), $(field "$tcomment" installed) modules)"
}

status() {
  echo "owner:        $OWNER (default clone $DEFAULT_CLONE)"
  echo "parity:       $PARITY"
  echo "fingerprint:  $FP"
  echo "template:     $TEMPLATE_DB ($(template_ready && echo ready || echo absent))"
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
    clone | drop | assert-clone) validate_clone_name "${2:-$DEFAULT_CLONE}" ;;
    run)
      validate_clone_name "${2:-}"
      parse_run "$2" "${@:3}"
      ;;
    template | status) ;;
    *)
      echo "usage: $0 template | clone [db] | run <db> -- <odoo args> | assert-clone <db> | drop <db> | status | name" >&2
      exit 2
      ;;
  esac

  ensure_db_service
  ensure_odoo_image
  compute_fingerprint
  case "$command" in
    template) build_template ;;
    clone) clone_template "${2:-$DEFAULT_CLONE}" ;;
    assert-clone) assert_clone "$2" ;;
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
      if [ "$RUN_MODE" = "make" ]; then
        # The import's own `docker compose` is bound to this repository's
        # verified file and project.
        COMPOSE_FILE="$COMPOSE_FILE_HERE" COMPOSE_PROJECT_NAME="$PROJECT" "${RUN_ARGS[@]}"
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
