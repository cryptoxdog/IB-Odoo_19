# Architecture Decisions and Guardrails

## AD-1 — Preserve business predicates before optimizing execution

A performance repair may change **how** records are found, not **which records semantically qualify**.

Examples:

- PO delivery term remains governed by `transaction.purchase_order_ids` membership.
- material profile computations retain their existing matching predicates.
- load transaction selection cannot be changed until cardinality is proven.

## AD-2 — Existing relations outrank reverse searches only when they are authoritative

An existing Many2one/One2many path is preferred over repeated reverse search when all of the following are proven:

1. it represents the same business relationship;
2. its cardinality matches the intended relationship;
3. its stored/recompute behavior is correct;
4. it is current under all relevant write paths.

Presence of a field alone is not proof.

## AD-3 — Database owns uniqueness, Python owns friendly UX

For uniqueness invariants:

```text
DB constraint = final authority
Python precheck = friendly early error
```

The Python layer must never be the only concurrency protection.

## AD-4 — Batch-aware means operation-aware

A correct precheck must reason about the **whole requested final state**, not each row independently.

It must detect:

- conflicts against persisted rows;
- conflicts between records in the same batch;
- conflicts created by multi-record write.

## AD-5 — Stored computes must expose real dependencies

A stored computed field that depends on a hidden `search()` can become stale.

Prefer declared relational dependencies and prefetch when the relation models the actual concept.

If arbitrary search semantics must remain, add explicit recomputation behavior at the authoritative mutation owner rather than relying on undocumented cache luck.

## AD-6 — Scanner correctness must be generic

No scanner change may special-case:

- a filename;
- a line number;
- `perplexity_api_key` specifically;
- any one of the eight existing findings.

The scanner rule must generalize to the semantic pattern.

## AD-7 — New scanner findings do not expand current scope

Improved detectors may reveal previously hidden debt. Report it separately.

Do not:

- absorb it into the same PR by default;
- add suppressions automatically;
- weaken the detector to preserve the old count.

## AD-8 — Runtime changes require addon version propagation

Any changed runtime addon must advance its manifest version according to repo-native law.

Only affected modules are upgraded. Do not perform broad all-module reloads as a convenience.

## AD-9 — No new business fields for this campaign

The current model surfaces are sufficient to implement the scoped repair unless execution proves a contradiction. If a new field appears necessary, STOP and report the contradiction rather than adding it opportunistically.

## AD-10 — Publication is a verified execution surface

At execution time inspect the exact current publication tooling.

The operator intends `make pr` to be the sole publication ceremony, but the historical `Staging` state observed during this architecture campaign implemented `make pr` only as a fast local gate.

Therefore:

- if `make pr` has since been repaired to actual publication semantics, use it exactly once for publication;
- if not, STOP and report publication as blocked;
- do not substitute another publication path.
