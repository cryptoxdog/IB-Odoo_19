# Whole-change-set plan

This is a working, source-bound change accounting record. It contains every presently identified effect, plus explicit unobserved frontiers. It does not certify undiscovered runtime consumers as absent.

## Delivery order

- **U00**: Resolve runtime, source, contract and cross-campaign frontiers before any dependent code. Prerequisites: none. Effects: read-only proof/admission gate.
- **U01**: Admit narrow ADR amendments and implementation contracts; freeze data ownership and interface versions. Prerequisites: U00. Effects: O01, O18.
- **U02**: Harden optional semantic persistence, identity, evidence states and server-side dormancy. Prerequisites: U01. Effects: O02, O03, O04, O05, O06, O07.
- **U03**: Implement truthful scoped backfill and durable commit-bound projection operations. Prerequisites: U02. Effects: O08, O09.
- **U04**: Develop versioned EIE industrial hypothesis rules and independent evaluation. Prerequisites: U01. Effects: X01, X02.
- **U05**: Align CEG graph identity, edges, domain roles and two matching directions. Prerequisites: U01. Effects: X03, X04.
- **U06**: Implement scoped CEG gap assessment, quantity coverage and information-gap behavior. Prerequisites: U05. Effects: X05.
- **U07**: Admit and verify least-privilege Gate routes and caller scopes for the frozen external contracts. Prerequisites: U04, U05, U06. Effects: X06.
- **U08**: Wire one optional Odoo integration bridge to native opportunity sources, EIE and CEG. Prerequisites: U03, U07. Effects: O10, O11, O12, O13, O14.
- **U09**: Add native read-only review and explicit CRM handoff without duplicate commercial lifecycle. Prerequisites: U08. Effects: O15, O20, O21.
- **U10**: Complete integrated tests, optional Enterprise lane, migration/recovery and independent review. Prerequisites: U09. Effects: O16, O17, O19, X07.
- **U11**: Run isolated Staging shadow acceptance on the final immutable release set. Prerequisites: U10. Effects: read-only proof/admission gate.
- **U12**: Operator-only phased activation and monitored recovery; disabled until separately authorized. Prerequisites: U11. Effects: O22.

## Odoo effects

### O01: Odoo ADR/source authority [EDIT]

**Observed boundary:** Supply/demand and field authority are blanket-blocked; old ADRs do not express staged activation.

**Required disposition:** Adopt only the exact supersession deltas in ADR/AMENDMENTS.md. Keep prohibitions against ambiguous conversion, local intelligence and automatic activation.

Source anchor: `docs/adr/ADR-124-semantic-kernel-backfill.md@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P01, P02, P31. Dependencies: none.

Files: `docs/adr/ADR-120-plasticos-semantic-kernel-skeleton.md` (EDIT); `docs/adr/ADR-121-spec-observation-models.md` (EDIT); `docs/adr/ADR-122-supply-demand-models.md` (EDIT); `docs/adr/ADR-124-semantic-kernel-backfill.md` (EDIT); `docs/adr/ADR-125-split-opportunity-protocol.md` (EDIT); `docs/adr/ADR-126-odoo-semantic-gate-mappers.md` (EDIT); `docs/adr/ADR-127-field-family-cutover.md` (EDIT); `docs/adr/PROPOSED-semantic-kernel-controlled-activation.md` (CREATE).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O02: Semantic supply persistence [EDIT]

**Observed boundary:** Standalone editable states, supplier partner required; no direct native opportunity provenance.

**Required disposition:** Preserve stable UUID; permit prospect identity under a governed owner, bind current supply to approved native opportunity snapshot, separate listing eligibility from commercial Won. Derived projection cannot be independently traded. See DESIGN/DATA_CONTRACT.md.

Source anchor: `plasticos_semantic_kernel/models/supply_opportunity.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P04, P07, P09, P10, P21. Dependencies: O01.

