#!/usr/bin/env bash
# Build a real Odoo 19 + PostgreSQL 16 runtime WITHOUT Docker.
#
# This is docs/runbooks/C1_C6_LOCAL_RUNTIME.md made executable. That runbook is
# correct and precise, and it was prose only — so every person and every agent
# retyped it by hand, which is why the launch gates in tests/runtime_gates/ were
# run rarely and by few.
#
# Why not Docker: the gates need a live registry, real cursors, real commits and
# real session advisory-lock lifetime. Docker is the usual way to get that, and
# it is not the only way. In a sandbox with no daemon, no registry egress, or no
# bridge networking, this path still works — the whole argument of the runbook.
#
# Idempotent: every step is skipped when its artifact already exists, so a warm
# machine reaches "ready" in seconds. That is what makes it usable as a session
# setup step rather than a once-a-quarter chore.
#
#   bash scripts/setup_local_runtime.sh              # build + verify
#   bash scripts/setup_local_runtime.sh --check      # verify only, no mutation
#   bash scripts/setup_local_runtime.sh --recreate-db  # rebuild the template DB
#
# Environment overrides (defaults suit a fresh Linux container):
#   L9_PG_PORT=5433 L9_PG_HOST=/tmp L9_PG_USER=odoo
#   L9_PG_DATA=/var/lib/postgresql/c1c6
#   L9_ODOO_SRC_DIR=/opt/odoo-src  L9_ODOO_VENV=/opt/odoo-venv
#   L9_ODOO_TEMPLATE_DB=plasticos_template
#   L9_ODOO_MODULES=plasticos_crm_sync,plasticos_transaction
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PG_PORT="${L9_PG_PORT:-5433}"
PG_HOST="${L9_PG_HOST:-/tmp}"
PG_USER="${L9_PG_USER:-odoo}"
PG_DATA="${L9_PG_DATA:-/var/lib/postgresql/c1c6}"
PG_BIN="${L9_PG_BIN:-/usr/lib/postgresql/16/bin}"
ODOO_SRC_DIR="${L9_ODOO_SRC_DIR:-/opt/odoo-src}"
ODOO_VENV="${L9_ODOO_VENV:-/opt/odoo-venv}"
TEMPLATE_DB="${L9_ODOO_TEMPLATE_DB:-plasticos_template}"
MODULES="${L9_ODOO_MODULES:-plasticos_crm_sync,plasticos_transaction}"
ODOO_TARBALL_URL="${L9_ODOO_TARBALL_URL:-https://nightly.odoo.com/19.0/nightly/src/odoo_19.0.latest.tar.gz}"

CHECK_ONLY=0
RECREATE_DB=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    --recreate-db) RECREATE_DB=1 ;;
    -h|--help) sed -n '2,30p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '  %s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
die()  { printf '\nFAIL: %s\n' "$*" >&2; exit 1; }

odoo_src() { ls -d "$ODOO_SRC_DIR"/odoo-19.0* 2>/dev/null | sort | tail -1; }

