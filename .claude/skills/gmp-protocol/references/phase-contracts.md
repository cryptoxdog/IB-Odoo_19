---
skill_schema: 1
layer: reference
role: phase_contract
tags: [gmp, phases, contract]
owner: igor_beylin
status: active
version: 1.0.0
updated: 2026-06-04
---

# GMP Phase Contracts (0–6)

Compressed input/output/exit contract per phase. Long form: `docs/gmp_protocol/cursor-phase-{0..6}-*.md`.

Each phase ends with its named status line and proceeds only if the exit gate is satisfied.

## Phase 0 — TODO Plan Lock

- **Does:** establishes ground truth (real files, classes, signatures from this repo), reads relevant ADRs (`.cursor/rules/*.mdc`, `docs/adr/`), emits the locked plan. No code edits.
- **Plan record (per TODO):**
  ```text
  [TODO T-001]
  Phase: {1-6}
  File: {relative/path}
  Operation: {Insert|Replace|Delete|Wrap|Create}
  Anchor: {line N or unique string}
  Description: {clear, testable behavior}
  Dependencies: {none | T-xxx, ...}
  ```
- **Also declare:** MODIFICATION LOCK (may-modify list / must-not-modify list) and `ADRs CONSULTED`.
- **Rules:** monotonic IDs; one file + one operation group per TODO; no placeholders, no "maybe/likely/should"; no protected path scheduled.
- **Exit:** "Phase 0 complete. TODO PLAN locked. ADRs consulted: [list]." Stop for approval if scope is high-risk or ambiguous.

## Phase 1 — Baseline Confirmation

- **Does:** validates the plan against reality; no behavior change.
- **Per TODO checks:** file exists; anchor resolves **uniquely** (multiple matches → AMBIGUOUS); target is not a protected path; dependency chain is acyclic and satisfiable.
- **Output:** baseline report with per-TODO `READY | BLOCKED | AMBIGUOUS` and `OVERALL STATUS: READY | PARTIAL | BLOCKED`.
- **Exit:** proceed to Phase 2 only on READY (PARTIAL → fix/remove blocked TODOs; BLOCKED → revise plan), or explicit human override.

## Phase 2 — Implementation

- **Does:** applies only READY TODOs.
- **Operation semantics:** Insert = add adjacent to anchor; Replace = swap only the indicated block; Delete = remove the indicated block; Wrap = enclose existing code (e.g. try/except); Create = new file (wire into `__init__.py` / manifest as needed).
- **Standards:** preserve import order and file conventions; no dead code; no new TODOs/placeholders; minimal, deterministic, line-anchored.
- **Output (per TODO):** `[T-xxx] APPLIED — file, operation, lines {start}-{end}, notes` or `[T-xxx] FAILED — reason`.
- **Exit:** "Phase 2 complete. {n_applied} applied, {n_failed} failed."

## Phase 3 — Enforcement

- **Does:** adds only the guards the TODOs require — capability/ACL coverage for new models, approval gates for high-risk ops, observability/logging, constraint patterns. Skip cleanly when none are needed.
- **Rules:** never weaken existing governance; never bypass approval requirements.
- **Output:** governance report (gates added, hooks added, ACL/logging verified).
- **Exit:** "Phase 3 complete. Governance protections updated."

## Phase 4 — Validation

- **Does:** runs the gates that apply to the change. No app-code edits (tests only if the plan lists them).
- **Order:** `python -m py_compile` / import check → targeted unit tests → integration/smoke → repo gate `make pr-check` (ruff, XML, module wiring, circular deps, Odoo 19 patterns).
- **Output:** validation report with pass/fail counts and failure summaries; `Recommendation: PROCEED | BLOCKED`.
- **Exit:** all-pass → Phase 5; any fail → fix or block (never proceed past a failure).

## Phase 5 — Recursive Verification

- **Does:** diffs actual changes vs the locked plan. No new changes.
- **Checks:** every TODO applied as specified; files modified match the plan; line ranges match; protected systems untouched; no high-risk action without approval; no scope creep.
- **Output:** `OVERALL STATUS: VERIFIED | DISCREPANCY_FOUND` with any discrepancy detail.
- **Exit:** finalize only when VERIFIED; otherwise stop and report.

## Phase 6 — Finalization

- **Does:** consolidates phase outputs into one evidence report; no code changes.
- **Output:** report at `reports/GMP-Report-{NNN}-{slug}.md` per `references/evidence-report.md`, ending with the verbatim final declaration.
- **Exit:** "Phase 6 complete. GMP run {RUN_ID} finalized."

## Fail Rule (every phase)

If any checklist item cannot be marked with evidence → STOP. Report the exact gap and recovery options; the human chooses the next action.
