# Source-bound owner and whole-change accounting

All source updates below are **PROPOSED**. `EDIT` is not permission to execute. Every planned edit requires live-source revision rebind, source owner agreement, test, rollback and no change to excluded domains.

### C01: CEG / `engine/config/settings.py` [NO_CHANGE]

**Before:** Three enable switches default false, plus unrelated safety switches.

**After:** Preserve defaults false, separate readiness flags from activation; no live config change.

Planned files: NONE: no-change justified. Proofs: P18, P19, P21. Source blob: `119c8a16cfd436bd49e2b064bfba97defe0de3fb`.

**Disposition basis:** Settings defaults are a safety invariant; proof of effective future config belongs to release operator.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### C02: CEG / `engine/spec.yaml` [NO_CHANGE]

**Before:** Canonical health-assess already advertised.

**After:** Preserve existing advertisement; Gate registry must align, no admin or enrich added.

Planned files: NONE: no-change justified. Proofs: P02, P03. Source blob: `b1aeedd9c67917d3c4e6cc8dfad4d6013bd985c6`.

**Disposition basis:** Spec already correct at pinned revision; no CEG-side need to rename action.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### C03: CEG / `engine/handlers.py` [EDIT]

**Before:** Graph-inference producer callable only via admin emit_inference_feedback; health route limited to three.

**After:** Keep health route limited; wire feedback producer to existing authorized internal graph/rule event; remove unsafe payload-driven domain switching, add recursion and producer receipts.

Planned files: engine/handlers.py. Proofs: P03, P12, P13. Source blob: `9d05bc24b13bf2ffa22955d20e6714c02acda8d4`.

**Disposition basis:** Owner-restricted edit only after evidence frontier closure.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### C04: CEG / `engine/health/api.py` [EDIT]

**Before:** Assessor currently auto-dispatches enrich_now if allowed; batch scans caller input, dispatched=0.

**After:** Separate strictly read-only assess/batch/report from paid worker actions. Replace automatic read-side side effect with eligibility only; keep server-owned caps.

Planned files: engine/health/api.py. Proofs: P03, P06, P07. Source blob: `b11f76e18b7930cb5aeb9e9c9c1982b0a8a55812`.

**Disposition basis:** Owner-restricted edit only after evidence frontier closure.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### C05: CEG / `engine/health/nightly_health_scan.py` [EDIT]

**Before:** No production entity_loader returns []; top100 estimated queue only; global scanned set.

**After:** Reuse GraphDriver tenant DB to obtain real candidates; stable paging/watermarks, stateful due selection, truthful zero/unavailable, queue output only with bounded policies.

Planned files: engine/health/nightly_health_scan.py. Proofs: P04, P05, P06, P07. Source blob: `b0658bc2966b8ab7ea190260f8ae9c4246d462bf`.

**Disposition basis:** Owner-restricted edit only after evidence frontier closure.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### C06: CEG / `engine/health/enrichment_trigger.py` [EDIT]

**Before:** ROI derived from assumed projected match probability and default deal value; request_enrichment returns Gate dispatch status.

**After:** Keep ranking advisory; require explicit approved tenant budget and durable dispatch check; no hypothetical ROI used as spending authority; preserve one Gate egress.

Planned files: engine/health/enrichment_trigger.py. Proofs: P07, P08, P09. Source blob: `95c70a4c9d2a6f2c5000e5dea79c607c17c335f0`.

**Disposition basis:** Owner-restricted edit only after evidence frontier closure.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### C07: CEG / `engine/boot.py` [EDIT]

**Before:** Lifecycle schedules GDS jobs and compliance only; no health job.

**After:** Wire existing approved lifecycle/scheduler to a scoped health worker with startup/shutdown single scheduler and OFF effective gate; reuse existing lifecycle, no new service by default.

Planned files: engine/boot.py. Proofs: P05, P18, P19. Source blob: `3629cae40ff4e498d1b2b3c10674075e483c912e`.

**Disposition basis:** Owner-restricted edit only after evidence frontier closure.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### C08: CEG / `engine/gate_egress.py` [NO_CHANGE]

**Before:** Gate-only SDK egress, fixed enrich keys without explicit input revision.

**After:** Preserve SDK transport; before coding confirm idempotency key sufficiency and acknowledgement semantics. If revision-awareness cannot be enforced at workflow owner, open narrow amendment here, never direct HTTP.

Planned files: NONE: no-change justified. Proofs: P08, P09, P13. Source blob: `2b96ff343bd566cf2de449277a3f35665bdeec4d`.

**Disposition basis:** Existing SDK is an adequate transport owner; its semantic retry identity needs independent proof, not speculative refactor.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### C09: CEG / `tests/unit/test_health_api.py` [EDIT]

