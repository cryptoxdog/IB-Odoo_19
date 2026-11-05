#!/usr/bin/env bash
# Negative regression for the compatibility-proof exit status.
# A zero Odoo-shell status without CRM4_PROOF_OK, and an explicit zero exit
# while the proof is unset, must both leave a nonzero status. Neither path
# may clone a database or rewrite the selected constraint file.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
sql="tests/crm4_selected_constraint.sql"
before_sql="$(cksum "$sql")"
before_clones="$(docker exec odoo19-db-1 psql -U odoo -d postgres -tAc "SELECT datname FROM pg_database WHERE datname LIKE 'odoo_test_crm4%' ORDER BY 1")"

run_negative() {
  local mode=$1
  local rc=0
  set +e
  CRM4_COMPAT_NEGATIVE="$mode" bash tests/crm4_constraint_compat.sh >/tmp/crm4-negative-"$mode".log 2>&1
  rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then
    echo "negative mode ${mode} exited 0" >&2
    cat /tmp/crm4-negative-"$mode".log >&2 || true
    exit 1
  fi
}

run_negative missing-marker
run_negative trap-zero

after_sql="$(cksum "$sql")"
after_clones="$(docker exec odoo19-db-1 psql -U odoo -d postgres -tAc "SELECT datname FROM pg_database WHERE datname LIKE 'odoo_test_crm4%' ORDER BY 1")"
if [ "$before_sql" != "$after_sql" ]; then
  echo "selected constraint file changed during the negative proof" >&2
  exit 1
fi
if [ "$before_clones" != "$after_clones" ]; then
  echo "odoo_test_crm4 clone set changed during the negative proof" >&2
  exit 1
fi
echo CRM4_NEGATIVE_OK
