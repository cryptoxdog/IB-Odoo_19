# Source and evidence notes

The current four repository heads were resolved on 2026-10-29 and match the same immutable revisions read earlier in this conversation. Full file reads from those unchanged revisions are reused; search-only/identified surfaces are explicitly weaker evidence. No live database, deployed worker, SDK pin or Enterprise registry was inspected.

## S01: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:docs/adr/ADR-122-supply-demand-models.md](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/docs/adr/ADR-122-supply-demand-models.md)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Accepted TASK-024 adds supply/demand persistence. Matching remains Gate/CEG authority; no ambiguous automatic conversion.

## S02: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:docs/adr/ADR-124-semantic-kernel-backfill.md](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/docs/adr/ADR-124-semantic-kernel-backfill.md)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Accepted TASK-026/TASK-031 explicitly blocks supply/demand backfill; only specification wave eligible.

## S03: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:docs/adr/ADR-125-split-opportunity-protocol.md](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/docs/adr/ADR-125-split-opportunity-protocol.md)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Supply and demand are peer protocols, not a combined discriminator payload.

## S04: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:docs/adr/ADR-126-odoo-semantic-gate-mappers.md](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/docs/adr/ADR-126-odoo-semantic-gate-mappers.md)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Existing semantic payload mapper and two directions, without demonstrated runtime dispatch.

## S05: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:docs/adr/ADR-127-field-family-cutover.md](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/docs/adr/ADR-127-field-family-cutover.md)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Specification-only dual-gated field authority; supply/demand blocked independently of backfill.

## S06: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:scripts/semantic_kernel_backfill.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/scripts/semantic_kernel_backfill.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

CLI consumes fixture rows, forces dry-run, writes reports; no real Odoo reader/writer adapter.

## S07: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:scripts/semantic_kernel_backfill_engine.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/scripts/semantic_kernel_backfill_engine.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

BLOCKED_AUTOMATIC contains supply/demand. Non-dry branch mutates an in-memory identity set and reports created, not database persistence. Conflict detection is fixture-oriented.

## S08: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_gate/services/field_family_cutover.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_gate/services/field_family_cutover.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; blob `625f4ae2e070966de54402e9fcbaab63888bed30`.

Dual flags default off, specification-only policy. Predicate call search returned its definition and tests, not a demonstrated runtime guard consumer.

## S09: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_semantic_kernel/__manifest__.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_semantic_kernel/__manifest__.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; blob `b990bfd16431e6cf711b21c418d288cdb5ba197f`.

Optional, installable, auto_install false; six models and ordinary forms/security loaded; no native CRM or Gate integration dependency.

## S10: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_semantic_kernel/models/supply_opportunity.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_semantic_kernel/models/supply_opportunity.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; blob `b338c85a664ba0047ca270cd0432653610ed865e`.

Material profile and supplier partner required; no typed native CRM opportunity link; state, quantity, availability, commercial readiness, UUID; no integration execution.

## S11: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_semantic_kernel/models/buyer_demand.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_semantic_kernel/models/buyer_demand.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; blob `a2db72ae03d7c5c542d1c1001ed7c269a53d3ad5`.

Confirmed-requirement-shaped record; buyer partner and material specification required; quantity-state and need window; no evidence admission workflow.

## S12: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_semantic_kernel/models/material_specification.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_semantic_kernel/models/material_specification.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; blob `2c3929b59ecb2bab0a47795b94f51b31802dc917`.

Versioned normative material specification; UUID immutable, other business fields not generally immutable.

## S13: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_semantic_kernel/models/material_observation.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_semantic_kernel/models/material_observation.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; blob `f2083519224c9de34984fbc7c8f02195fed4b4d8`.

Attributed observed/reported/inferred/unknown/stale/conflicting values, provenance, expiry and supersession fields. UUID immutability alone does not freeze observation content.

## S14: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_semantic_kernel/models/facility_material_rule.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_semantic_kernel/models/facility_material_rule.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; blob `6a32931a5be0ff7c920c42bdbc5286c21d371087`.

