---
skill_schema: 1
layer: reference
role: report_contract
tags: [gmp, evidence, report, declaration]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-04
---

# Evidence Report Contract

Every GMP run ends with one signed report in `reports/`. Long form: `docs/gmp_protocol/cursor-phase-6-finalization.md` and `docs/gmp_protocol/gmp-report-template.md`.

## Naming & Numbering

- Path: `reports/GMP-Report-{NNN}-{slug}.md` (e.g. `reports/GMP-Report-134-feature-x.md`).
- `{NNN}` = highest existing report number + 1, zero-padded to 3 digits. Find it by listing `reports/GMP-Report-*.md` and taking the max numeric prefix.
- `{slug}` = short kebab description of the change.
- `Run ID` = a descriptive tag (e.g. `GMP-FIX-AI-FALLBACK`) or, when none is chosen, default to `GMP-{NNN}` matching the file number.

## Report Shape (PlasticOS)

Header block:

```text
# GMP Report {NNN} — {Title}

**Run ID:** {RUN_ID}
**Date:** {YYYY-MM-DD}
**Target Branch:** Staging
**Scope:** {paths touched} ({additive only | refactor | fix})
**Commit Message:** `{conventional commit}`
```

Required sections (numbered; merge/rename to match the actual change but cover all evidence):

1. **PLAN** — context + the locked TODO table (`ID | File | Lines | Action | Status`) and the MODIFICATION LOCK (may-modify / must-not-modify) and `ADRs CONSULTED`.
2. **CHANGES** — files, line ranges, action, description (insertions/deletions).
3. **TODO → CHANGE MAP** — each TODO mapped to its phase, file, operation, and result.
4. **VALIDATION** — gate results: `py_compile`, import test, ruff, XML, `make pr-check`, unit tests (X passed).
5. **INVARIANTS CHECK** — protected systems untouched, no scope drift, repo guardrails honored.
6. **DECLARATION** — the verbatim final declaration.

The canonical 10-section finalization layout (Change Summary, Locked TODO Plan, Ground Truth, Files Modified, Implementation Evidence, Governance Updates, Tests Run, Validation Results, Invariants Check, Final Declaration) is acceptable when a fuller record is warranted — see `docs/gmp_protocol/cursor-phase-6-finalization.md`.

## Final Declaration (verbatim)

End every report with exactly:

```text
Phases 0-6 complete. No assumptions. No drift.
```

This is the repo-canonical wording — it matches `gmp-report-template.md` and the actual report history (e.g. reports 001, 020, 132, 133, 134). The long-form doc `docs/gmp_protocol/cursor-phase-6-finalization.md` shows `All phases (0–6) complete. No assumptions. No drift.`; per the Authority Order (ground truth > canonical docs), use the repo wording above for consistency. Do not flip between the two forms.

When a fuller finalization record is warranted, append to the same base line:

```text
GMP run {RUN_ID} finalized.
No further changes permitted.
```

## Checklist Rule

Checklist marks must never be pre-checked. A box is marked only with attached evidence (line numbers, test counts, gate output). If any item lacks evidence, the run is `⚠️ PARTIAL` or `❌ FAILED`, not `✅ COMPLETE`.