**Before:** Current tests assert automatic trigger from read-path and mock analysis.

**After:** Revise for side-effect-free health read, budget authority, real candidate integration and disabled gates; never weaken tenant/gate assertions.

Planned files: tests/unit/test_health_api.py, tests/unit/test_health_engine.py, tests/architecture/test_seam_gate_only.py. Proofs: P03, P06, P16, P21. Source blob: `276310bf94df04884cb9dc9f0ed78470b182526a`.

**Disposition basis:** Owner-restricted edit only after evidence frontier closure.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### C10: CEG / `docs/FEATURE_GATES.md` [EDIT]

**Before:** Docs report 3 dormant flags and separate commercial setting.

**After:** Update expected proven readiness and staged enabling process without setting flags or falsely claiming live.

Planned files: docs/FEATURE_GATES.md. Proofs: P18, P19, P21. Source blob: `ccc877ec77ff9fc3fa09cf641937d3a1bfa9e5fc`.

**Disposition basis:** Owner-restricted edit only after evidence frontier closure.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### C11: CEG / `engine/health/health_schemas.py` [NO_CHANGE]

**Before:** HealthScanProfile and batch caps exist; no observed proven deficiency in exact schema.

**After:** Reuse current typed profiles; amend schema only after an exact failed required contract test.

Planned files: NONE: no-change justified. Proofs: P04, P07. Source blob: `NOT OBSERVED`.

**Disposition basis:** Preserve existing typed schemas and avoid speculative fields.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### C12: CEG / `engine/graph/driver.py` [NO_CHANGE]

**Before:** GraphDriver has explicit tenant database handling; not used by current scanner default.

**After:** Use GraphDriver; do not invent new Neo4j client or tenant fallback.

Planned files: NONE: no-change justified. Proofs: P04, P15. Source blob: `NOT OBSERVED`.

**Disposition basis:** GraphDriver is existing source owner; no code change demonstrated necessary yet.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### C13: CEG / `engine/inference_rule_registry.py` [NO_CHANGE]

**Before:** Authorized graph rule registry is consumed from admin path.

**After:** Reuse authorized rules; no generic rule engine or autonomous rule expansion.

Planned files: NONE: no-change justified. Proofs: P12, P21. Source blob: `NOT OBSERVED`.

**Disposition basis:** Existing rule registry supplies validated rule authorization; activation should wire it, not fork it.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### G01: GATE / `constellation-gate/src/constellation_gate/routing/action_ownership.py` [EDIT]

**Before:** Canonical owners and SEAM_ACTIONS lack health-assess.

**After:** Admit `health-assess:ceg`, preserve enrich/graph-inference-result:EIE; extend seam/readiness contract and deny collisions.

Planned files: constellation-gate/src/constellation_gate/routing/action_ownership.py. Proofs: P02, P09, P16. Source blob: `c4099451db191d34937d168f138e97afa9ce5e5c`.

**Disposition basis:** Owner-restricted edit only after evidence frontier closure.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### G02: GATE / `constellation-gate/src/constellation_gate/config/node_registry.yaml` [EDIT]

**Before:** Static seed graph node has no health-assess.

**After:** Align static graph action with CEG spec and owner, preserve unrelated EIE routes.

Planned files: constellation-gate/src/constellation_gate/config/node_registry.yaml. Proofs: P02, P15. Source blob: `823c5dfde515b5b15fef374d8b7aebb7f03b20fc`.

**Disposition basis:** Owner-restricted edit only after evidence frontier closure.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### G03: GATE / `constellation-gate/tests/architecture/test_seam_route_contract.py` [EDIT]

**Before:** Architecture route tests freeze old action set and default readiness semantics.

**After:** Extend exact owner, static/dynamic registry, readiness, wrong-owner and collision tests; keep worker retry ownership enforced.

Planned files: constellation-gate/tests/architecture/test_seam_route_contract.py, constellation-gate/tests/runtime/test_routing_readiness.py. Proofs: P02, P15, P16. Source blob: `6925fa1252b25c69d2e8dc3b8ffc84efc9dee172`.

**Disposition basis:** Owner-restricted edit only after evidence frontier closure.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### G04: GATE / `constellation-gate/src/constellation_gate/runtime/routing_readiness.py` [NO_CHANGE]

**Before:** Default readiness uses SEAM_ACTIONS owned in action_ownership.

**After:** Existing readiness aggregation suffices after SEAM_ACTIONS update; test no silent liveness-only green.

Planned files: NONE: no-change justified. Proofs: P02, P16. Source blob: `abaaaee77e52b7b7421145098940b11e9a637464`.

