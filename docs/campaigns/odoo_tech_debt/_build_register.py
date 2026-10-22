#!/usr/bin/env python3
"""One-shot census of open tech debt on origin/Staging. Not a runtime module."""

from __future__ import annotations

import ast
import collections
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
# Replaced in main() by an exact export of origin/Staging; the scanners read only that tree.
ROOT = REPO

OUT = Path(__file__).resolve().parent


def git(*args: str) -> str:
    # Fixed argv. The only variable pieces are paths from this repo's git index.
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True)  # noqa: S603, S607


def export_origin_staging(dest: Path) -> Path:
    archive = subprocess.check_output(["git", "-C", str(REPO), "archive", "--format=tar", "origin/Staging"])  # noqa: S603, S607
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(dest, filter="data")
    return dest


def sha() -> str:
    return git("rev-parse", "origin/Staging").strip()


def tracked() -> set[str]:
    return set(git("ls-tree", "-r", "--name-only", "origin/Staging").splitlines())


def function_at(source: str, line: int) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""
    best = None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end = getattr(node, "end_lineno", node.lineno)
        if node.lineno <= line <= end and (best is None or node.lineno >= best.lineno):
            best = node
    return best.name if best else ""


def source_of(rel: str) -> str:
    path = ROOT / rel
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return git("show", f"origin/Staging:{rel}")


def line_in_symbol(rel: str, symbol: str, code: str) -> int:
    source = source_of(rel)
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
            lines = source.splitlines()
            for number in range(node.lineno, node.end_lineno + 1):
                if lines[number - 1].strip() == code:
                    return number
    raise LookupError(f"{code!r} not found in {rel}:{symbol}")


def line_text(rel: str, line: int) -> str:
    lines = source_of(rel).splitlines()
    if 1 <= line <= len(lines):
        return lines[line - 1].strip()
    return ""


def enclosing_relation(rel: str, line: int) -> str | None:
    lines = source_of(rel).splitlines()
    depth = 0
    open_sub = re.compile(r"<(list|form|kanban)\b")
    close_sub = re.compile(r"</(list|form|kanban)>")
    for index in range(line - 2, -1, -1):
        text = lines[index]
        if close_sub.search(text):
            depth += 1
            continue
        if open_sub.search(text):
            if depth:
                depth -= 1
                continue
            for back in range(index, -1, -1):
                if "<record" in lines[back]:
                    return None
                match = re.search(r'<field\s+name="([^"]+)"', lines[back])
                if match:
                    return match.group(1)
            return None
    return None


def item(**kwargs) -> dict:
    base = {
        "status": "open",
        "remediate": False,
        "do_not": "",
        "proof": "",
        "symbol": "",
        "code": "",
        "message": "",
        "fingerprint": "",
        "parent_id": "",
        "recommended_batch": "",
    }
    base.update(kwargs)
    return base


def field_scanner_cause(code: str, enclosing: str | None) -> str:
    """Why odoo_audit attributed this column to the wrong model."""
    if enclosing:
        return "nested_subview"
    if " ref=" in code or re.search(r'<field name="[^"]+">[^<]+</field>', code):
        return "record_context_bleed"
    return "cross_module_inherit"


FIELD_CAUSE_TEXT = {
    "nested_subview": (
        "The column sits inside a relational list or form. The scanner still has the parent view model.",
        "No view edit. Use this row as a fixture for TD-SCAN-001.",
    ),
    "record_context_bleed": (
        "This element is data on a later ir.actions or ir.cron record. The scanner kept the previous view model because it never resets the model when a record ends.",
        "No view edit. Use this row as a fixture for TD-SCAN-001.",
    ),
    "cross_module_inherit": (
        "The field is added by another module's _inherit. The single-file scanner does not see that class.",
        "No view edit. Use this row as a fixture for TD-SCAN-001.",
    ),
}


def call_window(rel: str, line: int, span: int = 8) -> str:
    rows = source_of(rel).splitlines()
    return "\n".join(rows[line - 1 : line - 1 + span])


def unbounded_disposition(rel: str, line: int, code: str, bound: str) -> tuple[str, str, str, bool]:
    """Return classification, why, action, remediate."""
    window = call_window(rel, line)
    if rel.endswith("plasticos_crm_bridge/models/facility_profile.py"):
        return (
            "false_positive",
            "Dynamic inverse lookup. Every installed row pointing at the profile must be seen before retarget or deletion. The field name is data, so the scanner reports unknown.",
            "Leave the search complete. A limit would drop referencing rows.",
            False,
        )
    if rel.endswith("plasticos_geolocalize/models/res_partner_geo.py"):
        return (
            "false_positive",
            "limit=batch_size and _geo_backfill_param floors the value at 1. The proof crosses a function call, so the scanner reports unknown.",
            "Leave the call. Do not add a second literal limit.",
            False,
        )
    if rel.endswith("plasticos_intake_normalizer/models/intake_normalizer.py") and "pending" in code:
        return (
            "false_positive",
            "PR #240 refuses a negative batch_limit before this search. 0 still means 200 via `or 200`. The scanner cannot see that constraint.",
            "Leave the call. The positivity proof is plasticos_intake_normalizer/models/normalizer_config.py _check_batch_limit.",
            False,
        )
    if bound == "unknown" and re.search(r"""['"]in['"]""", window):
        return (
            "false_positive",
            "The domain is an input set built from the current recordset (names or document origins). The scanner reports unknown because the field is not an identity column.",
            "Leave the search. Do not add limit=1.",
            False,
        )
    if rel.endswith("plasticos_partner_import/models/validation.py") and (
        "facility_role" in window or ("is_company" in window and "parent_id" in window)
    ):
        return (
            "false_positive",
            "PR #240 narrowed this read to the rows the check can fail. The scanner still says unbounded because the domain is categorical.",
            "Leave the domain. Do not add limit=1.",
            False,
        )
    return (
        "accepted_bounded_debt",
        "The search is the complete set its caller returns or enforces. Truncation changes the result. GMP-NC-D classified this shape as business-complete.",
        "Leave the search complete. Re-open only if a caller is shown to filter most of the rows in Python.",
        False,
    )


