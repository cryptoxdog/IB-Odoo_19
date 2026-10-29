# Planned verification and rollback

All cases are NOT_RUN. No source code was implemented or runtime tests executed in preparing the package.

| Proof | Stage | Positive witness | Negative witness |
| --- | --- | --- | --- |
| P01 | PRECODE | Exact deployed image/SDK, effective route/caller grants and tenant/Neo4j DB are inventoried against pinned refs. | Mismatch, missing authority, stale pack or unknown dynamic consumer remains explicitly blocked. |
| P02 | POSTCODE | health-assess has unique CEG owner, static and dynamic registration, and ready routing. | Cross-owner collision or unhealthy/missing CEG fails readiness and routes nowhere else. |
| P03 | POSTCODE | health-assess supports exactly assess/batch/report and remains read-only under all flags. | No admin subaction exposed, no paid Gate request from read-only health call. |
| P04 | POSTCODE | Neo4j loader retrieves due health entities from exact tenant database with stable pagination. | No-loader is classified unavailable, never a successful zero; cross-tenant reads rejected. |
| P05 | POSTCODE | Scheduled health job runs only in explicitly authorized test context, chooses stable deduped entities and cancels cleanly. | Restart or multiple workers do not double-schedule, scan disabled tenant or run after kill-switch. |
| P06 | POSTCODE | Healthy/missing-field cases produce correct readiness, prioritized target fields and traceable evidence. | Bad entity label, unknown field, nonexistent spec or poisoned provenance cannot become accepted target. |
| P07 | POSTCODE | One run obeys per-tenant max entities, actual paid spend/calls/token ceilings, scope and audit. | Heuristic ROI, $50 nightly estimate or request-specified ceilings cannot raise server budget. |
| P08 | POSTCODE | Durable operation identity survives restart with source revision and field-set digest; worker sends once. | Concurrent workers, clock/retry/mapping changes or reorders cannot multiply paid requests. |
| P09 | POSTCODE | CEG uses Gate SDK enrich, receiving typed worker ack with correct entity and tenant. | Gate absent, bad signature, HTTP200 failure packet, wrong action/tenant not recorded success. |
| P10 | POSTCODE | EIE persists accepted feedback targets in recoverable owner and reports durable accepted versus rejected counts. | Full process queue, restart, wrong process or duplicate packet cannot claim successfully consumed work. |
| P11 | POSTCODE | Authorized converge pass consumes tenant+entity graph target exactly once with provenance. | Graph suggestion cannot overwrite stronger verified facts or cross another entity/tenant. |
| P12 | POSTCODE | Graph-derived inference producer is triggered by authorized real event not via unavailable admin action, with rule whitelist and floor. | Unchanged evidence, unauthorized rule, low-confidence or cyclic graph-derived result does not cause new paid feedback. |
| P13 | POSTCODE | Graph feedback traverses CEG→Gate graph-inference-result→EIE, stores and acknowledges exact outputs. | Unknown action, queue full, worker failure, wrong tenant or partial acceptance remains retryable/not completed. |
| P14 | POSTCODE | EIE enrichment persists evidence and receives CEG graph-sync acknowledgement; CEG reassessment uses updated revision. | Transport accept or queued target alone does not count as refreshed graph health. |
| P15 | PREMERGE | No direct peer ingress, no privilege escalation, no payload tenant override, safe source allowlists and no secrets. | Adversarial tenant mismatch, missing production allowlist, forged headers and forbidden fields fail closed. |
| P16 | PREMERGE | All edited current tests, ownership/ADR/readiness registries and lifecycle paths pass at exact source heads. | One test suite passing from a detached source, mock-only integration, or suppressed failure is insufficient. |
| P17 | PRERELEASE | Real Gate+CEG+EIE+Neo4j fixture proves scored deficiency→dispatch→EIE result→graph update→health improvement. | An empty queue, just an HTTP200, or one node fake cannot produce a green end-to-end receipt. |
| P18 | PRERELEASE | All three flags OFF in actual deployment until separate approval; ON tested only in authorized isolated fixture. | No flag flip, paid send, scheduled job or deployment implied by published code or plan. |
| P19 | PRERELEASE | Kill switches stop new queued/cached/retried sends and preserve evidence; rollback/restore exercised. | Previously queued retry cannot dispatch after disabled, and disabling does not delete evidence. |
| P20 | PRERELEASE | Exact final candidate revisions, real action registration, data/tenant boundaries, budgets and unresolved findings closed. | Any missing approval, unknown result, cost runaway, feedback recursion or source drift prevents activation. |
| P21 | PREMERGE | No edits to Odoo, Offer Drafting, PR #329 or Semantic Kernel; unrelated feature gates remain off. | A new Odoo selector cron, inferred inventory, health commercial tier or direct peer transport is regression. |

## Isolated end-to-end recipe (future, after authorization)

1. Launch exact pinned Gate+CEG+EIE nodes and disposable tenant Neo4j database with approved fixtures, no real paid provider calls except separately authorized bounded test.
2. Keep actual deployed flags OFF; verify health route produces disabled response and zero provider requests/cron dispatch.
3. With explicit isolated-test-only grants, enable read-only health assessment and verify missing fields without spending. Confirm wrong-tenant refusal.
4. Admit one due entity under an exact per-tenant cost cap, connect Gate EIE worker; verify signed packet and durable EIE result/graph acknowledgment.
5. Introduce graph inference with valid provenance. Test feedback received, persisted and consumed on next authorized convergence. Simulate worker restart and queue overflow; verify no silent success.
6. Re-assess health; compare field coverage and match-readiness before/after. Exercise fully healthy entity, unsuitable field, ROI heuristic under uncertainty and missing provider.
7. Repeated/reordered/parallel runs must not cause duplicate calls, permission bypass, degraded source precedence or infinite feedback.
8. Toggle effective kill switches OFF; verify pending jobs do not dispatch, evidence remains and normal independent match/sync still works.

## Recovery

The release and operator must document a specific pause/restore flow with exact code revisions, queue lease and pending outcome reconciliation. Unknown external completion cannot be retried blindly. Disabling the flags prevents new sends and must cancel/suspend scheduled work on every worker; it must not erase graph/data provenance or reset tenant allowlists. If EIE return targets are not durable, runtime must remain disabled until safety is demonstrated.