# ---------------------------------------------------------------- preflight --
step "Preflight"
[ "$(uname -s)" = "Linux" ] || die "This builder targets Linux (the runbook's
  \`initdb\`/\`pg_ctl\` invocations and /usr/lib/postgresql layout). On macOS use
  the Docker path (make up / make test-odoo) or adapt L9_PG_BIN to Homebrew."
command -v python3.12 >/dev/null || die "python3.12 not found (Odoo 19 targets 3.12)"
[ -x "$PG_BIN/initdb" ] || die "PostgreSQL 16 not found at $PG_BIN — install postgresql-16 or set L9_PG_BIN"
say "linux, python3.12, postgresql-16 present"

# --------------------------------------------------------------- postgresql --
step "PostgreSQL cluster on port $PG_PORT"
if pg_isready -h "$PG_HOST" -p "$PG_PORT" >/dev/null 2>&1; then
  say "already accepting connections"
elif [ "$CHECK_ONLY" = "1" ]; then
  die "cluster is not running (re-run without --check)"
else
  if [ ! -d "$PG_DATA/base" ]; then
    say "initdb $PG_DATA"
    mkdir -p "$PG_DATA"
    chown -R postgres:postgres "$PG_DATA"
    su postgres -c "$PG_BIN/initdb -D $PG_DATA -A trust -U $PG_USER" >/dev/null
  fi
  say "starting"
  su postgres -c "$PG_BIN/pg_ctl -D $PG_DATA -o '-p $PG_PORT -k $PG_HOST' -l $PG_DATA/pg.log start" >/dev/null 2>&1 || true
  for _ in $(seq 1 30); do pg_isready -h "$PG_HOST" -p "$PG_PORT" >/dev/null 2>&1 && break; sleep 1; done
  pg_isready -h "$PG_HOST" -p "$PG_PORT" >/dev/null 2>&1 || die "cluster did not start; see $PG_DATA/pg.log"
  say "up"
fi

# -------------------------------------------------------------- odoo source --
step "Odoo 19 source"
if [ -n "$(odoo_src)" ]; then
  say "present: $(odoo_src)"
elif [ "$CHECK_ONLY" = "1" ]; then
  die "Odoo source missing under $ODOO_SRC_DIR"
else
  mkdir -p "$ODOO_SRC_DIR"
  # nightly.odoo.com is Odoo's official source channel and stays reachable where
  # an egress policy blocks github.com/odoo/odoo.
  [ -f "$ODOO_SRC_DIR/odoo_19.0.latest.tar.gz" ] || \
    curl -sSf -o "$ODOO_SRC_DIR/odoo_19.0.latest.tar.gz" "$ODOO_TARBALL_URL"
  tar xzf "$ODOO_SRC_DIR/odoo_19.0.latest.tar.gz" -C "$ODOO_SRC_DIR"
  [ -n "$(odoo_src)" ] || die "tarball did not expand to odoo-19.0*"
  say "fetched $(odoo_src)"
fi
SRC="$(odoo_src)"

# --------------------------------------------------------------- python venv --
step "Runtime venv"
if [ -x "$ODOO_VENV/bin/odoo" ]; then
  say "present: $ODOO_VENV"
elif [ "$CHECK_ONLY" = "1" ]; then
  die "venv missing at $ODOO_VENV"
else
  [ -x "$ODOO_VENV/bin/python" ] || python3.12 -m venv "$ODOO_VENV"
  "$ODOO_VENV/bin/pip" install -q -U pip wheel setuptools
  # psycopg2 and python-ldap need C headers that may be absent. psycopg2-binary
  # is a drop-in; python-ldap is only used by auth_ldap, which these gates never
  # load. Dropping them is what makes this work on a bare container.
  grep -vE '^(psycopg2|python-ldap)' "$SRC/requirements.txt" > /tmp/l9-odoo-req.txt
  "$ODOO_VENV/bin/pip" install -q -r /tmp/l9-odoo-req.txt psycopg2-binary
  "$ODOO_VENV/bin/pip" install -q --no-deps -e "$SRC"
  say "built"
fi
"$ODOO_VENV/bin/python" -c "import odoo.release as r; print('  odoo', r.version)"

# -------------------------------------------------------------- template db --
step "Template database '$TEMPLATE_DB' ($MODULES)"
db_exists() { psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -lqt 2>/dev/null | cut -d'|' -f1 | grep -qw "$1"; }
if [ "$RECREATE_DB" = "1" ] && [ "$CHECK_ONLY" != "1" ]; then
  dropdb -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" --if-exists "$TEMPLATE_DB"
fi
if db_exists "$TEMPLATE_DB"; then
  say "present (use --recreate-db to rebuild)"
elif [ "$CHECK_ONLY" = "1" ]; then
  die "template database $TEMPLATE_DB missing"
else
  createdb -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" "$TEMPLATE_DB"
  say "installing modules (several minutes on a cold build)"
  "$ODOO_VENV/bin/odoo" -d "$TEMPLATE_DB" \
    --db_host="$PG_HOST" --db_port="$PG_PORT" --db_user="$PG_USER" \
    --addons-path="$SRC/odoo/addons,$REPO" \
    -i "$MODULES" --stop-after-init --log-level=warn
  say "installed"
fi

# ------------------------------------------------------------------ summary --
step "Ready"
cat <<SUMMARY
  export L9_PG_HOST=$PG_HOST L9_PG_PORT=$PG_PORT L9_PG_USER=$PG_USER
  export SEAM_ODOO_SRC=$SRC

  Run the launch gates:   make runtime-gates
  Fresh DB from template: createdb -h $PG_HOST -p $PG_PORT -U $PG_USER -T $TEMPLATE_DB <name>
SUMMARY
