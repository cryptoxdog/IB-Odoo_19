# Operator executive brief

**Decision:** Keep #2 disabled. Complete the missing wiring and prove real end-to-end health improvement before enabling any deployed PlasticOS flags.

## Why the code is not ready

1. **Action ownership drift:** CEG advertises `health-assess`; Gate canonical ownership and static registry omit it, so feature readiness is incomplete.
2. **No autonomous scanner:** nightly scan only processes an injected callback; without an entity loader it returns zero candidates. CEG boot starts GDS/compliance tasks, not the nightly health scan.
3. **No scheduled dispatch:** nightly scan calculates and returns a queue; it does not call the Gate EIE enrichment trigger. The batch-assess HTTP path reports `dispatched=0`.
4. **Paid read-side effect:** current `health_assess` can call `trigger_reenrichment_v2` when a flag is ON. Make assessment read-only and reserve spending for an authorized background dispatcher.
5. **Feedback only partially closed:** CEG `emit_inference_feedback` is behind a non-Gate-advertised admin subaction. EIE accepts graph targets into a process-local queue and consumes them only at the start of a future convergence pass. A successful queue response is not proof of durable convergence or improved graph readiness.
6. **Economic assumptions:** priority ROI estimates assume every critical gap can be filled and derive deal value from description or a $1,000 fallback. Existing $10 batch estimate limit and $50 nightly estimate limit are not real paid-provider controls.

## The smallest good path

- U00: census exact deployment/SDK/tenant/Neo4j and callback topology read-only.
- U01: accept the ownership and safety ADR deltas, preserving code defaults OFF.
- U02: reconcile Gate's `health-assess` ownership, route, static registry and readiness tests.
- U03: implement bounded real entity loader/scheduler and **read-only** assessment.
- U04: connect eligible health work to a durable, budget-controlled Gate→EIE dispatch.
- U05: make CEG feedback production-triggerable and EIE receipt/consumption durable, with no recursive enrichment storms.
- U06: prove full integration and negative/restart/cross-tenant tests in isolated staging.
- U07: source-owner review and **READY BUT DISABLED** verdict. Production enabling is a later, separate explicit decision, not a step performed by this pack.

## Scope protections

No Odoo module changes, no PR #329 edits, no Offer Drafting, no Semantic Kernel, no local intelligence fallback and no new autonomous commercial behavior. Reuse Gate SDK, existing result/evidence stores and engine lifecycle where actually sufficient. No new service or repo by default.

## Verification status

This ZIP verifies **declared planning structure only**. Actual tests of CEG/Gate/EIE, real Neo4j, durable worker queue and future deployment are NOT_RUN. External architecture admission and coding authorization are NOT_GRANTED.