Files: `plasticos_semantic_kernel/models/supply_opportunity.py` (EDIT).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O03: Semantic demand persistence [EDIT]

**Observed boundary:** Requirement-shaped rows have no evidence admission path and force partner identity.

**Required disposition:** Use confirmed inquiry/source evidence and qualified facility identity; hypothetical demand remains inference evidence. No buyer capability-to-demand auto conversion; explicit native CRM source binding via optional integration.

Source anchor: `plasticos_semantic_kernel/models/buyer_demand.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P05, P07, P09, P19. Dependencies: O01.

Files: `plasticos_semantic_kernel/models/buyer_demand.py` (EDIT).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O04: Material evidence persistence [EDIT]

**Observed boundary:** UUID immutable but general evidence facts can change; source classes exist.

**Required disposition:** Server-admitted evidence provenance, revision/expiry/supersession semantics, value-state consistency and no confirmed write from unverified inference. Append/supersede approved observations rather than rewrite.

Source anchor: `plasticos_semantic_kernel/models/material_observation.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P07, P11, P32. Dependencies: O01.

Files: `plasticos_semantic_kernel/models/material_observation.py` (EDIT); `plasticos_semantic_kernel/models/material_specification.py` (EDIT).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O05: Facility evidence persistence [EDIT]

**Observed boundary:** Useful rule/observation vocabulary exists but does not itself validate industrial inference or current demand.

**Required disposition:** Preserve accept/reject/prefer/require and capacity categories; enforce provenance, units, time and conflict states. Inferred capability is research evidence, never confirmed buying intent.

Source anchor: `plasticos_semantic_kernel/models/facility_material_rule.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P05, P06, P07, P11. Dependencies: O01.

Files: `plasticos_semantic_kernel/models/facility_material_rule.py` (EDIT); `plasticos_semantic_kernel/models/capacity_observation.py` (EDIT).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O06: Semantic security and UI [EDIT]

**Observed boundary:** Internal users can edit supply/demand; independent menus invite duplicate pipeline.

**Required disposition:** Read-only derived supply/demand views; permitted evidence approval uses checked actions. Add company rules and role-based grants, retain admin diagnostics without bypass. No standalone Run Match/Send/Mark Won.

Source anchor: `plasticos_semantic_kernel/__manifest__.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P03, P19, P23. Dependencies: O02, O03, O04, O05.

Files: `plasticos_semantic_kernel/security/ir.model.access.csv` (EDIT); `plasticos_semantic_kernel/views/supply_opportunity_views.xml` (EDIT); `plasticos_semantic_kernel/views/buyer_demand_views.xml` (EDIT); `plasticos_semantic_kernel/views/menus.xml` (EDIT); `plasticos_semantic_kernel/security/semantic_rules.xml` (CREATE).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O07: Semantic module wiring [EDIT]

**Observed boundary:** Optional schema package; no real ORM test suite registered.

**Required disposition:** Bump installed version monotonically, register security and model tests, remain optional/non-auto-installed and free of Gate/client/scoring imports.

Source anchor: `plasticos_semantic_kernel/__manifest__.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P03, P11, P19, P23, P24. Dependencies: O06.

Files: `plasticos_semantic_kernel/__manifest__.py` (EDIT); `plasticos_semantic_kernel/models/__init__.py` (EDIT); `plasticos_semantic_kernel/tests/__init__.py` (EDIT); `plasticos_semantic_kernel/README.md` (EDIT); `plasticos_semantic_kernel/tests/test_evidence_admission.py` (CREATE); `plasticos_semantic_kernel/tests/test_projection_ownership.py` (CREATE).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O08: Backfill planner [EDIT]

**Observed boundary:** Supply/demand blocked; created increments without a writer; mapping version participates in identity; conflict check fixture-only.

**Required disposition:** Keep default denial and replace blanket block only for an approved source family/batch. Stable business identity independent of mapping version; planned/committed/reused/rejected/unknown outcomes reflect durable results. Detect real conflicts and safe resume cursor.

Source anchor: `scripts/semantic_kernel_backfill_engine.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P04, P05, P08, P09. Dependencies: O07.

