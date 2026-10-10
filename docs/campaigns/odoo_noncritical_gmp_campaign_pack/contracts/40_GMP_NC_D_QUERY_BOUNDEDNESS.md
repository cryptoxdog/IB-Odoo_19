# GMP-NC-D — Query Boundedness Semantics

## Contract

**ID:** GMP-NC-D  
**Tier:** Runtime Performance / ORM Semantics  
**Objective:** Resolve genuine unsafe unbounded searches by query intent, not by mechanically adding limits.  
**File isolation:** `check_unbounded_searches` is in scope. `check_n_plus_one_queries` is not. The High N+1 scanner slice owns that method.

## Entry gate

Record whether the High performance-scanner slice has landed.

Proceed when the modification lock excludes `check_n_plus_one_queries` and any N+1 fixtures owned by that slice.

If an unmerged High slice already modifies `scripts/audit/performance_audit.py`, stack on that HEAD or wait.

If the lock cannot keep the two edits apart: **BLOCKED**. Do not fork a second scanner.

## Locked scope

Owned finding family:

- `UNBOUNDED_SEARCH` Moderate findings emitted by the post-hardening scanner.

Runtime files may change only where a surviving finding is proven to represent unsafe query behavior.

## Non-goals

- No blind `limit=1` additions.
- No query-result truncation for scanner silence.
- No reopening High N+1 repairs.
- No broad ORM refactor.
- No new data model fields.

## Phase 0 — Bind current target

Record current SHA, performance-scanner predecessor identity, and exact current scanner behavior.

## Phase 1 — Fresh census

Generate a fresh `UNBOUNDED_SEARCH` inventory from current code.

For every finding classify query intent:

1. existence;
2. count-only;
3. single authoritative record;
4. input-bounded batch;
5. business-complete set;
6. truly large traversal;
7. small canonical registry;
8. UNKNOWN.

No mutation before all findings are classified.

## Phase 2 — Select correct ORM realization

Allowed transformations only when semantically justified:

| Intent | Preferred shape |
|---|---|
| existence | bounded existence lookup |
| count-only | `search_count` or equivalent |
| single authoritative record | unique identity + bounded single lookup |
| input-bounded batch | complete query over explicit identity set |
| business-complete set | keep complete result |
| large traversal | explicit batching/pagination |
| small registry | complete lookup may remain |
| UNKNOWN | block |

The scanner warning is not authority over business cardinality.

Replace the spelling exemptions inside `check_unbounded_searches` (variable-name suffixes, a nearby `batch` comment, any `'in'` domain, the small-table name list used as a substitute for intent) with the intent table above. Do not add a second exemption list beside them. Do not edit `check_n_plus_one_queries`.

## Phase 3 — Implement smallest runtime fixes

Modify only findings proven unsafe.
Preserve business-complete queries unchanged.
Do not alter result semantics to obtain a green scan.

Apply current module version/upgrade obligations for runtime changes.

## Phase 4 — Behavioral proof

For each changed query prove:

- result cardinality semantics unchanged or deliberately corrected;
- no records are silently omitted;
- batch/pagination termination is deterministic where introduced;
- query count/volume improves for the intended path;
- replay/idempotency semantics are unaffected where relevant.

## Phase 5 — Scanner comparison

Compare:

- original Moderate set;
- post-classification true debt;
- repaired set;
- legitimate complete searches intentionally retained;
- UNKNOWNs.

A business-complete search that stays complete is retained, not open debt. If the scanner still flags it, teach `check_unbounded_searches` the intent class. Do not add `limit=1` and do not create a second exemption framework.

`UNKNOWN` blocks a CLOSED verdict. It does not authorize `limit=1`, truncation, or a new scanner.

## Phase 6 — Evidence and publication

Report every semantic class and every runtime modification. Publication uses only the verified current repo ceremony.

## Acceptance

PASS only if:

- genuine dangerous unbounded traversals are closed;
- no query is arbitrarily truncated;
- a business-complete search may remain, with its intent class recorded;
- spelling exemptions are replaced by the intent table inside `check_unbounded_searches`;
- `check_n_plus_one_queries` is unchanged;
- every survivor has an explained boundedness contract;
- `UNKNOWN` blocks a CLOSED verdict and does not authorize `limit=1`;
- High N+1 work is not reopened.
