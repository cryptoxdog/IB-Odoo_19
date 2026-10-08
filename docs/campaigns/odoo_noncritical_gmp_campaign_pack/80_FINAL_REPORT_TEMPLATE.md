# GMP Evidence Report Template

## Identity

- GMP ID:
- Objective:
- Repository:
- Base branch:
- Base SHA:
- Working branch:
- Final HEAD:
- Predecessor receipt/PR/HEAD:

## Phase 0 — Bound target

- Current repo law inspected:
- Current relevant owners inspected:
- Current publication surface verified:
- Entry gate: PASS / BLOCKED

## Phase 1 — Before-state census

| Finding family | Before count | Evidence |
|---|---:|---|
| | | |

## Phase 2 — Root-cause decision

- Root cause:
- Authoritative owner:
- Highest upstream fix:
- Alternatives rejected:
- Unknowns:

## Modification lock

| File | Existing/New | Why required |
|---|---|---|
| | | |

No other files modified: YES / NO

## Phase 3 — Realization

Summarize implemented change without restating unrelated repository history.

## Phase 4 — Validation

| Proof | Result | Evidence |
|---|---|---|
| | PASS/FAIL/UNKNOWN | |

## Phase 5 — Before/after comparison

| Finding family | Before | After | Delta | Explanation |
|---|---:|---:|---:|---|
| | | | | |

New unrelated findings discovered:

- none / list as REPORT ONLY

## No-reopen proof

- Prior completed Critical/High remediation touched: YES / NO
- If YES, exact blocking contradiction that required it:
- Otherwise previous campaign remained sealed: YES / NO

## Runtime propagation

- Runtime modules changed:
- Version bumps required/completed:
- Migrations required/completed:
- Upgrade/runtime proof:

## Publication

- Current `make pr` publication semantics verified against exact target: YES / NO
- Publication attempted: YES / NO
- Result:
- Remote/PR HEAD equality evidence:

## Verdict

- CLOSED
- PARTIAL
- BLOCKED
- REOPEN_REQUIRED

## Next action

Exactly one smallest safe next action, or `NONE` if this GMP is closed.
