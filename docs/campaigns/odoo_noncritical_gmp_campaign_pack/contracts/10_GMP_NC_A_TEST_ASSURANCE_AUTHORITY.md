# GMP-NC-A — Test Assurance Authority Convergence

## Contract

**ID:** GMP-NC-A  
**Tier:** CI / Assurance Tooling  
**Objective:** Establish one truthful weak-test owner and remove pseudo-coverage claims from the extended audit.  
**Predecessor:** none required; branch from then-current `origin/Staging`.  
**Expected runtime behavior change:** none.

## Locked scope

Primary owners expected in scope:

- `ci/weak_test_fixer.py`
- `scripts/audit/test_audit.py`
- `scripts/audit/run_all_audits.py`
- existing tests for these audit tools, or the smallest existing suitable test location

No application model/business-logic files may be changed.

## Non-goals

- Do not add hundreds of assertions to tests.
- Do not convert pytest tests to unittest style.
- Do not create fake coverage thresholds.
- Do not build Odoo runtime coverage infrastructure in this GMP.
- Do not touch High N+1/logging scanner work.

## Phase 0 — Bind current target

1. Record current `origin/Staging` SHA.
2. Confirm working branch/base and repository cleanliness.
3. Read the exact current versions of `test_audit.py`, `weak_test_fixer.py`, `run_all_audits.py`, relevant CI wiring, and current test-quality policy.
4. If the current tree has already converged these owners, stop and report `ALREADY_SATISFIED` rather than recreating work.

## Phase 1 — Census before mutation

Produce a before-state inventory:

- count of `WEAK_TEST` findings from the extended audit;
- count/list from `ci/weak_test_fixer.py`;
- count of `NO_TEST_COVERAGE` findings;
- exact disagreement set between the two weak-test analyzers;
- confirm whether `raise AssertionError(...)` is recognized.

Do not mutate code in Phase 1.

## Phase 2 — Resolve authoritative ownership

Architecture to realize:

```text
ci/weak_test_fixer.py
        -> sole assertion-quality semantic owner

actual Odoo runtime evidence
        -> future coverage authority

scripts/audit/test_audit.py
        -> no independent weak-test doctrine
        -> no static regex claim presented as runtime coverage
```

Required behavior:

- bare `assert` recognized;
- unittest `assert*` recognized;
- `pytest.raises` / `assertRaises` recognized;
- explicit `raise AssertionError(...)` recognized;
- helper-based assertion evidence remains supported where current policy already permits it;
- genuinely assertion-free tests remain detectable.

`NO_TEST_COVERAGE` must either be retired from factual audit output or explicitly downgraded/reframed so it cannot be mistaken for measured Odoo runtime coverage. Prefer removing the false claim rather than inventing a new heuristic.

## Phase 3 — Implement smallest repair

Modify only the existing owners needed to achieve Phase 2.

Do not create a new test-audit framework.
Do not add a new file unless no existing test surface can validate the scanner semantics.

## Phase 4 — Validation

Validate, at minimum:

- a bare-assert pytest test is not flagged;
- `pytest.raises` is not flagged;
- `raise AssertionError` is not flagged;
- a genuinely assertion-free test is flagged;
- extended audit no longer duplicates weak-test truth;
- pseudo `NO_TEST_COVERAGE` does not survive as a factual runtime-coverage claim;
- unrelated audit families remain behaviorally unchanged.

Discover and use only exact-current repo validation commands whose semantics are verified from the repo at execution time.

## Phase 5 — Recursive comparison

Compare before vs after:

- Moderate count delta;
- weak-test finding delta;
- `NO_TEST_COVERAGE` delta;
- any newly exposed findings.

New unrelated findings are REPORT ONLY. They do not widen this GMP.

## Phase 6 — Evidence and publication

Emit a GMP report with exact SHA coordinates and before/after counts.

Before publication, verify the current repo publication surface. If `make pr` still implements the operator-locked publication SSOT, use it exactly once for final publication. Otherwise stop on the mismatch; do not substitute another publication path.

## Acceptance

PASS only if:

- one weak-test semantic owner remains;
- valid pytest assertion forms are not false-positive debt;
- explicit `AssertionError` is recognized;
- pseudo-runtime-coverage claims are removed;
- no runtime application files changed;
- no prior High/Critical remediation reopened.

## Stop conditions

STOP if:

- current repo policy declares a different authoritative weak-test owner;
- implementing the fix requires runtime application changes;
- a proposed change would create a new coverage framework;
- current `Staging` materially contradicts the architecture above.