Files: `scripts/semantic_kernel_backfill_engine.py` (EDIT); `tests/test_semantic_kernel_backfill.py` (EDIT); `tests/test_semantic_kernel_backfill_family_report.py` (EDIT).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O09: Backfill execution boundary [EDIT]

**Observed boundary:** Fixture-only rows; force dry-run; no ORM persistence and no source admission.

**Required disposition:** Keep ordinary CLI dry-run. Authorized execute binds a live read adapter and owned ORM write adapter in the optional bridge, reviewed batch/digest/company/source cutoff. No flag-only global unblock or install-hook writes.

Source anchor: `scripts/semantic_kernel_backfill.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P01, P03, P08, P09. Dependencies: O08.

Files: `scripts/semantic_kernel_backfill.py` (EDIT).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O10: Gate domain mappings [EDIT]

**Observed boundary:** Hardcoded Odoo supply record IDs, revision default 1, empty evidence, nested direction wrapper differs from active match.

**Required disposition:** Single versioned owner-approved mapping from typed source. Preserve source/UUID/tenant/revision, quantity state and evidence; distinguish sync, match and gap payloads. Never point stale wrapper directly at live match handler.

Source anchor: `plasticos_gate/services/semantic_payloads.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P07, P12, P13, P14, P15, P16, P31. Dependencies: O09.

Files: `plasticos_gate/services/semantic_payloads.py` (EDIT); `plasticos_gate/services/gate_contracts.py` (EDIT); `plasticos_gate/services/gate_builders.py` (EDIT); `plasticos_gate/services/gate_mappers.py` (EDIT); `tests/test_semantic_gate_payloads.py` (EDIT); `tests/test_gate_canonical_contract.py` (EDIT).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O11: Field-authority and activation controls [EDIT]

**Observed boundary:** Specification-only classifier; controls not proven to guard business dispatch.

**Required disposition:** Preserve existing specification behavior. Add only owner-admitted family/operation checks and call-site enforcement; backfill is not read-authority promotion; default off with grant bound to tenant/release/evidence. No local fallback.

Source anchor: `plasticos_gate/services/field_family_cutover.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P03, P12, P27, P29. Dependencies: O10.

Files: `plasticos_gate/services/field_family_cutover.py` (EDIT); `tests/test_field_family_cutover.py` (EDIT).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O12: Gate SDK consumer seam [EDIT]

**Observed boundary:** Existing SDK seam and dual_write module; no proven authoritative native-opportunity publisher.

**Required disposition:** Inspect/reuse dual_write and SDK transport before adding operation support; maintain one SDK import owner and verified signed failures. New source sync calls remain forbidden until explicit Gate grant.

Source anchor: `plasticos_gate/__manifest__.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P02, P03, P12, P27, P31. Dependencies: O11.

Files: `plasticos_gate/services/gate_client.py` (EDIT); `plasticos_gate/services/gate_config.py` (EDIT); `plasticos_gate/__manifest__.py` (EDIT).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O13: Optional integration ownership [CREATE]

**Observed boundary:** No existing addon owns both optional kernel integration and CRM/Gate orchestration without broadening mandatory installation or violating ADR-120.

**Required disposition:** Proposed optional bridge depends on kernel, native CRM bridge, Gate, matching and enrichment. No mandatory addon depends on it. Schema remains passive; transport remains plasticos_gate. Admission of new addon requires U00 sufficiency check.