Accept/reject/prefer/require rules; inferred/documented/operator-confirmed states, confidence and source. Storage only.

## S15: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_semantic_kernel/models/capacity_observation.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_semantic_kernel/models/capacity_observation.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; blob `64a40d2d1877482f617a71511345451894b6cc67`.

Installed/throughput/available/committed/reserved/estimated capacity categories; unit, period, provenance and expiry. Capacity is not buying intent.

## S16: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_semantic_kernel/security/ir.model.access.csv](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_semantic_kernel/security/ir.model.access.csv)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Internal users currently get broad create/write; administrators unlink. UI read-only alone cannot enforce projection ownership.

## S17: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_semantic_kernel/views/menus.xml](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_semantic_kernel/views/menus.xml)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Independent Supply Opportunities and Buyer Demand menus exist if optional addon installed.

## S18: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_gate/services/semantic_payloads.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_gate/services/semantic_payloads.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; blob `be1ed55d0700b2b125a911599af2dd0064a68782`.

Supply mapping requires specification/window beyond ORM requirements; defaults revision to 1; supplies empty evidence lists; wrapper emits direction and nested facts.

## S19: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_gate/services/gate_contracts.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_gate/services/gate_contracts.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Active MatchRequest uses match_direction plus query/top_n; distinct from detached semantic wrapper shape.

## S20: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_gate/services/gate_builders.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_gate/services/gate_builders.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Active matching builder is intake/supplier based and maps snapshot fields; cannot infer opportunity ownership from a name.

## S21: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_matching/models/match_orchestrator.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_matching/models/match_orchestrator.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Gate-only active orchestration requires intake partner and material profile; durable run receipts; result persistence writes two review representations.

## S22: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_matching/models/match_run.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_matching/models/match_run.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Run schema requires supplier partner and intake; receipts protected; current status not proof of end-to-end result identity.

## S23: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_crm_bridge/models/material_profile.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_crm_bridge/models/material_profile.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Inherited partner_id is optional with a lead-owned facility owner. Reuse existing provisional profile logic; do not create a replacement system.

## S24: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_crm_bridge/models/facility_profile.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_crm_bridge/models/facility_profile.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Lead-owned facility identity and verified-location reconciliation; generic registry scan retargets material foreign keys, including optional supply records.

## S25: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_crm_sync/tests/test_orchestrator_upsert.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_crm_sync/tests/test_orchestrator_upsert.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Optional non-standard semantic-kernel collision tests preserve supply/material relationships. Standard test success does not exercise this lane.

## S26: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:config/odoo_module_order.yaml](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/config/odoo_module_order.yaml)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Semantic kernel explicitly excluded from default install/smoke, optional and outside Staging critical path.

## S27: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_offer/models/offer.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_offer/models/offer.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Supplier partner required; action_send only changes state. Offer/email execution belongs to separate web/CRM campaign, not this kernel.

## S28: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:plasticos_intake/models/intake.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_intake/models/intake.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Legacy Make PO creates transaction and marks intake won without confirmed purchase.order proof. Reuse successor lifecycle contract, not this false event.

## S29: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:docs/adr/ADR-003-single-external-intelligence-authority.md](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/docs/adr/ADR-003-single-external-intelligence-authority.md)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Gate-only egress. CEG match/scoring, EIE enrichment/inference, Odoo business persistence. No local fallback.

## S30: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:INVARIANTS.md](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/INVARIANTS.md)

Revision `677d734fd88615d673501d91de88734b7150ff50`; blob `c16e99c575a262ff6279f2202e5959f777b2fc6f`.

v2.2.0 is active constitution; 19 numbered rules plus BAN001. Draft POS candidates not admitted.

