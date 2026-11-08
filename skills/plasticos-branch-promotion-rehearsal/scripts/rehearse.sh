#!/usr/bin/env bash
# Staging -> Production promotion rehearsal.
#
# Runs the two post-cutover import commands, unchanged, at 10 percent volume
# against a named non-production database:
#   1. make import-erp LIMIT=10%                     (newest 10% of ERP worksheets;
#                                                     partners, addresses, contacts,
#                                                     roles and salespersons stay complete)
#   2. make import-vanillasoft VANILLASOFT_HISTORY_MAX_IDS=<ceil(10% of census rows)>
#                                                    (history mode on the frozen census)
# Nothing else runs. No production permit is ever set.
#
# Evidence: at most five files in $REHEARSAL_EVIDENCE_DIR
#   erp-summary.json          the importer's own summary (when it was written)
#   vanillasoft-summary.json  the importer's own HISTORY VERDICT (when it was written)
#   misalignments.json        every failure and misalignment read from both runs
#   receipt.json              what ran, on what, with which caps, and the verdict
# Logs and the ERP census sibling are written to a scratch directory and deleted.
#
# Required environment:
#   ODOO_DB_NAME                         non-production rehearsal database
#   ERP_SQL_SERVER, ERP_SQL_DATABASE     restored ERP source (plus the reader login)
#   VANILLASOFT_HISTORY_CENSUS           frozen no-PII census, inside this checkout
#   VANILLASOFT_HISTORY_CENSUS_SHA256    its declared SHA-256
#   VANILLASOFT_HISTORY_CHECKPOINT       append-only ledger for this database
# Optional:
#   REHEARSAL_EVIDENCE_DIR               default .l9/runtime/promotion-rehearsal/<UTC stamp>
#
# Exit 0 only when both commands exit 0 and misalignments.json lists nothing.
# Exit 2 on a refusal (nothing was imported), 1 on a failed or misaligned run.
set -uo pipefail
umask 077

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(git -C "${SKILL_DIR}" rev-parse --show-toplevel 2>/dev/null)" || {
  echo "❌ rehearsal refused: the skill is not inside a git checkout" >&2
  exit 2
}
cd "${ROOT}" || exit 2

EVIDENCE_CAP=5
ERP_LIMIT_SHARE="10%"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_DIR="${REHEARSAL_EVIDENCE_DIR:-.l9/runtime/promotion-rehearsal/${STAMP}}"
SCRATCH_DIR="${EVIDENCE_DIR}.scratch"

refuse() {
  echo "❌ rehearsal refused: $1. Nothing was imported." >&2
  exit 2
}

# ── Refusals: before either make target runs ────────────────────────────────
[ "${ODOO_STAGE:-}" = "production" ] && refuse "ODOO_STAGE=production; the rehearsal never targets production"
[ -n "${ERP_PRODUCTION_PERMIT:-}" ] && refuse "ERP_PRODUCTION_PERMIT is set; the rehearsal never passes a permit"
[ -n "${VANILLASOFT_PRODUCTION_PERMIT:-}" ] && refuse "VANILLASOFT_PRODUCTION_PERMIT is set; the rehearsal never passes a permit"
[ -n "${ODOO_DB_NAME:-}" ] || refuse "ODOO_DB_NAME must name the rehearsal database (the Makefile default 'odoo' is not assumed)"
db_lower="$(printf '%s' "${ODOO_DB_NAME}" | tr '[:upper:]' '[:lower:]')"
case "${db_lower}" in
  *prod*) refuse "ODOO_DB_NAME=${ODOO_DB_NAME} denotes production" ;;
esac
[ "${ERP_REQUIRE_EMPTY:-1}" = "1" ] || refuse "ERP_REQUIRE_EMPTY must stay at the importer default of 1"
[ -z "${ERP_PAYLOAD_ROOT:-}${PAYLOAD_ROOT:-}" ] || refuse "a payload root selects the frozen grid; the rehearsal reads only the restored ERP database"
[ -z "${VANILLASOFT_CALL_FLOOR:-}${VANILLASOFT_CONTACT_FLOOR:-}" ] \
  || refuse "call and contact floors select the rolling window; the rehearsal runs the history census only"
