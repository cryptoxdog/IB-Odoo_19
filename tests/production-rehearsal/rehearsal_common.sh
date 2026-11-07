# shellcheck shell=bash
# Shared helpers for the promotion-rehearsal kit. Sourced, never executed.
# Bash 3.2 compatible (macOS /bin/bash): no associative arrays, no mapfile,
# no empty-array expansion under `set -u`.
#
# Callers set KIT_DIR and ROOT before sourcing.

REHEARSAL_PY="${REHEARSAL_PY:-python3}"

# rlib <command> [args...] — the kit's Python helper (gate receipts, proof checks).
rlib() {
  "${REHEARSAL_PY}" "${KIT_DIR}/common.py" "$@"
}

# db_query <db> <out_file> — run the SQL on stdin against <db> in the compose `db`
# service, unaligned and tuples-only, stopping on the first error. The SQL never
# goes on argv. Returns psql's exit status; <out_file> holds stdout only.
db_query() {
  local db="$1" out="$2"
  docker compose -f "${ROOT}/docker-compose.yml" exec -T db \
    psql -U odoo -X -q -At -v ON_ERROR_STOP=1 -d "${db}" >"${out}" 2>>"${out}.err"
}

# business_partner_census <db> <out_file> — every customer or supplier partner,
# inactive ones included. Prints the strict count on success; returns nonzero
# when the query fails or its output is not exactly one integer.
business_partner_census() {
  local db="$1" out="$2"
  if ! printf '%s\n' "SELECT COUNT(*) FROM res_partner WHERE customer_rank > 0 OR supplier_rank > 0;" \
    | db_query "${db}" "${out}"; then
    return 2
  fi
  rlib count "${out}"
}

# vanillasoft_ref_census <db> <out_file> — VanillaSoft ContactIDs with a durable
# external ref at either destination the history driver accepts
# (import_vanillasoft_shell._durable_ids): an ERP person (res.partner) for a
# crosswalk YES, otherwise a crm.lead. Gate 7 reads it before and after the
# import; the difference is what this run landed. Strict count, never zero on
# a failed query.
vanillasoft_ref_census() {
  local db="$1" out="$2"
  if ! printf '%s\n' "SELECT COUNT(DISTINCT external_id) FROM plasticos_crm_external_ref WHERE provider = 'vanillasoft' AND res_model IN ('crm.lead', 'res.partner');" \
    | db_query "${db}" "${out}"; then
    return 2
  fi
  rlib count "${out}"
}
