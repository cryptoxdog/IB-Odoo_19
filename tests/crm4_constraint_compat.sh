#!/usr/bin/env bash
# CRM4-PR-001: prove PostgreSQL 15+ and Odoo constraint replacement on an owned
# enterprise clone, then record the selected uniqueness SQL. The clone is dropped
# on success and on failure. plasticos_material_profile is not altered.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
unset TEST_ENV_PARITY

owner_db="$(bash scripts/test_env.sh name)"
suffix="${owner_db#odoo_test_}"
db="odoo_test_crm4_${suffix}"
sql_out="tests/crm4_selected_constraint.sql"
log="$(mktemp)"
cloned=0
proof_ok=0

case "$db" in
  *prod* | *staging*)
    echo "refusing ${db}: production and staging names are never disposable" >&2
    exit 2
    ;;
  odoo_test_crm4_[a-z0-9_]*) ;;
  *)
    echo "refusing ${db}: clone name is not odoo_test_crm4_<owner>" >&2
    exit 2
    ;;
esac
if [ "$db" = "odoo" ] || [ "$db" = "${ODOO_DB_NAME:-odoo}" ]; then
  echo "refusing business database ${db}" >&2
  exit 2
fi

cleanup() {
  local status=$?
  if [ "$cloned" -eq 1 ]; then
    if ! bash scripts/test_env.sh drop "$db"; then
      echo "owned clone retirement failed: ${db}" >&2
      status=1
    fi
  fi
  rm -f "$log"
  if [ "$proof_ok" -ne 1 ]; then
    rm -f "$sql_out"
    if [ "$status" -eq 0 ]; then
      status=1
    fi
    exit "$status"
  fi
  if [ "$status" -ne 0 ]; then
    rm -f "$sql_out"
    exit "$status"
  fi
  printf '%s\n' 'UNIQUE NULLS NOT DISTINCT (partner_id, polymer_id, form_id)' >"$sql_out"
  exit 0
}
trap cleanup EXIT

if [ "${CRM4_COMPAT_NEGATIVE:-}" = "missing-marker" ]; then
  sql_out="$(mktemp)"
  rc=0
  proof_ok=0
elif [ "${CRM4_COMPAT_NEGATIVE:-}" = "trap-zero" ]; then
  sql_out="$(mktemp)"
  proof_ok=0
  exit 0
else
  bash scripts/test_env.sh clone "$db"
  cloned=1

  set +e
  bash scripts/test_env.sh run "$db" -- shell >"$log" 2>&1 <<'PY'
import inspect
import sys

from odoo.orm.fields import Field
from odoo.orm.table_objects import Constraint
from odoo.tools import sql

env.cr.execute("SHOW server_version_num")
if int(env.cr.fetchone()[0]) < 150000:
    sys.exit(1)

env.cr.execute(
    """
    SELECT pg_get_constraintdef(c.oid), a.attnotnull
      FROM pg_constraint c
      JOIN pg_class t ON t.oid = c.conrelid
      JOIN pg_attribute a ON a.attrelid = t.oid AND a.attname = 'form_id'
     WHERE t.relname = 'plasticos_material_profile'
       AND c.conname = 'plasticos_material_profile_unique_partner_polymer_form'
       AND NOT a.attisdropped
    """
)
before = env.cr.fetchone()
# A fresh install of this branch already applies the selected constraint.
# The probe below still has to show Odoo can perform that replacement.
if (
    not before
    or before[1] is not False
    or (before[0] or "") != "UNIQUE NULLS NOT DISTINCT (partner_id, polymer_id, form_id)"
):
    print("CRM4_PROOF_PRECONDITION", repr(before), file=sys.stderr)
    sys.exit(1)

apply_src = inspect.getsource(Constraint.apply_to_database)
notnull_src = inspect.getsource(Field.update_db_notnull)
if "sql.drop_constraint" not in apply_src or "sql.add_constraint" not in apply_src:
    sys.exit(1)
if "if current_definition:" not in apply_src:
    sys.exit(1)
if "sql.drop_not_null" not in notnull_src or "not self.required and has_notnull" not in notnull_src:
    sys.exit(1)

env.cr.execute("CREATE TABLE crm4_compat_probe (id integer PRIMARY KEY, form_id integer NOT NULL)")
sql.drop_not_null(env.cr, "crm4_compat_probe", "form_id")
env.cr.execute(
    """
    SELECT a.attnotnull
      FROM pg_attribute a
      JOIN pg_class c ON c.oid = a.attrelid
     WHERE c.relname = 'crm4_compat_probe' AND a.attname = 'form_id' AND NOT a.attisdropped
    """
)
if env.cr.fetchone()[0] is not False:
    sys.exit(1)

sql.add_constraint(env.cr, "crm4_compat_probe", "crm4_compat_probe_uniq", "UNIQUE (form_id)")
first = sql.constraint_definition(env.cr, "crm4_compat_probe", "crm4_compat_probe_uniq")
sql.drop_constraint(env.cr, "crm4_compat_probe", "crm4_compat_probe_uniq")
sql.add_constraint(
    env.cr,
    "crm4_compat_probe",
    "crm4_compat_probe_uniq",
    "UNIQUE NULLS NOT DISTINCT (form_id)",
)
second = sql.constraint_definition(env.cr, "crm4_compat_probe", "crm4_compat_probe_uniq")
if first == second or second != "UNIQUE NULLS NOT DISTINCT (form_id)":
    sys.exit(1)
env.cr.execute("DROP TABLE crm4_compat_probe")

env.cr.execute(
    """
    SELECT pg_get_constraintdef(c.oid), a.attnotnull
      FROM pg_constraint c
      JOIN pg_class t ON t.oid = c.conrelid
      JOIN pg_attribute a ON a.attrelid = t.oid AND a.attname = 'form_id'
     WHERE t.relname = 'plasticos_material_profile'
       AND c.conname = 'plasticos_material_profile_unique_partner_polymer_form'
       AND NOT a.attisdropped
    """
)
after = env.cr.fetchone()
if after != before:
    sys.exit(1)

print("CRM4_PROOF_OK")
sys.exit(0)
PY
  rc=$?
  set -e
  if [ "$rc" -eq 0 ] && grep -q '^CRM4_PROOF_OK$' "$log"; then
    proof_ok=1
  fi
fi
if [ "$proof_ok" -ne 1 ]; then
  echo "CRM4 constraint compatibility proof failed (status ${rc})" >&2
  if [ -f "$log" ]; then
    tail -n 80 "$log" >&2 || true
  fi
  if [ "${rc}" -eq 0 ]; then
    exit 1
  fi
  exit "${rc}"
fi
