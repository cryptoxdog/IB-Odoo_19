# Production Acceptance Matrix

The campaign is not closed until every applicable row is proven.

## A. Business semantics

| Requirement | Required result |
|---|---|
| PO delivery-term relationship remains M2M-driven | PASS |
| No `origin` semantic substitution in PO compute | PASS |
| Existing transaction profile matching predicates preserved | PASS |
| Load cardinality explicitly resolved | PASS |
| Facility one-profile-per-partner invariant preserved | PASS |
| Commission one-active-rule-per-rep invariant strengthened, not weakened | PASS |

## B. Relationship correctness

| Requirement | Required result |
|---|---|
| scoped transaction profile computation no longer performs per-record qualifying search | PASS |
| stored profile recomputation contract proven | PASS |
| PO compute performs set-based lookup | PASS |
| load create avoids per-load transaction query | PASS |
| load close avoids per-load transaction query | PASS |
| delivery override compute avoids per-load transaction query | PASS |
| inverse load/transaction relationship remains correct on reassignment | PASS |

## C. Uniqueness/concurrency

| Requirement | Required result |
|---|---|
| facility DB uniqueness remains authoritative | PASS |
| facility same-batch duplicates rejected | PASS |
| facility multi-write collisions rejected | PASS |
| commission DB uniqueness authority exists | PASS |
| commission same-batch duplicates rejected | PASS |
| commission activation/reassignment collisions rejected | PASS |
| concurrent commission writers cannot persist duplicate active rules | PASS |

## D. Security scanner

| Requirement | Required result |
|---|---|
| static `api_key` prose false positive | 0 |
| dynamic `api_key` value logging detected | PASS |
| f-string secret interpolation detected | PASS |
| format-argument secret interpolation detected | PASS |
| original two migration log lines changed | NO |

## E. Performance scanner

| Requirement | Required result |
|---|---|
| `self.search` inside loop detected | PASS |
| alias `.search` inside loop detected | PASS |
| `self.env[..].search` inside loop detected | PASS |
| `browse()` alone reported as N+1 query | NO |
| batch search outside loop reported | NO |

## F. Release realization

| Requirement | Required result |
|---|---|
| every changed runtime addon version advanced | PASS |
| unaffected addon versions left unchanged | PASS |
| new migration version used where schema application requires it | PASS |
| migration/data census performed before new uniqueness constraint | PASS |
| installed runtime reflects new addon versions | PASS |

## G. Baseline

| Requirement | Required result |
|---|---|
| repaired scoped fingerprints removed | PASS |
| new suppressions for repaired paths | 0 |
| unrelated newly discovered findings silently absorbed | 0 |

## H. General quality

| Requirement | Required result |
|---|---|
| no new business fields | PASS |
| no unrelated ERP/import changes | PASS |
| no filename/line scanner special cases | PASS |
| current repo-native validation passes | PASS |
| exact publication surface verified before publication | PASS |

## Closure verdict

Only two terminal verdicts are legal:

- `PRODUCTION-DEBT-SCOPE CLOSED`
- `BLOCKED` with the exact unresolved invariant/evidence gap

Do not label partial completion as closed.