## S31: OBSERVED_REPOSITORY
[Quantum-L9/Enrichment.Inference.Engine:domains/plasticos/spec.yaml](https://github.com/Quantum-L9/Enrichment.Inference.Engine/blob/3f96eda98240789963b0e6534aa2151aed12658e/domains/plasticos/spec.yaml)

Revision `3f96eda98240789963b0e6534aa2151aed12658e`; independent blob checksum not captured in this source record.

Evidence/inference-only domain; current grading/tier rules and sync target declarations; not a proven product/process-to-scrap application.

## S32: OBSERVED_REPOSITORY
[Quantum-L9/Enrichment.Inference.Engine:app/engines/inference/rule_loader.py](https://github.com/Quantum-L9/Enrichment.Inference.Engine/blob/3f96eda98240789963b0e6534aa2151aed12658e/app/engines/inference/rule_loader.py)

Revision `3f96eda98240789963b0e6534aa2151aed12658e`; independent blob checksum not captured in this source record.

Typed rule conditions/outputs, rule version and strict parser; reuse rather than a local Odoo engine.

## S33: OBSERVED_REPOSITORY
[Quantum-L9/Enrichment.Inference.Engine:app/engines/packet_router.py](https://github.com/Quantum-L9/Enrichment.Inference.Engine/blob/3f96eda98240789963b0e6534aa2151aed12658e/app/engines/packet_router.py)

Revision `3f96eda98240789963b0e6534aa2151aed12658e`; independent blob checksum not captured in this source record.

Tenant-bound graph endpoint resolution, typed failure and acknowledgement checks; preserves Gate mediation.

## S34: OBSERVED_REPOSITORY
[Quantum-L9/Enrichment.Inference.Engine:app/services/side_effect_coordinator.py](https://github.com/Quantum-L9/Enrichment.Inference.Engine/blob/3f96eda98240789963b0e6534aa2151aed12658e/app/services/side_effect_coordinator.py)

Revision `3f96eda98240789963b0e6534aa2151aed12658e`; independent blob checksum not captured in this source record.

Existing side-effect coordination and graph synchronization caller; integration must preserve durable-before-completed semantics.

## S35: OBSERVED_REPOSITORY
[Quantum-L9/Enrichment.Inference.Engine:tests/contracts/test_graph_sync_contract.py](https://github.com/Quantum-L9/Enrichment.Inference.Engine/blob/3f96eda98240789963b0e6534aa2151aed12658e/tests/contracts/test_graph_sync_contract.py)

Revision `3f96eda98240789963b0e6534aa2151aed12658e`; independent blob checksum not captured in this source record.

Graph sync contract/ack tests; exact endpoint and expected count; does not itself prove Odoo opportunity projection.

## S36: OBSERVED_REPOSITORY
[Quantum-L9/Enrichment.Inference.Engine:kb/plastics_recycling.yaml](https://github.com/Quantum-L9/Enrichment.Inference.Engine/blob/3f96eda98240789963b0e6534aa2151aed12658e/kb/plastics_recycling.yaml)

Revision `3f96eda98240789963b0e6534aa2151aed12658e`; independent blob checksum not captured in this source record.

Existing capability/grade/processing rule material; packaged rules are not validated industrial ground truth and must not be used blindly.

## S37: OBSERVED_REPOSITORY
[Quantum-L9/Cognitive.Engine.Graphs:domains/plasticos/spec.yaml](https://github.com/Quantum-L9/Cognitive.Engine.Graphs/blob/0d84ec8531baf604383c5ddc012f40aa84fc4b76/domains/plasticos/spec.yaml)

Revision `0d84ec8531baf604383c5ddc012f40aa84fc4b76`; independent blob checksum not captured in this source record.

Facility capability and active SupplyOpportunity candidate types; OFFERS/FULFILLS_POLYMER edges; two directions, required facility identity, quantity/price units needing explicit agreement.

## S38: OBSERVED_REPOSITORY
[Quantum-L9/Cognitive.Engine.Graphs:engine/handlers.py](https://github.com/Quantum-L9/Cognitive.Engine.Graphs/blob/0d84ec8531baf604383c5ddc012f40aa84fc4b76/engine/handlers.py)

Revision `0d84ec8531baf604383c5ddc012f40aa84fc4b76`; independent blob checksum not captured in this source record.

Active match reads query/match_direction, traverses and scores; sync dispatch and admission must be aligned with versioned projections; no observed complete gap-report application.

## S39: OBSERVED_REPOSITORY
[Quantum-L9/Cognitive.Engine.Graphs:docs/adr/ADR-104-first-match-direction.md](https://github.com/Quantum-L9/Cognitive.Engine.Graphs/blob/0d84ec8531baf604383c5ddc012f40aa84fc4b76/docs/adr/ADR-104-first-match-direction.md)

Revision `0d84ec8531baf604383c5ddc012f40aa84fc4b76`; independent blob checksum not captured in this source record.

Direction label says supply-to-buyer while prose retains buyer-demand/supplier-facility semantics. Requires semantic repair with discriminating fixtures.

## S40: OBSERVED_REPOSITORY
[Quantum-L9/Cognitive.Engine.Graphs:docs/adr/ADR-105-second-match-direction.md](https://github.com/Quantum-L9/Cognitive.Engine.Graphs/blob/0d84ec8531baf604383c5ddc012f40aa84fc4b76/docs/adr/ADR-105-second-match-direction.md)

Revision `0d84ec8531baf604383c5ddc012f40aa84fc4b76`; independent blob checksum not captured in this source record.

Buyer demand targets active supply, not general facility capability.

## S41: OBSERVED_REPOSITORY
[Quantum-L9/Cognitive.Engine.Graphs:engine/models/payloads.py](https://github.com/Quantum-L9/Cognitive.Engine.Graphs/blob/0d84ec8531baf604383c5ddc012f40aa84fc4b76/engine/models/payloads.py)

Revision `0d84ec8531baf604383c5ddc012f40aa84fc4b76`; independent blob checksum not captured in this source record.

Detached domain-neutral payload contracts use domain admission. Not proof that live handler uses the same schema.

## S42: SOURCE_IDENTIFIED_REQUIRES_CENSUS
[Quantum-L9/Cognitive.Engine.Graphs:engine/sync/generator.py](https://github.com/Quantum-L9/Cognitive.Engine.Graphs/blob/0d84ec8531baf604383c5ddc012f40aa84fc4b76/engine/sync/generator.py)

Revision `0d84ec8531baf604383c5ddc012f40aa84fc4b76`; independent blob checksum not captured in this source record.

Existing sync owner; node and edge write behavior must be proven before claiming a queryable graph projection. Full mutation path requires current owner census.

## S43: OBSERVED_REPOSITORY
[Quantum-L9/Cognitive.Engine.Graphs:tests/e2e/constellation_odoo/scripts/odoo_driver.py](https://github.com/Quantum-L9/Cognitive.Engine.Graphs/blob/0d84ec8531baf604383c5ddc012f40aa84fc4b76/tests/e2e/constellation_odoo/scripts/odoo_driver.py)

Revision `0d84ec8531baf604383c5ddc012f40aa84fc4b76`; independent blob checksum not captured in this source record.

Historical match probe accepts a signed candidates key; no mandatory nonempty buyer identity, source revision or consumer persistence proof.

## S44: OBSERVED_REPOSITORY
[Quantum-L9/Constellation.Gate:constellation-gate/src/constellation_gate/routing/action_ownership.py](https://github.com/Quantum-L9/Constellation.Gate/blob/cfeb81fa4d11eb8c106314fa27310f660a1dfad7/constellation-gate/src/constellation_gate/routing/action_ownership.py)

Revision `cfeb81fa4d11eb8c106314fa27310f660a1dfad7`; blob `c4099451db191d34937d168f138e97afa9ce5e5c`.

Canonical match/sync/outcomes are CEG owned, converge/enrich are EIE owned. New gap action requires owner admission; no side route.

## S45: SEARCH_EXCERPT
[Quantum-L9/Constellation.Gate:constellation-gate/src/constellation_gate/services/admission_service.py](https://github.com/Quantum-L9/Constellation.Gate/blob/cfeb81fa4d11eb8c106314fa27310f660a1dfad7/constellation-gate/src/constellation_gate/services/admission_service.py)

Revision `cfeb81fa4d11eb8c106314fa27310f660a1dfad7`; independent blob checksum not captured in this source record.

Read-only signed capability admission probes; registration is not a consumer entitlement.

## S46: SEARCH_EXCERPT
[Quantum-L9/Constellation.Gate:constellation-gate/src/constellation_gate/config/settings.py](https://github.com/Quantum-L9/Constellation.Gate/blob/cfeb81fa4d11eb8c106314fa27310f660a1dfad7/constellation-gate/src/constellation_gate/config/settings.py)

Revision `cfeb81fa4d11eb8c106314fa27310f660a1dfad7`; independent blob checksum not captured in this source record.

Configured caller policies bind node/kind/tenant/action to signed key; current deployment grants unknown.

## S47: SEARCH_EXCERPT
[Quantum-L9/Constellation.Gate:constellation-gate/deploy/README_DEPLOY.md](https://github.com/Quantum-L9/Constellation.Gate/blob/cfeb81fa4d11eb8c106314fa27310f660a1dfad7/constellation-gate/deploy/README_DEPLOY.md)

Revision `cfeb81fa4d11eb8c106314fa27310f660a1dfad7`; independent blob checksum not captured in this source record.

Documented Odoo consumer grant example is converge/match. Do not assume sync or gap permissions.

## S48: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:docs/adr/ADR-120-plasticos-semantic-kernel-skeleton.md](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/docs/adr/ADR-120-plasticos-semantic-kernel-skeleton.md)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Semantic addon forbids intelligence/Gate client execution; integration should not be smuggled into passive model package.

## S49: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:docs/adr/ADR-121-spec-observation-models.md](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/docs/adr/ADR-121-spec-observation-models.md)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Separate normative specification and attributed observation roles; schema only, no install-hook backfill.

## S50: OBSERVED_REPOSITORY
[cryptoxdog/IB-Odoo_19:tests/test_field_family_cutover.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/tests/test_field_family_cutover.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Definition-level control tests exist; real dispatch/read/write call-site enforcement remains a separate proof.

## S51: SOURCE_IDENTIFIED_REQUIRES_CENSUS
[cryptoxdog/IB-Odoo_19:plasticos_gate/services/dual_write.py](https://github.com/cryptoxdog/IB-Odoo_19/blob/677d734fd88615d673501d91de88734b7150ff50/plasticos_gate/services/dual_write.py)

Revision `677d734fd88615d673501d91de88734b7150ff50`; independent blob checksum not captured in this source record.

Existing dual-write owner must be inspected for reuse, parity and retention before adding operation journal semantics.

## S52: SEARCH_EXCERPT
[Quantum-L9/Cognitive.Engine.Graphs:engine/gates/compiler.py](https://github.com/Quantum-L9/Cognitive.Engine.Graphs/blob/0d84ec8531baf604383c5ddc012f40aa84fc4b76/engine/gates/compiler.py)

Revision `0d84ec8531baf604383c5ddc012f40aa84fc4b76`; independent blob checksum not captured in this source record.

Actual GateCompiler owner; domain gates must express equality/null behavior correctly. Do not mask wrong engine semantics in Odoo.

## Primary native Odoo documentation

- Security in Odoo 19: https://www.odoo.com/documentation/19.0/developer/reference/backend/security.html . ACL and record rules are distinct; absent applicable record rules can permit access. Consult exact installed models before writing security.
- Odoo 19 Coding Guidelines: https://www.odoo.com/documentation/19.0/contributing/development/coding_guidelines.html . The framework normally owns RPC transactions; do not insert arbitrary commits into business methods.

These official documents were searched on 2026-10-29. They are general native guidance, not evidence of the user's installed Enterprise code or runtime.

## Honest limits

Search absence establishes only that no call was found in the inspected indexed scope. Full dynamic, installed and native/Enterprise closure is F01. Identified external source paths require deeper owner inspection before edit (F03). Optional module state and row counts remain unknown. Previously generated campaign receipts were not used as proof of current runtime.
