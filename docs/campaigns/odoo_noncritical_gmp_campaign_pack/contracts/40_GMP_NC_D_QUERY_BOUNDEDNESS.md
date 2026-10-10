# GMP-NC-D — Query Boundedness Semantics

## Contract

**ID:** GMP-NC-D  
**Tier:** Runtime Performance / ORM Semantics  
**Objective:** Resolve genuine unsafe unbounded searches by query intent, not by mechanically adding limits.  
**Hard dependency:** consume the completed High performance-scanner hardening from the earlier production-debt campaign.  

## Entry gate

Before proceeding, prove one of:

1. prior High performance-scanner remediation has landed on current `Staging`; or
2. this branch stacks on the exact completed predecessor HEAD.

If neither is true: **BLOCKED**. Do not implement a second scanner architecture here.

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

If the scanner still flags a semantically correct complete query, repair the scanner only if that behavior is within the already-hardened performance scanner's architecture. Do not create a second exemption framework.

## Phase 6 — Evidence and publication

Report every semantic class and every runtime modification. Publication uses only the verified current repo ceremony.

## Acceptance

PASS only if:

- genuine dangerous unbounded traversals are closed;
- no query is arbitrarily truncated;
- every survivor has an explained boundedness contract;
- UNKNOWN is zero or explicitly blocks closure;
- High N+1 work is not reopened.