Source anchor: `plasticos_semantic_bridge/__manifest__.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P02, P03, P04, P05, P08, P12, P23. Dependencies: O09, O12.

Files: `plasticos_semantic_bridge/__manifest__.py` (CREATE); `plasticos_semantic_bridge/__init__.py` (CREATE); `plasticos_semantic_bridge/models/__init__.py` (CREATE); `plasticos_semantic_bridge/models/opportunity_projection.py` (CREATE); `plasticos_semantic_bridge/models/projection_operation.py` (CREATE); `plasticos_semantic_bridge/models/semantic_admission.py` (CREATE).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O14: Optional bridge lifecycle/writer [CREATE]

**Observed boundary:** There is no proved native opportunity -> semantic -> graph lifecycle publisher.

**Required disposition:** Checked material-readiness approval captures exact snapshot; durable operation written with source transaction; background worker publishes after commit, retries stable identity and rejects stale revision. No generic message bus. Reuse existing durable journal if U00 proves it sufficient.

Source anchor: `plasticos_semantic_bridge/models/opportunity_projection.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P03, P08, P09, P13, P21, P27. Dependencies: O13.

Files: `plasticos_semantic_bridge/services/__init__.py` (CREATE); `plasticos_semantic_bridge/services/backfill_adapter.py` (CREATE); `plasticos_semantic_bridge/services/projection_service.py` (CREATE); `plasticos_semantic_bridge/models/semantic_scheduler.py` (CREATE); `plasticos_semantic_bridge/data/semantic_cron.xml` (CREATE); `plasticos_semantic_bridge/models/__init__.py` (EDIT); `plasticos_semantic_bridge/__manifest__.py` (EDIT).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O15: Optional bridge review/security [CREATE]

**Observed boundary:** No explicit hypothesis-review -> native CRM handoff for this capability.

**Required disposition:** Native read-only fact/hypothesis/gap views and explicit review actions. Human can create/reuse lead or link opportunity, but never implicitly send offers, issue PO or create partner. Underlying receipt remains with evidence owner.

Source anchor: `plasticos_semantic_bridge/models/semantic_admission.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P03, P10, P19, P20, P22. Dependencies: O14.

Files: `plasticos_semantic_bridge/views/semantic_review_views.xml` (CREATE); `plasticos_semantic_bridge/security/ir.model.access.csv` (CREATE); `plasticos_semantic_bridge/security/semantic_rules.xml` (CREATE); `plasticos_semantic_bridge/wizards/__init__.py` (CREATE); `plasticos_semantic_bridge/wizards/semantic_review.py` (CREATE); `plasticos_semantic_bridge/__manifest__.py` (EDIT); `plasticos_semantic_bridge/__init__.py` (EDIT).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O16: Optional bridge proofs [CREATE]

**Observed boundary:** No current integrated optional-bridge tests.

**Required disposition:** Register real ORM tests for dormancy, source ownership, backfill, races, lifecycle and non-HOT preservation; use no paid calls or real email by default.

Source anchor: `plasticos_semantic_bridge/tests/__init__.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P03, P08, P09, P19, P20, P21, P22, P24. Dependencies: O15.

Files: `plasticos_semantic_bridge/tests/__init__.py` (CREATE); `plasticos_semantic_bridge/tests/test_dormant_boundaries.py` (CREATE); `plasticos_semantic_bridge/tests/test_source_projection.py` (CREATE); `plasticos_semantic_bridge/tests/test_backfill_commit.py` (CREATE); `plasticos_semantic_bridge/tests/test_lifecycle_replay.py` (CREATE); `plasticos_semantic_bridge/tests/test_review_handoff.py` (CREATE).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O17: Install, migration and optional tests [EDIT]

**Observed boundary:** Default critical lane excludes semantic kernel; optional collision suite is non-standard.

**Required disposition:** Keep default exclusion; add separate opt-in optional-kernel/bridge Enterprise lane and explicit versioned data migration. Freeze numeric migration directory only after current installed versions known. Preserve default MVP lane.