def main() -> None:
    global ROOT
    with tempfile.TemporaryDirectory(prefix="odoo_tech_debt_") as tmp:
        ROOT = export_origin_staging(Path(tmp))
        sys.path[:0] = [str(ROOT / "scripts" / "audit"), str(ROOT / "ci")]
        os.chdir(ROOT)
        try:
            build()
        finally:
            os.chdir(REPO)


def build() -> None:
    from baseline_utils import compute_fingerprint, diff_findings, load_baseline
    from business_logic_audit import BusinessLogicAudit
    from odoo_audit import OdooAudit
    from performance_audit import PerformanceAudit
    from security_audit import SecurityAudit
    from test_audit import TestAudit

    head = sha()
    on_branch = tracked()
    perf = PerformanceAudit(ROOT)
    bl = BusinessLogicAudit(ROOT)
    sec = SecurityAudit(ROOT)
    tests = TestAudit(ROOT)
    nplus = perf.check_n_plus_one_queries()
    unbounded = perf.check_unbounded_searches()
    sudo = bl.check_missing_access_checks()
    state = bl.check_state_machine_bypasses()
    weak = [row for row in tests.check_weak_tests() if row["file"] in on_branch]
    sensitive = sec.check_sensitive_logging()
    high = list(nplus)
    base = load_baseline(ROOT / "ci/baselines/extended_audit_baseline.json")
    known, new_high, stale = diff_findings(high, base)

    oa = OdooAudit(".")
    schema = oa.run_all_checks()
    schema_base = load_baseline(ROOT / "ci/baselines/odoo_audit_baseline.json")
    gated = [row for row in schema if row.get("severity") in ("CRITICAL", "HIGH")]
    schema_known, schema_new, schema_stale = diff_findings(gated, schema_base)

    items: list[dict] = []

    def add(row: dict) -> None:
        items.append(row)

    # --- N+1 ---
    nplus_sorted = sorted(nplus, key=lambda row: (row["file"], row["line"]))
    for index, row in enumerate(nplus_sorted, 1):
        rel = row["file"]
        code = row.get("code") or line_text(rel, row["line"])
        fingerprint = compute_fingerprint({**row, "code": code})
        pagination = rel.endswith("plasticos_documents_native/models/document_sync.py")
        mutation = "mutation in loop" in row["message"]
        if pagination:
            classification = "false_positive"
            why = "Id-keyset pagination. The loop issues one search per 200-document page. Logged in the extended baseline as a reviewed false positive."
            action = "Leave the loop. Removing it would load the whole unlinked set at once."
            remediate = False
        elif mutation:
            classification = "accepted_bounded_debt"
            why = "Operator accepted this structural loop finding on 2026-10-10. It is a per-iteration ORM mutation, not one of the eight relationship paths repaired in PR #234."
            action = "Batch the create, write, or unlink for the whole recordset after proving each iteration does not depend on the previous write."
            remediate = True
        else:
            classification = "accepted_bounded_debt"
            why = "Operator accepted this structural loop finding on 2026-10-10. It is a per-iteration ORM read, not one of the eight relationship paths repaired in PR #234."
            action = "Lift the search out of the loop only when every iteration's domain can be expressed as one domain over the recordset. Keep selection order identical."
            remediate = True
        add(
            item(
                id=f"TD-N1-{index:03d}",
                classification=classification,
                severity="HIGH",
                family="N_PLUS_ONE_QUERY",
                source_campaign="odoo_critical_debt_playbook_pack",
                source_id="GAR-PROD-009",
                file=rel,
                line=row["line"],
                symbol=function_at(source_of(rel), row["line"]),
                code=code,
                message=row["message"],
                why_open=why,
                action=action,
                do_not="Do not special-case this file inside scripts/audit/performance_audit.py. Do not add a new baseline row for a rewritten line; remove this fingerprint in the same change.",
                remediate=remediate,
                proof="python3 scripts/audit/performance_audit.py is not required; re-run check_n_plus_one_queries and scripts/audit/check_baseline.py against ci/baselines/extended_audit_baseline.json. The old fingerprint must be absent and no new HIGH fingerprint may appear.",
                fingerprint=fingerprint,
                recommended_batch=rel,
                loop_start=row.get("loop_start"),
            )
        )

    for fingerprint in stale:
        entry = base[fingerprint]
        add(
            item(
                id=f"TD-BASE-{fingerprint}",
                classification="baseline_housekeeping",
                severity="HIGH",
                family="STALE_BASELINE",
                source_campaign="odoo_critical_debt_playbook_pack",
                source_id="D-09",
                file=entry["file"],
                line=entry.get("line") or 0,
                code=entry.get("message") or "",
                message="Baseline fingerprint has no live finding.",
                why_open="The flagged line is gone. check_baseline.py reports stale rows and does not fail CI.",
                action="Delete this entry from ci/baselines/extended_audit_baseline.json when a baseline-only change is already in progress.",
                do_not="Do not treat a stale row as a live defect. Do not fail a feature PR solely to prune it.",
                remediate=False,
                fingerprint=fingerprint,
                recommended_batch="ci/baselines/extended_audit_baseline.json",
            )
        )

    if new_high:
        for index, row in enumerate(new_high, 1):
            add(
                item(
                    id=f"TD-N1-NEW-{index:03d}",
                    classification="real_debt",
                    severity="HIGH",
                    family="N_PLUS_ONE_QUERY",
                    source_campaign="live_census",
                    source_id="unbaselined",
                    file=row["file"],
                    line=row["line"],
                    code=row.get("code") or "",
                    message=row["message"],
                    why_open="Live HIGH finding with no baseline fingerprint.",
                    action="Fix the call or, after review, log it through check_baseline.py --dump-new.",
                    remediate=True,
                    fingerprint=compute_fingerprint(row),
                )
            )

    # --- weak tests ---
    for index, row in enumerate(sorted(weak, key=lambda item: (item["file"], item["line"])), 1):
        add(
            item(
                id=f"TD-WEAK-{index:03d}",
                classification="real_debt",
                severity="MODERATE",
                family="WEAK_TEST",
                source_campaign="odoo_noncritical_gmp_campaign_pack",
                source_id="GMP-NC-A",
                file=row["file"],
                line=row["line"],
                symbol=row.get("test") or "",
                code=line_text(row["file"], row["line"]),
                message=row["message"],
                why_open="GMP-NC-A made ci/weak_test_fixer.py the only assertion owner and left these tests assertion-free. The CI step prints them and exits 0.",
                action="Add an assertion that fails if the contract under test is broken. Use the operations already in the test body.",
                do_not="Do not add assert True, a tautology, or a helper whose name merely starts with check_, validate_, _run_, or _safe_.",
                remediate=True,
                proof="python3 ci/weak_test_fixer.py no longer lists this test.",
                recommended_batch=row["file"],
            )
        )

    # --- unbounded ---
    for index, row in enumerate(sorted(unbounded, key=lambda item: (item["file"], item["line"])), 1):
        rel = row["file"]
        code = row.get("code") or line_text(rel, row["line"])
        classification, why, action, remediate = unbounded_disposition(rel, row["line"], code, row.get("bound"))
        add(
            item(
                id=f"TD-UB-{index:03d}",
                classification=classification,
                severity="MODERATE",
                family="UNBOUNDED_SEARCH",
                source_campaign="odoo_noncritical_gmp_campaign_pack",
                source_id="GMP-NC-D",
                file=rel,
                line=row["line"],
                symbol=function_at(source_of(rel), row["line"]),
                code=code,
                message=row["message"],
                why_open=why,
                action=action,
                do_not="Do not add limit=1 to silence the scanner.",
                remediate=remediate,
                proof="Re-run check_unbounded_searches. A business-complete search stays reported until the scanner can represent that intent.",
                recommended_batch=rel,
                bound=row.get("bound"),
            )
        )

    # --- sudo ---
    for index, row in enumerate(sudo, 1):
        rel = row["file"]
        add(
            item(
                id=f"TD-SUDO-{index:03d}",
                classification="real_debt",
                severity="MODERATE",
                family="UNJUSTIFIED_SUDO",
                source_campaign="odoo_noncritical_gmp_campaign_pack",
                source_id="GMP-NC-B",
                file=rel,
                line=row["line"],
                symbol=function_at(source_of(rel), row["line"]),
                code=row.get("code") or line_text(rel, row["line"]),
                message=row["message"],
                why_open="The elevation reason is on the following .search( line. GMP-NC-B requires '# sudo: <reason>' on the same line as .sudo(). A reason that is only nearby does not count.",
                action="Move the existing chatter-ACL reason onto the .sudo() line as '# sudo: sync ACL cannot read chatter'. Re-read the method before changing the elevation itself.",
                do_not="Do not remove the elevation unless mail.message is readable by the sync caller without it. Do not put TODO in the reason; the scanner rejects debt words.",
                remediate=True,
                proof="BusinessLogicAudit.check_missing_access_checks returns no row for this line.",
                recommended_batch=rel,
            )
        )

    if state:
        for index, row in enumerate(state, 1):
            add(
                item(
                    id=f"TD-STATE-{index:03d}",
                    classification="real_debt",
                    severity="MODERATE",
                    family="STATE_BYPASS",
                    source_campaign="odoo_noncritical_gmp_campaign_pack",
                    source_id="GMP-NC-C",
                    file=row["file"],
                    line=row["line"],
                    message=row["message"],
                    why_open="Live STATE_BYPASS finding.",
                    action="Compare with ci/check_state_guard_bypass.py before changing a transition.",
                    remediate=True,
                )
            )

    if sensitive:
        for index, row in enumerate(sensitive, 1):
            add(
                item(
                    id=f"TD-SEC-{index:03d}",
                    classification="real_debt",
                    severity=row.get("severity") or "HIGH",
                    family="SENSITIVE_DATA_LOGGED",
                    source_campaign="odoo_critical_debt_playbook_pack",
                    source_id="GAR-PROD-008",
                    file=row["file"],
                    line=row.get("line") or 0,
                    code=row.get("code") or "",
                    message=row.get("message") or "",
                    why_open="Live sensitive-logging finding. The two migration false positives were cleared.",
                    action="Stop interpolating the secret. Leave static prose that merely names a parameter.",
                    remediate=True,
                )
            )

    # schema false positives, one parent plus evidence children
    add(
        item(
            id="TD-SCAN-001",
            classification="scanner_misalignment",
            severity="CRITICAL",
            family="FIELD_NOT_FOUND",
            source_campaign="ci/baselines/odoo_audit_baseline.json",
            source_id="odoo_audit.check_field_mismatches",
            file="scripts/audit/odoo_audit.py",
            line=line_in_symbol(
                "scripts/audit/odoo_audit.py", "scan_view_field_refs", "current_model = model_match.group(1)"
            ),
            symbol="scan_view_field_refs",
            code="current_model = model_match.group(1)",
            message="View fields are checked against the wrong model.",
            why_open=(
                f"{sum(1 for row in gated if row['type'] == 'FIELD_NOT_FOUND')} live CRITICAL rows match "
                f"{sum(1 for row in schema_base.values() if row['type'] == 'FIELD_NOT_FOUND')} baseline fingerprints "
                f"(repeated fields share a fingerprint). new={len(schema_new)} stale={len(schema_stale)}. "
                "Three causes, recorded on each TD-FIELD row as scanner_cause: nested_subview, "
                "record_context_bleed (the model is not reset on the next ir.actions or ir.cron record), "
                "and cross_module_inherit (the field is added by another module's _inherit)."
            ),
            action="Teach scan_view_field_refs to enter a relational subview, to reset the model when a record ends, and to follow _inherit. Child TD-FIELD rows are the fixtures.",
            do_not="Do not add these field names onto the model named in the message. Do not delete the view columns or the action records.",
            remediate=True,
            proof="odoo_audit.py check_field_mismatches returns no FIELD_NOT_FOUND for a nested list whose fields exist on the comodel. Existing baseline fingerprints for this family become stale together.",
            recommended_batch="scripts/audit/odoo_audit.py",
        )
    )
    field_rows = [row for row in gated if row["type"] == "FIELD_NOT_FOUND"]
    for index, row in enumerate(sorted(field_rows, key=lambda item: (item["file"], item["line"], item["field"])), 1):
        relation = enclosing_relation(row["file"], row["line"])
        code = line_text(row["file"], row["line"])
        cause = field_scanner_cause(code, relation)
        why, action = FIELD_CAUSE_TEXT[cause]
        add(
            item(
                id=f"TD-FIELD-{index:03d}",
                classification="false_positive",
                severity="CRITICAL",
                family="FIELD_NOT_FOUND",
                source_campaign="ci/baselines/odoo_audit_baseline.json",
                source_id="TD-SCAN-001",
                parent_id="TD-SCAN-001",
                file=row["file"],
                line=row["line"],
                symbol=row["field"],
                code=code,
                message=row["message"],
                why_open=why,
                action=action,
                do_not="Do not declare this field on the parent model named in the message.",
                scanner_cause=cause,
                remediate=False,
                fingerprint=compute_fingerprint(row),
                model=row["model"],
                field=row["field"],
                enclosing_field=relation or "",
                recommended_batch="scripts/audit/odoo_audit.py",
            )
        )

    constraint_rows = [row for row in gated if row["type"] == "INVALID_CONSTRAINT_FIELD"]
    for index, row in enumerate(constraint_rows, 1):
        add(
            item(
                id=f"TD-CONSTRAINT-{index:03d}",
                classification="false_positive",
                severity="HIGH",
                family="INVALID_CONSTRAINT_FIELD",
                source_campaign="ci/baselines/odoo_audit_baseline.json",
                source_id="commission_override_pct",
                file=row["file"],
                line=row["line"],
                symbol="_check_override_pct_range",
                code=line_text(row["file"], row["line"]),
                message=row["message"],
                why_open="The constrains decorator names commission_override_pct. The field is added by plasticos_commission through _inherit. The single-file scanner cannot see it. The method body is a stub overridden by that module.",
                action="Leave the stub. A scanner fix may follow _inherit across modules; that is separate work.",
                do_not="Do not drop the decorator and do not redeclare the field on plasticos.transaction.",
                remediate=False,
                fingerprint=compute_fingerprint(row),
                model=row.get("model") or "",
                field="commission_override_pct",
            )
        )

    # deferred NC-B items still present
    add(
        item(
            id="TD-DEF-D01",
            classification="real_debt",
            severity="MODERATE",
            family="AUTOMATION_LOG_PAYLOAD",
            source_campaign="odoo_noncritical_gmp_campaign_pack",
            source_id="GMP-NC-B D-01",
            file="plasticos_intake_normalizer/models/intake_normalizer.py",
            line=619,
            symbol="_log_normalization",
            code=line_text("plasticos_intake_normalizer/models/intake_normalizer.py", 619),
            message="Normalization log create payload does not match plasticos.automation.log.",
            why_open="The create sends record_id, detail, and action_type normalize_*. The model requires name and res_id, stores text on note, and allows only six action_type values. The exception is logged at debug, so the log row is never written.",
            action="Either map onto name, res_id, note, and an allowed action_type, or stop calling the log. Decide the shared schema before changing either model.",
            do_not="Do not widen action_type with a normalize value only to silence the exception, and do not drop the try/except without a replacement record.",
            remediate=True,
            proof="A normalization run creates one plasticos.automation.log row whose res_id is the intake id, or the call is gone and a test shows the skip is intentional.",
            recommended_batch="plasticos_intake_normalizer/models/intake_normalizer.py",
            related_files=[
                "plasticos_intake_normalizer/models/intake_normalizer.py:608",
                "plasticos_automation/models/automation_log.py:13",
            ],
        )
    )
    add(
        item(
            id="TD-DEF-D02",
            classification="policy_deferred",
            severity="MODERATE",
            family="PUBLIC_RPC",
            source_campaign="odoo_noncritical_gmp_campaign_pack",
            source_id="GMP-NC-B D-02",
            file="plasticos_partner_import/models/partner_import_service.py",
            line=270,
            symbol="run_csv_import",
            code=line_text("plasticos_partner_import/models/partner_import_service.py", 270),
            message="Public import methods accept caller-chosen server paths.",
            why_open="run_csv_import (line 270) and run_default_csv_import (line 82) have no leading underscore. Any internal user who can call the model can pass paths. GMP-NC-B left this as an authority decision.",
            action="If import stays an operator action, restrict the group or reject paths outside the configured import directory. If it is already server-only, prefix the methods with _ and update the one caller.",
            do_not="Do not mark them private without updating every RPC and shell caller in the same change.",
            remediate=True,
            proof="An internal user who is not in the import group receives AccessError. A path outside the allowed directory is rejected.",
            recommended_batch="plasticos_partner_import/models/partner_import_service.py",
            related_files=["plasticos_partner_import/models/partner_import_service.py:82"],
        )
    )
    add(
        item(
            id="TD-DEF-D03",
            classification="policy_deferred",
            severity="MODERATE",
            family="PUBLIC_RPC",
            source_campaign="odoo_noncritical_gmp_campaign_pack",
            source_id="GMP-NC-B D-03",
            file="plasticos_geolocalize/models/res_partner_geo.py",
            line=38,
            symbol="cron_geo_backfill",
            code=line_text("plasticos_geolocalize/models/res_partner_geo.py", 38),
            message="Geo backfill cron method is public.",
            why_open="The method has no leading underscore, so any user who can call the model over RPC can start the Nominatim backfill. The cron XML can call a private method.",
            action="Rename to _cron_geo_backfill and point the ir.cron code at the private name.",
            do_not="Do not leave a public alias that calls the private method.",
            remediate=True,
            proof="The cron record calls the private method and a direct RPC as base.group_user is rejected.",
            recommended_batch="plasticos_geolocalize/models/res_partner_geo.py",
        )
    )
    add(
        item(
            id="TD-DEF-D04",
            classification="policy_deferred",
            severity="MODERATE",
            family="PUBLIC_RPC",
            source_campaign="odoo_noncritical_gmp_campaign_pack",
            source_id="GMP-NC-B D-04",
            file="plasticos_crm_sync/models/crm_connection.py",
            line=121,
            symbol="action_sync_now",
            code=line_text("plasticos_crm_sync/models/crm_connection.py", 121),
            message="Any internal user with write access can run VanillaSoft sync.",
            why_open="ir.model.access.csv grants base.group_user create/read/write on plasticos.crm.connection. action_sync_now is public. The orchestrator then reads plasticos_crm_sync.vanillasoft_api_key with sudo. The key is not returned.",
            action="Restrict action_sync_now to the group that is allowed to spend the VanillaSoft key, or require that group inside the method before building the adapter.",
            do_not="Do not log the key. Do not remove the sudo on the ICP read unless the chosen group can already read system parameters.",
            remediate=True,
            proof="base.group_user without the sync group cannot call action_sync_now. The allowed group still completes a dry-run or health check.",
            recommended_batch="plasticos_crm_sync/models/crm_connection.py",
            related_files=[
                "plasticos_crm_sync/security/ir.model.access.csv:2",
                "plasticos_crm_sync/services/orchestrator.py:820",
            ],
        )
    )
    add(
        item(
            id="TD-DEF-D05",
            classification="real_debt",
            severity="MODERATE",
            family="SECRET_IN_QUERY",
            source_campaign="odoo_noncritical_gmp_campaign_pack",
            source_id="GMP-NC-B D-05",
            file="plasticos_crm_sync/controllers/webhook.py",
            line=62,
            symbol="_extract_token",
            code=line_text("plasticos_crm_sync/controllers/webhook.py", 62),
            message="Webhook token is accepted from the query string.",
            why_open="args.get('token') is tried before the header and the bearer token. Query strings are written to access logs and Referer headers.",
            action="Accept only X-Plasticos-Webhook-Token and Authorization: Bearer. Reject a query token.",
            do_not="Do not log the token value while removing the query path.",
            remediate=True,
            proof="A request with ?token= and no header returns 401. The same token in the header or bearer scheme returns the current success body.",
            recommended_batch="plasticos_crm_sync/controllers/webhook.py",
        )
    )
    add(
        item(
            id="TD-DEF-D06",
            classification="documentation_misalignment",
            severity="LOW",
            family="DOCSTRING_DRIFT",
            source_campaign="odoo_noncritical_gmp_campaign_pack",
            source_id="GMP-NC-B D-06",
            file="plasticos_web_leads/controllers/web_lead_api.py",
            line=34,
            symbol="WebLeadController",
            code=line_text("plasticos_web_leads/controllers/web_lead_api.py", 36),
            message="Class docstring says config creation happens only after token validation.",
            why_open="_authenticate calls get_config() at line 75 before adapter.authenticate succeeds at line 100. Line 171's comment says 'sudo after token validation' and does not use the '# sudo:' marker. Controllers are outside the model sudo scanner.",
            action="Rewrite the class note so it matches the pre-auth singleton read. Put '# sudo: public route reads config before auth' on line 171 if that elevation stays.",
            do_not="Do not move get_config() to after auth as a drive-by. The pre-auth read is documented in the method itself at line 73.",
            remediate=True,
            proof="The class docstring no longer claims post-auth creation, and the line 171 comment matches the elevation that is actually there.",
            recommended_batch="plasticos_web_leads/controllers/web_lead_api.py",
            related_files=[
                "plasticos_web_leads/controllers/web_lead_api.py:75",
                "plasticos_web_leads/controllers/web_lead_api.py:171",
            ],
        )
    )
    add(
        item(
            id="TD-DEF-D07",
            classification="evidence_gap",
            severity="LOW",
            family="UNVERIFIED_ELEVATION",
            source_campaign="odoo_noncritical_gmp_campaign_pack",
            source_id="GMP-NC-B D-07",
            file="plasticos_commission/models/sales_dashboard.py",
            line=230,
            symbol="_compute_doc_status",
            code=line_text("plasticos_commission/models/sales_dashboard.py", 230),
            message="Dashboard sudo depends on Enterprise documents.document ACL.",
            why_open="The same-line reason is present, so UNJUSTIFIED_SUDO is clear. Whether a sales user can read documents.document without sudo was not re-run on an Enterprise database in this census.",
            action="On an Enterprise fixture, read documents.document as the dashboard group with and without sudo. Remove the sudo only if the read succeeds without it.",
            do_not="Do not remove the sudo on a Community-only run. The model is absent there and the code falls back to plasticos.document.",
            remediate=False,
            proof="An Enterprise test shows the dashboard group either reading the four doc types without sudo, or still receiving AccessError.",
            recommended_batch="plasticos_commission/models/sales_dashboard.py",
        )
    )
    add(
        item(
            id="TD-DEF-D08",
            classification="policy_deferred",
            severity="LOW",
            family="PUBLIC_RPC",
            source_campaign="odoo_noncritical_gmp_campaign_pack",
            source_id="GMP-NC-B D-08",
            file="plasticos_matching/models/match_result_writer.py",
            line=24,
            symbol="persist_match_lines",
            code=line_text("plasticos_matching/models/match_result_writer.py", 24),
            message="Match persistence method is public.",
            why_open="The method checks the Gate receipt and buyer access before it writes. Its name is still RPC-visible. GMP-NC-B called a private rename defence in depth, not a proven bypass.",
            action="Rename to _persist_match_lines and update the orchestrator call if no UI action needs the public name.",
            do_not="Do not weaken the receipt checks while renaming.",
            remediate=True,
            proof="The only production caller uses the private name. A JSON-RPC call of the old name fails.",
            recommended_batch="plasticos_matching/models/match_result_writer.py",
        )
    )

    hook_hits = []
    for path in sorted(ROOT.glob("plasticos_*/hooks.py")):
        rel = str(path.relative_to(ROOT))
        if rel not in on_branch:
            continue
        for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ".sudo()" in text:
                hook_hits.append((rel, number, text.strip()))
    writes = [hit for hit in hook_hits if ".write(" in hit[2]]
    reads = [hit for hit in hook_hits if hit not in writes]
    add(
        item(
            id="TD-DEF-D10",
            classification="accepted_bounded_debt",
            severity="LOW",
            family="HOOK_SUDO",
            source_campaign="odoo_noncritical_gmp_campaign_pack",
            source_id="GMP-NC-B D-10",
            file=reads[0][0] if reads else "plasticos_*/hooks.py",
            line=reads[0][1] if reads else 0,
            code=reads[0][2] if reads else "",
            message=f"{len(reads)} install-hook sudo reads on a superuser environment.",
            why_open="post_init_hook already runs as superuser. These sudo() calls are no-ops and sit outside the model scanner.",
            action="Leave them. A later hook cleanup can drop them in one mechanical change.",
            do_not="Do not remove a single module's hooks sudo as part of an unrelated PR.",
            remediate=False,
            proof="No behavior change. Optional: hooks.py contains no .sudo() and install-smoke still assigns cron users.",
            related_files=[f"{rel}:{line}" for rel, line, _text in reads],
            recommended_batch="plasticos_*/hooks.py",
        )
    )
    for rel, line, code in writes:
        add(
            item(
                id="TD-DEF-D10-WRITE",
                classification="accepted_bounded_debt",
                severity="LOW",
                family="HOOK_SUDO",
                source_campaign="odoo_noncritical_gmp_campaign_pack",
                source_id="GMP-NC-B D-10",
                file=rel,
                line=line,
                symbol="_merge_automation_groups_into_settings",
                code=code,
                message="Install hook writes implied_ids on base.group_system through sudo.",
                why_open="The reason is on the previous line, which the model scanner does not require here because hooks are out of scope. The write is how automation groups reach Settings.",
                action="Leave the write. If the comment is moved, put it on this line.",
                do_not="Do not drop the write. Settings would stop implying the automation groups.",
                remediate=False,
                recommended_batch=rel,
            )
        )

    add(
        item(
            id="TD-OWN-001",
            classification="scanner_misalignment",
            severity="LOW",
            family="DUPLICATE_STATE_AUTHORITY",
            source_campaign="odoo_noncritical_gmp_campaign_pack",
            source_id="GMP-NC-C",
            file="scripts/audit/business_logic_audit.py",
            line=225,
            symbol="check_state_machine_bypasses",
            code="def check_state_machine_bypasses(self):",
            message="Two state-bypass checkers remain. Both are silent on this census.",
            why_open="PR #237 kept both owners because neither predicate contains the other. ci/check_state_guard_bypass.py is the CI gate. The extended audit still has its own heuristic.",
            action="Collapse them only when one predicate is shown to contain the other on a fixture pair. Until then leave both.",
            do_not="Do not delete either checker while both are quiet. Do not add a third.",
            remediate=False,
            proof="A fixture that fails exactly one of the two checkers is attached to the collapsing change.",
            related_files=["ci/check_state_guard_bypass.py:94"],
            recommended_batch="scripts/audit/business_logic_audit.py",
            live_state_bypass=len(state),
        )
    )
    add(
        item(
            id="TD-XPATH-001",
            classification="scanner_misalignment",
            severity="LOW",
            family="XPATH_GUIDANCE",
            source_campaign="odoo_noncritical_gmp_campaign_pack",
            source_id="GMP-NC-E",
            file="ci/check_xpath_stability.py",
            line=51,
            symbol="RISKY_PATTERNS",
            code=line_text("ci/check_xpath_stability.py", 51),
            message="Class-anchor advice still says to add a positional [1].",
            why_open="Notebook findings were repaired to named anchors and the live XPath scan is empty. The class-anchor fix string still recommends //div[@class='oe_title'][1], which repo law forbids.",
            action="Change that fix string to a named anchor. Do not add [1] to any view.",
            do_not="Do not insert positional predicates into XML to satisfy this string.",
            remediate=True,
            proof="The CLASS_BASED_ANCHOR fix_suggestion contains no [1], and ci/check_xpath_stability.py still reports 0 findings.",
            recommended_batch="ci/check_xpath_stability.py",
        )
    )
    for limit_id, message, action in (
        (
            "TD-SCAN-UB-001",
            "A many-to-one equality (*_id = value) counts as an identity bound even when the field is categorical, for example country_id.",
            "Widen the identity rule only with a fixture where a categorical *_id equality currently suppresses a real full-table search.",
        ),
        (
            "TD-SCAN-UB-002",
            "A dynamic identity value is not proven non-null. False and None on an identity field are not a bound, but a name that might be null is still treated as a bound.",
            "Leave the rule. A non-null proof needs a data model the scanner does not have.",
        ),
        (
            "TD-SCAN-UB-003",
            "A domain list passed into a helper that appends to it is not modelled.",
            "Leave the rule unless a real unbounded search is hiding behind a helper.",
        ),
        (
            "TD-SCAN-UB-004",
            "Aliasing (b = domain; b.append(...)) is not modelled.",
            "Leave the rule unless a real unbounded search is hiding behind an alias.",
        ),
    ):
        add(
            item(
                id=limit_id,
                classification="scanner_misalignment",
                severity="LOW",
                family="UNBOUNDED_SEARCH_LIMIT",
                source_campaign="odoo_noncritical_gmp_campaign_pack",
                source_id="GMP-NC-D known limits",
                file="scripts/audit/performance_audit.py",
                line=310,
                symbol="_search_verdict",
                message=message,
                why_open="GMP-NC-D stated this limit and did not widen the scanner. No current app site is waiting on it.",
                action=action,
                do_not="Do not weaken a current bounded verdict to chase this limit.",
                remediate=False,
                recommended_batch="scripts/audit/performance_audit.py",
            )
        )

    # Hand-recorded. The audit scanners do not inspect field parameters.
    # plasticos.freight.estimate.status and plasticos.freight.quote.selected
    # declare tracking=True without mail.thread. Odoo warns once per field on
    # every registry load. The stored values and the load audit path are intact.
    tracking_batch = "plasticos_logistics tracking parameter"
    add(
        item(
            id="TD-TRACK-001",
            classification="real_debt",
            severity="LOW",
            family="ILLEGAL_FIELD_PARAMETER",
            source_campaign="registry_load",
            source_id="plasticos.freight.estimate.status",
            file="plasticos_logistics/models/freight_estimate.py",
            line=68,
            symbol="status",
            code="tracking=True,",
            message="Field plasticos.freight.estimate.status: unknown parameter 'tracking'",
            why_open=(
                "plasticos.freight.estimate does not inherit mail.thread, and no other module inherits it. "
                "Odoo 19 Field.setup warns once for each unknown parameter. mail.thread._valid_field_parameter "
                "is what makes tracking legal. write() lists status as immutable, so the parameter cannot emit "
                "a change note. The load records the result with message_post and a freight_estimate_persisted "
                "or freight_estimate_rejected event. The warning prints on every registry load."
            ),
            action="Delete tracking=True from status. Keep the column. The stored value and the load audit path stay.",
            do_not=(
                "Do not add mail.thread to plasticos.freight.estimate. "
                "The model is immutable evidence and cannot post chatter."
            ),
            remediate=True,
            proof=(
                "A registry load prints no unknown parameter 'tracking' for plasticos.freight.estimate.status. "
                "status is still stored on the estimate row."
            ),
            recommended_batch=tracking_batch,
            related_files=[
                "plasticos_logistics/models/freight_estimate.py:157",
                "plasticos_logistics/models/load.py:645",
                "plasticos_logistics/models/load.py:649",
            ],
        )
    )
    add(
        item(
            id="TD-TRACK-002",
            classification="real_debt",
            severity="LOW",
            family="ILLEGAL_FIELD_PARAMETER",
            source_campaign="registry_load",
            source_id="plasticos.freight.quote.selected",
            file="plasticos_logistics/models/freight_quote.py",
            line=541,
            symbol="selected",
            code="selected = fields.Boolean(default=False, tracking=True)",
            message="Field plasticos.freight.quote.selected: unknown parameter 'tracking'",
            why_open=(
                "plasticos.freight.quote does not inherit mail.thread, and no other module inherits it. "
                "state on plasticos.freight.quote.request in this same file is tracked legally because that "
                "model inherits mail.thread. selected changes only through action_select, which records "
                "freight_quote_selected on the load. The warning prints on every registry load."
            ),
            action="Delete tracking=True from selected. Keep the column. action_select remains the only writer.",
            do_not=(
                "Do not add mail.thread to plasticos.freight.quote. "
                "Selection already writes the freight event on the load."
            ),
            remediate=True,
            proof=(
                "A registry load prints no unknown parameter 'tracking' for plasticos.freight.quote.selected. "
                "selected is still stored, and action_select still records freight_quote_selected."
            ),
            recommended_batch=tracking_batch,
            related_files=[
                "plasticos_logistics/models/freight_quote.py:70",
                "plasticos_logistics/models/freight_quote.py:698",
                "plasticos_logistics/models/freight_quote.py:711",
            ],
        )
    )

    by_class = collections.Counter(row["classification"] for row in items)
    remediate_count = sum(1 for row in items if row["remediate"])
    document = {
        "schema": "plasticos.odoo_tech_debt.open_register.v1",
        "subject": {
            "repository": "cryptoxdog/IB-Odoo_19",
            "ref": "origin/Staging",
            "sha": head,
            "census_date": datetime.now(UTC).date().isoformat(),
            "supersedes": [
                "docs/campaigns/odoo_critical_debt_playbook_pack",
                "docs/campaigns/odoo_noncritical_gmp_campaign_pack",
            ],
        },
        "sealed": [
            {
                "id": "GAR-PROD-001",
                "result": "closed",
                "where": "PR #234 purchase delivery term stays M2M and is batched",
            },
            {"id": "GAR-PROD-002", "result": "closed", "where": "PR #234 unique load_id"},
            {"id": "GAR-PROD-003", "result": "closed", "where": "PR #234 transaction profile batch and recompute"},
            {"id": "GAR-PROD-004", "result": "closed", "where": "material-profile selection was not collapsed"},
            {"id": "GAR-PROD-005", "result": "closed", "where": "PR #234 facility uniqueness batch and DB constraint"},
            {"id": "GAR-PROD-006", "result": "closed", "where": "PR #234 commission partial unique index"},
            {"id": "GAR-PROD-007", "result": "closed", "where": "PR #234 AST N+1 scanner; browse() is not a query"},
            {"id": "GAR-PROD-008", "result": "closed", "where": "PR #234 AST sensitive-log scanner; live count 0"},
            {
                "id": "GMP-NC-A",
                "result": "closed_owner",
                "where": "PR #235 one weak-test owner; assertion-free tests remain as TD-WEAK",
            },
            {
                "id": "GMP-NC-B",
                "result": "closed_elevations",
                "where": "PR #236; later TD-SUDO-001 and TD-DEF rows are the residue",
            },
            {
                "id": "GMP-NC-C",
                "result": "quiet",
                "where": "PR #237 both checkers silent; TD-OWN-001 records the duplicate",
            },
            {
                "id": "GMP-NC-D",
                "result": "closed_genuine_overfetch",
                "where": "PR #240 validation domains and negative batch_limit; scanner residue is TD-UB",
            },
            {
                "id": "GMP-NC-E",
                "result": "closed_findings",
                "where": "live XPath scan empty; TD-XPATH-001 is leftover fix text",
            },
            {"id": "GMP-NC-F", "result": "replaced", "where": "this register is the reconciliation"},
        ],
        "rules": [
            "Filter remediate=true. Rows with remediate=false are evidence or accepted residue.",
            "One recommended_batch per change. Do not clear the register in one branch.",
            "Do not add limit=1 to an UNBOUNDED_SEARCH row.",
            "Do not add a parent-model field for a FIELD_NOT_FOUND row.",
            "A rewritten N+1 line must remove its fingerprint from ci/baselines/extended_audit_baseline.json in the same change.",
            "Do not special-case a file inside performance_audit.py or security_audit.py.",
            (
                "Do not inherit mail.thread on plasticos.freight.estimate or plasticos.freight.quote "
                "to silence tracking. Remove tracking=True. TD-TRACK-001 and TD-TRACK-002."
            ),
            "Publication of a fix is make pr.",
        ],
        "census": {
            "live_n_plus_one": len(nplus),
            "n_plus_one_new": len(new_high),
            "n_plus_one_stale_baseline": len(stale),
            "extended_baseline_entries": len(base),
            "weak_tests": len(weak),
            "unbounded_search": len(unbounded),
            "unjustified_sudo": len(sudo),
            "state_bypass": len(state),
            "sensitive_logged": len(sensitive),
            "field_not_found": len(field_rows),
            "invalid_constraint": len(constraint_rows),
            "schema_new": len(schema_new),
            "schema_stale": len(schema_stale),
            "schema_baseline_entries": len(schema_base),
            "illegal_field_parameter": 2,
            "items": len(items),
            "remediate_true": remediate_count,
            "by_classification": dict(by_class),
        },
        "items": items,
    }
    json_path = OUT / "OPEN_REGISTER.json"
    json_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(json_path.read_bytes()).hexdigest()
    rel = json_path.relative_to(REPO).as_posix()
    (OUT / "OPEN_REGISTER.sha256").write_text(f"{digest}  {rel}\n", encoding="utf-8")
    write_markdown(document, OUT / "OPEN_REGISTER.md")
    print(json.dumps(document["census"], indent=2))
    print("items", len(items), "remediate", remediate_count)
    print("sha", head)


