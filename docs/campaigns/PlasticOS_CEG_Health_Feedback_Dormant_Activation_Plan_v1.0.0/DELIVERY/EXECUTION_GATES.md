# Bounded future execution sequence, not authorization

| Phase | Owner | Required output | Activation state |
|---|---|---|---|
| U00 read-only census | CEG/Gate/EIE source/runtime owners | Current deployed SHAs/SDK, tenant databases, effective flags, actual grants and scheduler/worker topology; source drift report | OFF |
| U01 contract/ADR alignment | Source owners | Adopted health action, read purity, budget/queue/durability and feedback-trigger contracts; reject unnecessary new infrastructure | OFF |
| U02 Gate canonical route | Gate | Unique `health-assess` ownership, static/dynamic registration, readiness tests and no action collision | OFF |
| U03 CEG health read/scan | CEG | Real tenant-correct Neo4j loader, read-only API, bounded scheduler OFF, correct missing-field evidence | OFF |
| U04 paid dispatch implementation | CEG | Explicit authorized worker/operation, hard cap, truthful result state, Gate SDK usage, durable retry | OFF |
| U05 feedback reliability | CEG+EIE | Authorized graph inference producer, durable return/ack, bounded wakeup, convergence, no recursion | OFF |
| U06 integration + hardening | All three + independent reviewer | Unit, negative, crash, multi-node, API/SDK/Neo4j E2E receipts at pinned revision | OFF; isolated fixture can simulate ON only under separate test permission |
| U07 review / isolated shadow | Release owner | Source audit, cost/liveness, staged test replay + kill-switch proof | OFF in live deployment |
| U08 readiness | Owner/independent reviewer | ALL scope findings disposed; `READY_BUT_DISABLED` receipt | OFF |
| Later separate production activation | Operator after this plan | Exact tenant/release/flags/budget/time window, fresh grant, rollback owner | Optional future ON; **not authorized by pack** |

**Concurrence:** Gate routing and CEG loader can be developed independently after U01; EIE durability may proceed independently of CEG scheduler, but frozen contract and source-owner admission are shared. No agent may modify the same path concurrently. No coordination with the deferred Offer Drafting campaign is required.

**No guessed commands:** A future implementer must verify the repo's current lint/test/CI/container commands at actual source. This plan does not grant permissions, publish PRs, or flip flags. An existing governed publication interface must be used only after explicit operator grant.

## Definition of done

A fully implemented, tested, source-owner-reviewed candidate that remains **disabled**. The set of action/tenant/provider controls is frozen and demonstrably safe to enable. The later ON flip is a separate operator-controlled release event, never an automatic consequence of green CI.