Source anchor: `config/odoo_module_order.yaml@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P01, P09, P23, P24. Dependencies: O16.

Files: `config/odoo_module_order.yaml` (EDIT); `tests/test_semantic_kernel_skeleton.py` (EDIT); `tests/test_semantic_kernel_supply_demand.py` (EDIT); `tests/test_semantic_kernel_spec_observation.py` (EDIT); `tests/test_semantic_kernel_facility_capacity.py` (EDIT).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O18: Payload schemas and validators [EDIT]

**Observed boundary:** Detached draft schemas coexist with live shapes; peer supply/demand and source references are not runtime equivalence.

**Required disposition:** Version revisions only after contract-owner admission; preserve peer protocols, source evidence and explicit quantity/availability. Add matched native source lineage and gap/hypothesis exchange schemas at owners, not transport fields.

Source anchor: `contracts/schemas/draft/supply-opportunity.schema.yaml@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P02, P07, P12, P31. Dependencies: O01.

Files: `contracts/schemas/draft/supply-opportunity.schema.yaml` (EDIT); `contracts/schemas/draft/buyer-demand.schema.yaml` (EDIT); `contracts/schemas/draft/canonical-projection.schema.yaml` (EDIT); `contracts/schemas/examples/supply-opportunity.json` (EDIT); `contracts/schemas/examples/buyer-demand.json` (EDIT); `scripts/opportunity_protocol.py` (EDIT); `scripts/projection_outcome_schemas.py` (EDIT); `tests/test_opportunity_protocol_split.py` (EDIT); `tests/test_projection_outcome_schemas.py` (EDIT).

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O19: Existing provisional material ownership [NO_CHANGE]

**Observed boundary:** CRM bridge already permits lead-owned material/facility profiles and reconciliation.

**Required disposition:** NO_CHANGE to the ownership mechanism in this campaign. The optional bridge must consume it and prove profile collision/foreign-key preservation. Reopen only a demonstrated defect; do not create parallel provisional model.

Source anchor: `plasticos_crm_bridge/__manifest__.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P10, P24. Dependencies: O17.

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O20: Web/CRM/matching/offer commercial seam [NO_CHANGE]

**Observed boundary:** Partnerless match and single canonical review/offer paths are owned by the branched web-lead campaign; current baseline still has conflicting legacy guards.

**Required disposition:** CONSUME predecessor interface and proof, do not duplicate its implementation. This plan supplies source facts and consumes canonical match results. No new direct supplier match or independent offer review.

Source anchor: `plasticos_matching/__manifest__.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P14, P16, P20, P21, P22, P30. Dependencies: O14.

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O21: Native PO/partner and Lost event ownership [NO_CHANGE]

**Observed boundary:** Legacy intake can claim PO creation from a transaction; external campaign must implement confirmed-PO and required-loss-reason semantics.

**Required disposition:** CONSUME actual native confirmed PO and explicit Lost reason as inputs only; no own partner/PO/won writer. Procurement alone does not prove buyer allocation or physical sale. Unknown residual disposition fails closed.

