# GMP-NC-C — State Audit Owner Convergence

## Contract

**ID:** GMP-NC-C  
**Tier:** CI / State-Machine Assurance  
**Objective:** Eliminate duplicate state-transition audit authority.  
**Predecessor:** none strictly required; consume current tree.  
**Expected runtime behavior change:** none unless the authoritative checker independently proves a real defect.

## Locked scope

Primary owners:

- `ci/check_state_guard_bypass.py`
- `scripts/audit/business_logic_audit.py`
- `scripts/audit/run_all_audits.py`
- tests for these tooling surfaces if required.

## Non-goals

- Do not refactor application state machines.
- Do not add bypass contexts merely to silence warnings.
- Do not alter canonical action methods unless the authoritative checker proves an actual bug.
- Do not reopen previously hardened state-machine work.

## Phase 0 — Bind current target

Record current `Staging` SHA and current CI wiring. Verify which state-guard checker currently blocks/advises in CI.

## Phase 1 — Compare owners

Run/inspect both state finding sources and build a comparison:

```text
extended STATE_BYPASS finding
<->
ci/check_state_guard_bypass.py finding
```

Classify each disagreement:

- authoritative guard says real issue;
- extended audit false positive;
- extended audit blind spot;
- UNKNOWN.

No runtime mutation in Phase 1.

## Phase 2 — Ownership decision

Target architecture:

```text
canonical model transition owners
        -> ci/check_state_guard_bypass.py
        -> single state-bypass verdict

extended audit
        -> consume/omit duplicate concern
```

`ci/check_state_guard_bypass.py` remains authoritative only if exact-current evidence confirms it still models guarded Odoo state transitions more faithfully than the generic extended heuristic.

## Phase 3 — Tooling convergence

Remove duplicate state-transition judgment from the weaker owner.

Do not duplicate the stronger checker by copy/paste.
Do not create a third checker.

If the authoritative checker exposes a genuine runtime defect, STOP this GMP and report that defect as a separate runtime remediation candidate rather than silently expanding this tooling campaign.

## Phase 4 — Validation

Prove:

- authoritative state-guard tests/checks retain all existing protections;
- extended audit no longer creates duplicate Moderate state warnings;
- state-machine application files are unchanged unless separately authorized;
- bypass policy is not weakened.

## Phase 5 — Before/after comparison

Report:

- prior `STATE_BYPASS` Moderate count;
- authoritative checker count;
- post-convergence count;
- disagreements closed;
- any runtime candidate deferred.

## Phase 6 — Evidence and publication

Emit report and publish only through a verified current publication surface.

## Acceptance

PASS only if:

- one state-bypass authority remains;
- no state protection is weakened;
- no runtime refactor was smuggled into a tooling PR;
- previous remediation remains sealed.
