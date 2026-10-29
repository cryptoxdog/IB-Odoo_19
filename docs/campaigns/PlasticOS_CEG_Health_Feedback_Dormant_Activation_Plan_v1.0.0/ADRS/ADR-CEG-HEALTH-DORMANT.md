# Proposed CEG ADR: health enrichment scheduler and strict assessment purity

**Status: PROPOSED. Owner: Quantum-L9/Cognitive.Engine.Graphs.** Never claimed accepted.

## Context

The repo contains health analysis, priority and EIE Gate egress, but nightly scan has no default entity loader or scheduled dispatcher, and a health assessment can cause paid side effects if flags are enabled. Cost estimates and projected match value are heuristic; graph-inference feedback is admin-only. Production enables remain OFF.

## Proposed decision

1. `health-assess` (including batch/report) is read-only and never spends EIE budget; it must not route through generic `admin`.
2. CEG GraphDriver reads only its signed packet tenant's Neo4j/domain DB. Real due-entity loader and approved lifecycle scheduler use one coordinated owner/leader; classify missing loader as unavailable.
3. Health ranking remains advisory. Automatic paid dispatch is a distinct server-internal operation with an explicit tenant, field, time, budget and data-version gate; reuse existing scheduler/journal if sufficient. No default-on behavior.
4. GateSDK is the only EIE egress. `enrich` remains EIE-owned; retries belong to source/domain worker, not generic Gate replay.
5. Graph-derived inference feedback is produced from a valid source-versioned event, not from a Gate-reachable admin shortcut. Confidence, contradictory evidence and recursion/duplication are bounded.
6. A result is complete only after EIE durable outcome, CEG graph acknowledgement and attributable current health re-assessment. Transport and queue receipt are separate states.
7. Keep code defaults False. No deployment OFF->ON until operator-granted action, tenant, release and cost bounds after isolated integration proof. Health commercial tiers and unrelated gates stay OFF.

## Consequences

New checks for read purity, scheduler lifecycle, budget expenditure, tenant isolation, queue durability, graph target identity and feedback loops. Potential existing unit tests expecting read-triggered enrichment must be changed to reject side effects rather than weakened. No Odoo changes or additional service by default.

## Supersession / compatibility

Amend `docs/FEATURE_GATES.md` sections for Health API, Graph Inference Feedback and paid Gate auto enrich, plus narrow CEG contracts if evidence shows input revisions required. Do not rename the canonical health-assess route or turn on dormant domain packs.

## Acceptance

P01-P09, P12, P14-P21. Until all proof is accepted, repository work may be coded in separately granted scope but deployment must stay disabled.