Source anchor: `plasticos_transaction/__manifest__.py@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P20, P21, P22. Dependencies: O14.

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

### O22: Release and recovery [NO_CHANGE]

**Observed boundary:** Source presence and tests are not production admission.

**Required disposition:** Exact multi-repo release set, operator authorization, company/operation allowlist, cost caps, live receipt, kill switch and restoration proof before any use. All package activation grants false.

Source anchor: `docs/adr/ADR-007-deployment-architecture.md@677d734fd88615d673501d91de88734b7150ff50`. Proofs: P26, P27, P28, P29, P34. Dependencies: O17, O19, O20, O21.

Migration: Versioned additive migration only after exact installed registry/data census; preserve IDs, historical approvals and source lineage. No install-hook backfill.

Recovery: Keep feature dormant; restore exact database/filestore and release set only from verified backup when destructive reversal is necessary. Preserve evidence and pause pending operations.

## External effects

### X01: Quantum-L9/Enrichment.Inference.Engine / Industrial inference rules

Pinned revision `3f96eda98240789963b0e6534aa2151aed12658e`; unit U04.

Existing rule infrastructure and a small plastics rule set, no proven full industrial inference application.

**Plan:** Add source-backed, versioned process/product-to-potential-material and capability-to-potential-demand rules, prerequisites/counterexamples, evidence/rationale/expiry/abstention. Hypotheses only; no order/inventory creation. All general mechanisms remain domain-neutral. No-change source entries are preservation obligations, not permission to edit if convenient.

Files: `domains/plasticos/spec.yaml` (EDIT); `app/engines/inference/rule_loader.py` (NO_CHANGE); `app/engines/inference_bridge_adapter.py` (NO_CHANGE); `tests/integration/test_industrial_hypothesis_pipeline.py` (CREATE); `docs/adr/PROPOSED-industrial-inference-evidence-admission.md` (CREATE).

Proofs: P06, P32, P33.

### X02: Quantum-L9/Enrichment.Inference.Engine / Evidence durability and sync coordination

Pinned revision `3f96eda98240789963b0e6534aa2151aed12658e`; unit U04.

Durable result and sync paths exist but are not a confirmed Odoo supply publisher.

**Plan:** Reuse durable results, tenant-bound routing and ack logic. Do not route authoritative Odoo facts through inference merely to obtain worker permissions. Preserve provenance and parent evidence revision. No-change source entries are preservation obligations, not permission to edit if convenient.

Files: `app/engines/handlers.py` (NO_CHANGE); `app/services/side_effect_coordinator.py` (NO_CHANGE); `app/engines/packet_router.py` (NO_CHANGE); `tests/contracts/test_graph_sync_contract.py` (EDIT).

Proofs: P12, P13, P32.

### X03: Quantum-L9/Cognitive.Engine.Graphs / Graph identity and lifecycle

Pinned revision `0d84ec8531baf604383c5ddc012f40aa84fc4b76`; unit U05.

SupplyOpportunity/BuyerDemand graph vocabulary exists; mandatory facility IDs and required relations need canonical mapping; detached/live schemas differ.

**Plan:** Admit stable prospect/source identity; upsert nodes AND required edges, latest-revision guards, tombstones, tenant isolation and verified eligibility. Acknowledgement proves materialized identities and lineage, not only transport. No-change source entries are preservation obligations, not permission to edit if convenient.

Files: `domains/plasticos/spec.yaml` (EDIT); `engine/handlers.py` (EDIT); `engine/models/payloads.py` (EDIT); `engine/sync/generator.py` (EDIT); `tests/integration/test_source_projection_lifecycle.py` (CREATE); `docs/adr/PROPOSED-source-projection-and-gap-assessment.md` (CREATE).

Proofs: P07, P12, P13, P15, P31.

### X04: Quantum-L9/Cognitive.Engine.Graphs / Matching domain semantics

Pinned revision `0d84ec8531baf604383c5ddc012f40aa84fc4b76`; unit U05.

First direction label/prose/roles conflict; second direction distinguishes active supply from capacity.

**Plan:** Specify supplier-offered load -> eligible buying facility; confirmed buyer need -> genuinely current supply. Unit tests must distinguish commercial role, capability and need. Fix only verified compiler defects at compiler owner; no Odoo workaround. No-change source entries are preservation obligations, not permission to edit if convenient.

Files: `docs/adr/ADR-104-first-match-direction.md` (EDIT); `docs/adr/ADR-105-second-match-direction.md` (EDIT); `domains/plasticos/spec.yaml` (EDIT); `tests/unit/test_first_match_direction.py` (EDIT); `tests/unit/test_second_match_direction.py` (EDIT); `tests/integration/test_match_handler.py` (EDIT).

Proofs: P14, P15, P16, P30.

### X05: Quantum-L9/Cognitive.Engine.Graphs / Scoped gap analysis

Pinned revision `0d84ec8531baf604383c5ddc012f40aa84fc4b76`; unit U06.

No complete, independently verified supply/demand-gap application located.

**Plan:** Proposed domain-neutral gap assessment composes actual eligible match evidence and scoped quantity coverage, with explicit information-gap/unknown outcomes. Proposed canonical action assess-gaps is not callable until admitted; reuse an existing equivalent route if U00 proves it sufficient. No-change source entries are preservation obligations, not permission to edit if convenient.

Files: `engine/gaps/__init__.py` (CREATE); `engine/gaps/assessment.py` (CREATE); `tests/unit/test_gap_assessment.py` (CREATE); `tests/integration/test_gap_assessment.py` (CREATE); `engine/handlers.py` (EDIT); `engine/spec.yaml` (EDIT); `engine/models/payloads.py` (EDIT).

Proofs: P17, P18, P31.

### X06: Quantum-L9/Constellation.Gate / Canonical route and caller authority

Pinned revision `cfeb81fa4d11eb8c106314fa27310f660a1dfad7`; unit U07.

Odoo documented grant example covers converge/match; deployed scope unknown; no admitted gap action.

**Plan:** After source-owner admission, route narrow CEG gap action and permitted source-projection operation. Signed Odoo consumer must remain consumer. Least-privilege tenant/action/source scope; do not grant worker or unrestricted sync privileges. Preserve existing routes. No-change source entries are preservation obligations, not permission to edit if convenient.

Files: `constellation-gate/src/constellation_gate/routing/action_ownership.py` (EDIT); `constellation-gate/src/constellation_gate/config/settings.py` (NO_CHANGE); `constellation-gate/src/constellation_gate/services/admission_service.py` (NO_CHANGE); `constellation-gate/deploy/README_DEPLOY.md` (EDIT); `constellation-gate/tests/api/test_admission_endpoint.py` (EDIT); `constellation-gate/tests/boundary/test_ingress_validator.py` (EDIT).

Proofs: P02, P03, P12, P31.

### X07: Quantum-L9/Cognitive.Engine.Graphs / Actual Odoo cross-system proof

Pinned revision `0d84ec8531baf604383c5ddc012f40aa84fc4b76`; unit U10.

Historical match positive is satisfied by candidates key; insufficient for full application.

**Plan:** Mandatory nonempty positive and correct empty negative, real registry IDs, saved review result, source revisions, edge readback, rollback/expiry/reopen/disable and role checks. Separate synthetic rules fixture from live evidence pilot. No-change source entries are preservation obligations, not permission to edit if convenient.

Files: `tests/e2e/constellation_odoo/scripts/odoo_driver.py` (EDIT); `tests/e2e/constellation_odoo/scripts/assert_odoo_evidence.py` (EDIT); `tests/e2e/constellation_odoo/README.md` (EDIT).

Proofs: P13, P14, P15, P16, P26, P27.

## No-change is bounded, not magical

`case.json` accounts for all six reverse-manifest candidates from the selected roots and additional cross-system consumers. A no-change means the proposed boundary preserves the consumer API and a named regression test is required. It does not mean a live database, dynamic action or every runtime path has been observed. F01/F03 reopens affected no-change decisions if a real consumer is found.

## Prospective file constraints

All CREATE paths are proposed additions, not existing files. All EDIT paths require exact source-content inspection at the frozen implementation head; paths identified by search or by module ownership are not treated as completed behavioral inspection. Dynamic migrations and existing test-command owners must be resolved in U00/U01. No numeric migration directory or deployment command is guessed.

## Concurrent work

After U00/U01, EIE U04 and CEG U05 can develop against the same frozen contracts while Odoo U02/U03 implements passive safety. CEG U06 follows U05 because they share handler/domain source. Gate U07 consumes admitted external actions. The Odoo integration U08 consumes those contracts and the sibling commercial interface. U10/U11 acceptance is combined even when implementation was independent.

No two agents write the same source path simultaneously. Reinspect current PRs and manifest versions before allocating each unit. Code may stack on an accepted predecessor head when that is the actual dependency; do not invent merge-only waiting. The protected web-lead campaign is not widened to include this kernel.
