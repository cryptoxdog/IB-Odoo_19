# GMP-NC-C — State Audit Containment

## Contract

**ID:** GMP-NC-C  
**Tier:** CI / State-Machine Assurance  
**Objective:** Decide state-audit ownership from containment. Keep both checks until one finding set is shown to contain the other.  
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

## Phase 2 — Containment decision

The two checks are adjacent until the Phase 1 comparison proves otherwise.

```text
CI guard check
        models with _validate_state_transition
        .write({'state': ...}) missing bypass_state_guard
        includes XML server actions

extended STATE_BYPASS
        any model with a Selection state or status
        self.write({'state': ...}) outside action_*, pipeline methods,
        and methods whose context contains "State transitions"
```

Decide from the census:

```text
one finding set contains the other
        -> converge to the containing owner
        -> remove only the contained duplicate judgment
        -> ci/check_state_guard_bypass.py stays the owner of the guard

the sets do not nest
        -> keep both concerns
        -> record them as adjacent, not duplicates
        -> do not delete STATE_BYPASS to shrink the Moderate count
```

Do not treat the CI checker's existence as a containment proof.

## Phase 3 — Tooling convergence

Apply only the Phase 2 decision.

When the sets nest, remove the contained judgment from the weaker owner.
When they do not nest, leave both owners in place and stop with that evidence.

Do not duplicate either checker by copy/paste.
Do not create a third checker.

If the authoritative checker exposes a genuine runtime defect, STOP this GMP and report that defect as a separate runtime remediation candidate rather than silently expanding this tooling campaign.

## Phase 4 — Validation

Prove:

- authoritative state-guard tests/checks retain all existing protections;
- extended `STATE_BYPASS` is removed only for findings the CI guard set actually contains;
- non-overlapping `STATE_BYPASS` findings remain;
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

- one owner remains only for a proven nested finding set;
- non-overlapping findings remain under their existing owner;
- no state protection is weakened;
- no runtime refactor was smuggled into a tooling PR;
- previous remediation remains sealed.
