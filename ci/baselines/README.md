# Audit baselines — per-finding allowlist, not a count

Each file here is a checked-in log of **already-reviewed** CRITICAL/HIGH
findings from a `scripts/audit/*.py` scanner — either a confirmed scanner
false positive, or real technical debt that's been triaged and accepted for
now. The CI `audit-baseline` job (and `make audit-baseline` locally) diffs
each scanner's current findings against the matching file here and only
fails on findings that **aren't logged yet**.

| File | Scanner | Gated severities |
|---|---|---|
| `odoo_audit_baseline.json` | `scripts/audit/odoo_audit.py` | CRITICAL, HIGH |
| `extended_audit_baseline.json` | `scripts/audit/run_all_audits.py` | HIGH |

## Why per-finding, not a count

A raw count baseline (`if HIGH > 15: fail`) can't tell "one known issue got
fixed and one new one appeared" apart from "nothing changed" — the count
stays flat either way, so a real regression can hide behind an unrelated fix.
Fingerprinting each finding (see `scripts/audit/baseline_utils.py`) and
diffing the actual set closes that gap.

Fingerprints are computed from the finding's `type` + `file` + the most
specific available identity (`model`/`field` for schema-level findings, or
the exact offending source line for pattern-level findings) — **not** the
line number alone, so unrelated edits elsewhere in a file don't invalidate
an entry. Editing the flagged line itself is correctly treated as a new
finding requiring re-review.

## Workflow: a scanner flags something new

1. **Investigate.** Is it a real bug, a scanner false positive, or accepted
   debt?
2. **Real bug → fix the code.** Nothing to do here.
3. **False positive / accepted debt → log it, don't patch the scanner.**
   Run the report, then dump ready-to-paste entries for anything not yet in
   the baseline:

   ```bash
   python3 scripts/audit/odoo_audit.py .
   python3 scripts/audit/check_baseline.py \
     odoo_audit_report.json ci/baselines/odoo_audit_baseline.json \
     --severities CRITICAL,HIGH --dump-new

   # or for the extended audit:
   python3 scripts/audit/run_all_audits.py .
   python3 scripts/audit/check_baseline.py \
     extended_audit_report.json ci/baselines/extended_audit_baseline.json \
     --severities HIGH --dump-new
   ```

4. Review the printed JSON entries (each has `type`, `file`, `line`,
   `message` — human-readable, no opaque data), then merge them into the
   `entries` array of the matching file. Commit that change **in the same
   PR** as the code that introduced the finding, with a short justification
   (why it's a false positive, or why the debt is accepted) either in the
   commit message or as a new `_root_cause`-style note in the file.
5. **Never** add special-casing for a specific finding inside
   `scripts/audit/odoo_audit.py`, `performance_audit.py`, or
   `security_audit.py` themselves to silence it — the scanners stay generic;
   only the log grows.

## Stale entries

If a baseline entry's underlying finding disappears (e.g. the flagged code
was refactored away), `check_baseline.py` reports it as a "stale baseline
entry" but does **not** fail the gate — pruning stale entries is housekeeping,
never required to unblock CI. Feel free to remove them opportunistically.