**Disposition basis:** Do not edit generic readiness if new required action inherits correctly from single SEAM_ACTIONS owner.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### G05: GATE / `constellation-gate/src/constellation_gate/resilience/replay_safety.py` [NO_CHANGE]

**Before:** Gate whole-operation replay defaults disabled.

**After:** Do not enable generic Gate replay for paid enrichment; domain worker owns safe retry.

Planned files: NONE: no-change justified. Proofs: P08, P09. Source blob: `b3a2942bfd29dcac406e6738a49cc7e4d35bcf10`.

**Disposition basis:** Transport timeout may conceal completed provider work; Gate retries remain denied.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### E01: EIE / `app/services/graph_return_channel.py` [EDIT]

**Before:** Per-process in-memory per-tenant queue; QueueFull drops; accepted response is not durable.

**After:** Reuse existing durable result/inbox where sufficient; otherwise owner-approved minimal durable target state, honest full/partial counts, dedupe, restart and multi-worker recovery. No silent successful discard.

Planned files: app/services/graph_return_channel.py. Proofs: P10, P11, P13. Source blob: `76679b7b18ea6d2391960b2cb60e4f7a936569cf`.

**Disposition basis:** Owner-restricted edit only after evidence frontier closure.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### E02: EIE / `app/engines/convergence_controller.py` [EDIT]

**Before:** GraphReturnChannel targets consumed only when some later authorized converge pass happens.

**After:** Connect admitted return targets to a bounded authorized convergence trigger or pending-state wakeup; preserve seed confidence and stronger source facts; no self-amplifying feedback loop.

Planned files: app/engines/convergence_controller.py. Proofs: P11, P14. Source blob: `d84b3db458011e17ed4af8b5e31db4e7134b699d`.

**Disposition basis:** Owner-restricted edit only after evidence frontier closure.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### E03: EIE / `app/services/chassis_handlers.py` [NO_CHANGE]

**Before:** Existing handler registers graph-inference-result via SDK.

**After:** Retain EIE canonical handler ownership and tenant identity from packet; no duplicate endpoint.

Planned files: NONE: no-change justified. Proofs: P10, P13. Source blob: `31009b26a44c2089def388723e993bfd571d50cf`.

**Disposition basis:** Existing registered action/handler are correct at observed source; no demonstrated change needed.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### E04: EIE / `app/services/side_effect_coordinator.py` [NO_CHANGE]

**Before:** Has process-local dedupe and graph sync acknowledgement checks.

**After:** Reuse result/graph-sync owners; a source restart probe may demonstrate separate durable inbox requirement; no speculative rewrite.

Planned files: NONE: no-change justified. Proofs: P10, P14. Source blob: `28e861bdfb8e3a539cd11b814e30e70140c3f791`.

**Disposition basis:** Separate EIE graph sync pipeline already owns durable result/evidence work, but graph-feedback queue durability unproven.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### E05: EIE / `tests/services/test_graph_return_channel.py` [EDIT]

**Before:** Tests cover singleton/tenant separation and receive, not crash/full/multiprocess/replayed-target semantics.

**After:** Add restart/dedup/reject-ack and source-confidence negative tests; ensure real delivery into next authorized converge pass.

Planned files: tests/services/test_graph_return_channel.py. Proofs: P10, P11, P16. Source blob: `13c9ecef819cf13b3251bab25d6947a082303967`.

**Disposition basis:** Owner-restricted edit only after evidence frontier closure.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

### E06: EIE / `docs/contracts/dependencies/constellation-gate.yaml` [EDIT]

**Before:** Current contract says graph return channel seeds convergence and sync ack must be exact; no durable target promise.

**After:** Update exact accepted durable target ack and bounded re-trigger semantics; preserve Gate-only producer and graph sync acknowledgement.

Planned files: docs/contracts/dependencies/constellation-gate.yaml. Proofs: P10, P11, P14. Source blob: `ce1b5d30e461b9cde2a6719a382d98fb106a1a9a`.

**Disposition basis:** Owner-restricted edit only after evidence frontier closure.

**Migration/recovery:** Only versioned additive config/state/schema where necessary; do not change historical packets or tenant IDs. Retain evidence; disable scoped operation; reconcile unacknowledged requests and restore prior release after verifying snapshot.

## Dynamic/transitive consumers not proven absent

Gate registration, EIE replica topology, CEG multiworker scheduler, current engine and Neo4j schema, feature deployments and paid-provider authorizations were not observed. Source search is bounded. Frontiers F01-F09 must be dispositioned before precode or release.

## File addition policy

No new service, repository, event bus, DB or framework is approved by this plan. New tests, leader-state or durable inbox files may become necessary only after source-owner proof that current owners cannot satisfy the obligation; admit them to the change ledger before coding. Pending that decision, all planned paths are existing-source edits or no-changes.