def md_cell(value) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def write_markdown(document: dict, path: Path) -> None:
    subject = document["subject"]
    census = document["census"]
    lines = [
        "# Open tech-debt register",
        "",
        f"Subject: `{subject['repository']}` `{subject['ref']}` `{subject['sha']}`.",
        f"Census date: {subject['census_date']}.",
        "",
        "Machine contract: [`OPEN_REGISTER.json`](OPEN_REGISTER.json). This page is the same census in reading order. If they differ, the JSON wins.",
        "",
        "An agent should load the JSON, keep rows with `remediate` true, and take one `recommended_batch` at a time.",
        "",
        "## Also on the radar",
        "",
        "[Proposed ADR backlog, 2026-08](../../adr/PROPOSED-ADR-BACKLOG-2026-08-architecture-convergence.md) "
        "is the session pack that became ADR-010 through ADR-019. Those ten files are Accepted. "
        "This register does not queue the backlog as code debt. Read the Accepted ADRs. "
        "The draft sections in the backlog still repeat the pre-acceptance notes.",
        "",
        "Open campaigns are [`workflow_state.md`](../../../workflow_state.md). "
        "This register does not copy those campaigns. It remains the debt tracker.",
        "",
        "## Counts",
        "",
        "| Measure | Value |",
        "|---|---:|",
    ]
    for key, value in census.items():
        if key == "by_classification":
            continue
        lines.append(f"| {key} | {value} |")
    lines.append("")
    lines.append("| Classification | Items |")
    lines.append("|---|---:|")
    for key, value in sorted(census["by_classification"].items()):
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "## Sealed work (do not reopen)",
            "",
            "| ID | Result | Where |",
            "|---|---|---|",
        ]
    )
    for row in document["sealed"]:
        lines.append(f"| {md_cell(row['id'])} | {md_cell(row['result'])} | {md_cell(row['where'])} |")
    lines.extend(["", "## Rules", ""])
    for rule in document["rules"]:
        lines.append(f"- {rule}")

    families = []
    seen = set()
    for row in document["items"]:
        if row["family"] not in seen:
            seen.add(row["family"])
            families.append(row["family"])
    for family in families:
        rows = [row for row in document["items"] if row["family"] == family]
        lines.extend(["", f"## {family}", "", f"{len(rows)} item(s).", ""])
        lines.append("| ID | Remediate | Class | File | Line | Symbol | Code / message |")
        lines.append("|---|---|---|---|---:|---|---|")
        for row in rows:
            detail = row.get("code") or row.get("message") or ""
            if row.get("scanner_cause"):
                detail = f"[{row['scanner_cause']}] {detail}"
            if len(detail) > 140:
                detail = detail[:137] + "..."
            lines.append(
                "| {id} | {rem} | {cls} | `{file}` | {line} | {sym} | {detail} |".format(
                    id=row["id"],
                    rem="yes" if row["remediate"] else "no",
                    cls=row["classification"],
                    file=md_cell(row["file"]),
                    line=row.get("line") or "",
                    sym=md_cell(row.get("symbol") or ""),
                    detail=md_cell(detail),
                )
            )
        lines.extend(["", "Actions:", ""])
        shown = set()
        for row in rows:
            key = (row["action"], row["do_not"])
            if key in shown:
                continue
            shown.add(key)
            ids = [other["id"] for other in rows if (other["action"], other["do_not"]) == key]
            head = ids[0] if len(ids) > 8 else ", ".join(ids)
            if len(ids) > 8:
                head = f"{ids[0]} … {ids[-1]} ({len(ids)} rows, same action)"
            lines.append(f"- {head}: {row['action']} {row['do_not']}".rstrip())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