[ -n "${VANILLASOFT_HISTORY_CENSUS:-}" ] || refuse "VANILLASOFT_HISTORY_CENSUS must name the frozen census"
[ -r "${VANILLASOFT_HISTORY_CENSUS}" ] || refuse "VANILLASOFT_HISTORY_CENSUS does not name a readable file"
command -v python3 >/dev/null 2>&1 || refuse "python3 is required to write the evidence"
# Both importers write their summary relative to the checkout, the only bind mount
# the odoo container can read, so the evidence directory is a relative path inside it.
case "${EVIDENCE_DIR}" in
  /* | *..*) refuse "REHEARSAL_EVIDENCE_DIR must be a relative path inside this checkout" ;;
esac

# 10 percent of the census data rows (header excluded, blank lines ignored), rounded up.
census_rows="$(tail -n +2 "${VANILLASOFT_HISTORY_CENSUS}" | grep -c '[^[:space:]]')"
[ "${census_rows}" -gt 0 ] 2>/dev/null || refuse "the census has no data rows"
vs_max_ids=$(( (census_rows + 9) / 10 ))

mkdir -p "${EVIDENCE_DIR}" "${SCRATCH_DIR}" || refuse "cannot create ${EVIDENCE_DIR}"
if [ -n "$(ls -A "${EVIDENCE_DIR}")" ]; then
  refuse "${EVIDENCE_DIR} is not empty; each rehearsal writes a fresh evidence directory"
fi

ERP_SUMMARY="${SCRATCH_DIR}/erp-summary.json"
VS_SUMMARY="${SCRATCH_DIR}/vanillasoft-summary.json"
ERP_LOG="${SCRATCH_DIR}/erp.log"
VS_LOG="${SCRATCH_DIR}/vanillasoft.log"

echo "→ promotion rehearsal on ${ODOO_DB_NAME} → ${EVIDENCE_DIR}"

# ── 1. make import-erp LIMIT=10% ────────────────────────────────────────────
echo "→ [1/2] make import-erp LIMIT=${ERP_LIMIT_SHARE}"
make import-erp \
  ODOO_DB_NAME="${ODOO_DB_NAME}" \
  LIMIT="${ERP_LIMIT_SHARE}" \
  ERP_REPORT_PATH="${ERP_SUMMARY}" 2>&1 | tee "${ERP_LOG}"
erp_exit=${PIPESTATUS[0]}

# ── 2. make import-vanillasoft, history census capped at 10 percent ─────────
# Runs whatever the ERP step returned, so one rehearsal shows every failure.
echo "→ [2/2] make import-vanillasoft VANILLASOFT_HISTORY_MAX_IDS=${vs_max_ids} (${census_rows} census rows)"
make import-vanillasoft \
  ODOO_DB_NAME="${ODOO_DB_NAME}" \
  VANILLASOFT_HISTORY_MAX_IDS="${vs_max_ids}" \
  VANILLASOFT_REPORT_PATH="${VS_SUMMARY}" 2>&1 | tee "${VS_LOG}"
vs_exit=${PIPESTATUS[0]}

# ── Evidence: two summaries, misalignments.json, receipt.json ───────────────
[ -s "${ERP_SUMMARY}" ] && cp "${ERP_SUMMARY}" "${EVIDENCE_DIR}/erp-summary.json"
[ -s "${VS_SUMMARY}" ] && cp "${VS_SUMMARY}" "${EVIDENCE_DIR}/vanillasoft-summary.json"

GIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"

# The reader password and VanillaSoft secrets reach only the redactor, through the environment.
python3 - "${EVIDENCE_DIR}" "${SCRATCH_DIR}" "${erp_exit}" "${vs_exit}" \
  "${ODOO_DB_NAME}" "${ERP_LIMIT_SHARE}" "${vs_max_ids}" "${census_rows}" \
  "${GIT_SHA}" "${GIT_BRANCH}" "${STAMP}" <<'PY'
import json
import os
import re
import sys
from pathlib import Path

(evidence, scratch, erp_exit, vs_exit, database, erp_limit, vs_max_ids, census_rows, sha, branch, stamp) = sys.argv[1:]
evidence, scratch = Path(evidence), Path(scratch)
erp_exit, vs_exit = int(erp_exit), int(vs_exit)
secrets = [v for v in (os.environ.get("ERP_SQL_PASSWORD"),) if v]
pattern = re.compile(r"(?i)(api[_-]?key|authorization|password|token)\s*[:=]\s*(?:bearer\s+)?\S+")


def redact(text: str) -> str:
    for value in secrets:
        text = text.replace(value, "[REDACTED]")
    return pattern.sub(r"\1=[REDACTED]", text)


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def tail(path: Path, lines: int = 40) -> list[str]:
    try:
        rows = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [redact(row) for row in rows[-lines:]]


items: list[dict] = []

# ERP: exit code, summary contract identity, duplicates, errors, census sibling.
erp = load(scratch / "erp-summary.json")
if erp_exit:
    items.append({"source": "import-erp", "kind": "exit_code", "detail": erp_exit, "log_tail": tail(scratch / "erp.log")})
if erp is None:
    items.append({"source": "import-erp", "kind": "summary_missing", "detail": "the importer wrote no summary"})
else:
    seen = int(erp.get("records_seen") or 0)
    accounted = sum(
        int(erp.get(key) or 0)
        for key in ("records_created", "records_updated", "records_unchanged", "records_rejected")
    )
    if seen != accounted:
        items.append(
            {"source": "import-erp", "kind": "reconciliation", "detail": f"records_seen {seen} != accounted {accounted}"}
        )
    if int(erp.get("duplicates") or 0):
        items.append({"source": "import-erp", "kind": "duplicates", "detail": erp.get("duplicates")})
    if erp.get("final_status") != "success":
        items.append({"source": "import-erp", "kind": "final_status", "detail": erp.get("final_status")})
    for row in erp.get("errors") or []:
        items.append({"source": "import-erp", "kind": "error_row", "detail": row})
sibling = load(scratch / "erp-summary-census.json")
if sibling:
    anomalies = sibling.get("anomalies") or []
    unresolved = sibling.get("unresolved") or []
    if anomalies or unresolved or sibling.get("census"):
        items.append(
            {
                "source": "import-erp",
                "kind": "source_exception_census",
                "detail": {
                    "anomalies": len(anomalies),
                    "unresolved": len(unresolved),
                    "census": sibling.get("census") or {},
                },
            }
        )

# VanillaSoft: exit code and the HISTORY VERDICT. Ids not reached under the cap are expected.
vs = load(scratch / "vanillasoft-summary.json")
if vs_exit:
    items.append(
        {"source": "import-vanillasoft", "kind": "exit_code", "detail": vs_exit, "log_tail": tail(scratch / "vanillasoft.log")}
    )
if vs is None:
    items.append({"source": "import-vanillasoft", "kind": "summary_missing", "detail": "the importer wrote no verdict"})
else:
    if vs.get("stopped") not in (None, "max_ids"):
        items.append({"source": "import-vanillasoft", "kind": "stopped", "detail": vs.get("stopped")})
    for key in ("dispositions_without_a_source_reason", "imported_with_error_signals"):
        if int(vs.get(key) or 0):
            items.append({"source": "import-vanillasoft", "kind": key, "detail": vs.get(key)})
    failed = int((vs.get("classes") or {}).get("genuine_failed") or 0)
    if failed:
        items.append({"source": "import-vanillasoft", "kind": "genuine_failed", "detail": failed})

clean = not items and erp_exit == 0 and vs_exit == 0
(evidence / "misalignments.json").write_text(
    json.dumps({"count": len(items), "items": items}, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
)
files = sorted(p.name for p in evidence.iterdir()) + ["receipt.json"]
receipt = {
    "rehearsal": "staging-to-production promotion",
    "started_utc": stamp,
    "git": {"branch": branch, "sha": sha},
    "database": database,
    "commands": [
        {"make": "import-erp", "LIMIT": erp_limit, "exit": erp_exit},
        {
            "make": "import-vanillasoft",
            "mode": "history",
            "VANILLASOFT_HISTORY_MAX_IDS": int(vs_max_ids),
            "census_rows": int(census_rows),
            "exit": vs_exit,
        },
    ],
    "production_permit": None,
    "evidence_files": files,
    "misalignments": len(items),
    "verdict": "PASS" if clean else "FAIL",
}
(evidence / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"REHEARSAL {receipt['verdict']}: {len(items)} misalignment(s); evidence {evidence}")
sys.exit(0 if clean else 1)
PY
verdict_exit=$?

# Logs and the census sibling never enter the evidence directory.
rm -rf -- "${SCRATCH_DIR:?}"

evidence_count="$(find "${EVIDENCE_DIR}" -mindepth 1 -maxdepth 1 | wc -l | tr -d '[:space:]')"
if [ "${evidence_count}" -gt "${EVIDENCE_CAP}" ]; then
  echo "❌ rehearsal evidence holds ${evidence_count} files, over the cap of ${EVIDENCE_CAP}" >&2
  exit 1
fi
exit "${verdict_exit}"
