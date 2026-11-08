---
status: IN FLIGHT IN Claude Code DO NOT BUILD.
name: Partners First Native Opportunity Matching Canonical Revision
overview: "Realize the approved Partners-first native crm.lead Opportunity root from fetched origin/Staging c8e7efebb03d79e3a5b220b8a7568a750918b2ed. Qualified HOT evidence or a manual Partner plus Material Profile converges on one Opportunity matching command, with plasticos.opportunity.approval as the immutable lot, optional Facility, Run to Result to Offer lineage owned by plasticos_crm_bridge, and native sale.order.opportunity_id plus the existing Transaction compiler. The 2026-11-04 schema delta is the field authority once contracts/SCHEMA_APPROVAL_2026-11-04.md is on the branch. Runtime proofs V1-V7 stay pending. Status stays draft until that ledger is admitted."
todos:
  - id: T02
    content: "Add plasticos.opportunity.approval in CRM Bridge with the approved fields, unprefixed ACL rows, version 19.0.3.4.20, and a server-minted immutable create path."
    status: pending
    phase: execute
    depends_on: []
  - id: T03
    content: "Add opportunity_id and approval_id on the match run, match_result_id on the offer, optional restrict intake links, and the partial uniqueness rules from the 2026-11-04 ledger."
    status: pending
    phase: execute
    depends_on: [T02]
  - id: T04
    content: "Send HOT, manual, and VanillaSoft ingress to a verified Partner, Material Profile, and native Opportunity without creating a synthetic Intake or Facility."
    status: pending
    phase: execute
    depends_on: [T02, T03]
  - id: T05
    content: "Build the Gate request from the frozen approval, keep one Gate orchestrator, and omit facility evidence when it is absent."
    status: pending
    phase: execute
    depends_on: [T02, T03]
  - id: T06
    content: "Create idempotent unsent offers from reviewed current results, keep terms immutable, and record one explicit commercial winner."
    status: pending
    phase: execute
    depends_on: [T04, T05]
  - id: T07
    content: "On acceptance, create or reuse one draft sale.order with native opportunity_id and the offer sell terms, then leave confirmation to the existing transaction compiler."
    status: pending
    phase: execute
    depends_on: [T06]
  - id: T09
    content: "Expose the Opportunity, Run, Result, and Offer lineage in the existing views without a second matching command."
    status: pending
    phase: execute
    depends_on: [T07]
  - id: T08
    content: "Run the Enterprise fixture migration and module suites, including interruption and a two-company visibility check, on a clone of odoo_test_tpl_ee_c9e8a81f52f23680."
    status: pending
    phase: execute
    depends_on: [T09]
  - id: T10
    content: "Append the native Opportunity correction to AGENTS.md and record finding continuity against the final fixture result."
    status: pending
    phase: execute
    depends_on: [T08]
isProject: false
kind: simple
execute_via: cursor-build
status: current
---

# PLAN: Partners First Native Opportunity Matching Canonical Revision

> **Projected by** `scripts/render_plan_pe_autonomy.py` from validated PLAN_DOCUMENT JSON.

> **First-class SSOT (git):** `environment/contracts/execution/templates/canonical.template.executable_plan.v1.plan.md` · metadata sidecar `*.meta.md` · registered in `environment/contracts/execution/MANIFEST.yaml`. Skill path is a symlink; `.cursor/plans/_TEMPLATE.plan.md` is a local mirror only.
> **Schema:** `canonical.schema.plan_document.v1` (status: fill → `executable` only when law holds)
> **Parameters:** every value is projected from PLAN_DOCUMENT. A value reading `unknown — …` or `unbound — …` is absent from PLAN_DOCUMENT and must be resolved before status becomes `executable`.
> **Execute:** status stays `draft` until `contracts/SCHEMA_APPROVAL_2026-11-04.md` is on the branch. When status is `executable`, press **Build** in a new clean worktree of fetched `origin/Staging`. After the todos, scoped-commit, `l4_local.py authorize-release`, then `make pr` with no `PR_STACK`, and display the PR URL. Do **not** run `make campaign`, admit a Program Lock, set `PR_STACK=auto`, branch from `origin/main` or local `Staging`, or free-form mutate from this markdown alone.
> **Cursor todos:** frontmatter `todos` project to Build todos. Body is the binding contract.
> **File name:** `partners_first_native_opportunity_matching_canonical_revision_a8251674.plan.md`
> **Law:** executable only when baseline matches, capability probes pass, invariants match, and envelope is respected. Markdown completeness alone is insufficient.

## Execute via Cursor Build

Press **Build** only after P2 passes. Execute in a new clean worktree of fetched `origin/Staging`, not on `docs/brs-documents-logistics-ownership`.

- Start with `agent_worktree_start.sh --base origin/Staging` and `L9_TASK_BASE_AUTHORIZED` set. PlasticOS integration is `origin/Staging`, not `origin/main`. Sibling pull requests into `Staging` are not a stack parent. `PR_STACK=auto` looks for pull requests into `main` and exits 2 on this board.
- Fetch `origin/Staging` at execution start. The worktree HEAD must equal that fetched SHA. Refuse local `Staging` (`4a6af0b2d5bbf8f16e4fa67baafe9d71e3b4f384`, 36 commits behind) and refuse historical `7d23e632d8341424e4faae33a085c12fe7fbe6da`.
- Do not run `make campaign`.
- Do not admit a Program Lock or Controller lease.
- Do not write `Lock: origin/main = <sha>`.
- Do not stack onto `docs/brs-documents-logistics-ownership`.
- After Build todos complete: scoped-commit (pathspecs), `l4_local.py authorize-release`, then `make pr` with no `PR_STACK`. Do not skip `make pr`. `scripts/pr_stack_parent.sh` accepts `Staging` as the publication base.
- The finish reply **must** display the opened PR URL as proof. Without that URL the Build is incomplete.

## Metadata

| Field | Value |
|-------|-------|
| plan_id | `plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1` |
| name | Partners First Native Opportunity Matching Canonical Revision |
| overview | Realize the approved Partners-first native crm.lead Opportunity root from fetched origin/Staging c8e7efebb03d79e3a5b220b8a7568a750918b2ed. Qualified HOT evidence or a manual Partner plus Material Profile converges on one Opportunity matching command, with plasticos.opportunity.approval as the immutable lot, optional Facility, Run to Result to Offer lineage owned by plasticos_crm_bridge, and native sale.order.opportunity_id plus the existing Transaction compiler. The 2026-11-04 schema delta is the field authority once contracts/SCHEMA_APPROVAL_2026-11-04.md is on the branch. Runtime proofs V1-V7 stay pending. Status stays draft until that ledger is admitted. |
| schema_version | `1.0.0` |
| status | `draft` — planning convergence is `partial` |
| is_project | `false` |
| owner | igor_beylin |
| created_at | 2026-11-04T22:29:28+00:00 |
| updated_at | 2026-11-05T19:16:00+00:00 |
| depth | `deep` |
| estimate | Approved delta on CRM Bridge, Matching, Gate, Offer, CRM sync, and Transaction. Execution starts from a clean worktree of fetched origin/Staging c8e7efebb03d79e3a5b220b8a7568a750918b2ed. Historical worktree 7d23e632d8341424e4faae33a085c12fe7fbe6da is not an ancestor of that commit. Local Staging 4a6af0b2d5bbf8f16e4fa67baafe9d71e3b4f384 is 36 commits behind origin/Staging and is refused. |

## Architect framing

| Field | Value |
|-------|-------|
| planning_ssot | validated PLAN_DOCUMENT JSON (`validate_plan_document.py`) |
| plan_class | `bounded_execution_contract` — PLAN_DOCUMENT mode `plan` |
| redesign_allowed | `false` |
| follow_on_schema_evolution_separate | `true` |
| framing_notes | Execute via Cursor Build from a clean worktree of fetched origin/Staging, then make pr with no PR_STACK. Sibling Staging pull requests are not a stack parent. No redesign unless plan_class requires it. |

## Immutable baseline

| Field | Value |
|-------|-------|
| captured_at | `2026-11-05T19:16:00+00:00` |
| repository | `cryptoxdog/IB-Odoo_19` |
| workspace | clean worktree created by `agent_worktree_start.sh --base origin/Staging` |
| branch | `origin/Staging` |
| commit_sha | `c8e7efebb03d79e3a5b220b8a7568a750918b2ed` |
| historical_commit_sha | `7d23e632d8341424e4faae33a085c12fe7fbe6da` — not an ancestor of origin/Staging; refused |
| local_staging_sha | `4a6af0b2d5bbf8f16e4fa67baafe9d71e3b4f384` — 36 commits behind origin/Staging; refused |
| planning_checkout | untracked plan file on `docs/brs-documents-logistics-ownership` at `8f599abf41d3b3e5dc7e9aa8d11a42c0b6cecad4`; not the execution checkout |
| dirty | `false` — the execution worktree must be clean |
| artifact_hashes | `{}` — none pinned by PLAN_DOCUMENT |
| allowed_local_dirt | none |
| overlap_policy | `stop_if_dirty_overlaps_may_modify` |
| verification_rule | `reverify_at_execution_start` |
| on_drift | `stop_and_replan` |

## Objective

### Mission

Realize the approved Partners-first native crm.lead Opportunity root from fetched origin/Staging c8e7efebb03d79e3a5b220b8a7568a750918b2ed. Qualified HOT evidence or a manual Partner plus Material Profile converges on one Opportunity matching command, with plasticos.opportunity.approval as the immutable lot, optional Facility, Run to Result to Offer lineage owned by plasticos_crm_bridge, and native sale.order.opportunity_id plus the existing Transaction compiler. The 2026-11-04 schema delta is the field authority once contracts/SCHEMA_APPROVAL_2026-11-04.md is on the branch. Runtime proofs V1-V7 stay pending. Status stays draft until that ledger is admitted.

### Scope in

- plasticos.opportunity.approval and the CRM Bridge lineage fields in contracts/SCHEMA_APPROVAL_2026-11-04.md
- HOT, manual, and VanillaSoft ingress onto a verified Partner, Material Profile, and native Opportunity
- Gate-only match request built from the frozen approval, with facility omitted when absent
- Enterprise fixture tests on odoo_test_tpl_ee_c9e8a81f52f23680

### Success properties

Each property's proof is the `final_validation` entry it names (by id or by script/file). A property with no proving validation, or only skipped / not_applicable ones, blocks `executable`.

| id | property | evidence_type | proof | blocking |
|----|----------|---------------|-------|----------|
| SP-01 | V1 proves HOT and manual routes use native Opportunity with verified Partner and Profile, source evidence optional, and independent approval snapshots. | `quality_gate` | V1: `make test-module m=plasticos_crm_bridge` → HOT and manual admission tests pass, including two lots for one partner and profile and no synthetic intake | `true` |
| SP-02 | V2 proves Facility is optional on the Gate request, Run, and Result, and missing optional evidence is omitted rather than fabricated. | `quality_gate` | V2: `make test-module m=plasticos_matching` → A run with no facility is accepted, empty scores stay empty, and the request matches the frozen approval | `true` |
| SP-03 | V3 proves typed Result-to-Offer lineage, idempotent unsent drafts, human review, and one commercial winner. | `quality_gate` | V3: `make test-module m=plasticos_offer` → Two reviewed results create two unsent drafts and a second acceptance does not create a second winner | `true` |
| SP-04 | V4 proves a native sale order with opportunity_id reaches the existing Transaction compiler, with independent purchase orders and truthful mail state. | `quality_gate` | V4: `make test-module m=plasticos_transaction` → The draft sale order uses opportunity_id, confirmation compiles one transaction, and no Won flag is set from acceptance alone | `true` |
| SP-05 | V5 proves the nullability and partial-unique migration keeps historical rows visible and does not invent lineage. | `quality_gate` | V5: `make test-module m=plasticos_crm_bridge` → Historical rows remain readable, null intake is allowed, and source intake uniqueness does not collapse manual lots | `true` |
| SP-06 | V6 and V7 prove the Enterprise fixture suites, manifest DAG, and .pre-commit-config.yaml owner gates after implementation. | `quality_gate` | V6: `python3 scripts/check_module_wiring.py && python3 ci/check_circular_deps.py` → CRM Bridge may depend on Matching and Offer. Matching does not depend on CRM Bridge. No cycle is reported.; V7: `ruff check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction && ruff format --check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction && test -f .pre-commit-config.yaml` → Ruff reports no findings on the touched modules and the hook catalog file is present | `true` |

## Capability preflight

`schema_ref:` `canonical.schema.capability_preflight.v1`
`instance_binding:` `capability_preflight_ref` → `preflight.plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1`

| Field | Value |
|-------|-------|
| preflight_id | `preflight.plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1` |
| source_ref | `plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1` |
| phase_id | `preflight` |
| blocking | `true` |
| immutable_baseline_ref | `baseline.plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1` |
| baseline_verified | `false` — reverify by fetching origin/Staging at execution start |
| drift_detected | `true` — historical baseline 7d23e632d8341424e4faae33a085c12fe7fbe6da is not an ancestor of origin/Staging c8e7efebb03d79e3a5b220b8a7568a750918b2ed |

### Probes (from PLAN_DOCUMENT `pre_validation`; failed blocking probe → status `preflight_blocked`)

| id | capability | command_or_action | pass_criteria | blocking |
|----|------------|-------------------|---------------|----------|
| P0 | pre-validation (status `not_run`) | `git fetch origin Staging && git rev-parse HEAD` | Clean worktree HEAD equals fetched origin/Staging c8e7efebb03d79e3a5b220b8a7568a750918b2ed. Local Staging 4a6af0b2d5bbf8f16e4fa67baafe9d71e3b4f384 and historical 7d23e632d8341424e4faae33a085c12fe7fbe6da are refused. | `true` |
| P1 | pre-validation (status `passed`) | `Read match run, offer, gate builder, and CRM Bridge manifests` | On this checkout, intake is still required, match_result_id stays commented out in plasticos_offer/models/offer.py, and plasticos_crm_bridge 19.0.3.4.19 comments out plasticos_matching. | `true` |
| P2 | pre-validation (status `failed`) | `Read contracts/SCHEMA_APPROVAL_2026-11-04.md` | The file is absent from the tree. The only copy is untracked inside stash@{5}. S1-S5 are not admitted. Feature Build stays draft. | `true` |
| P3 | pre-validation (status `unverified`) | `Read sale_crm in the Odoo 19 tree and config/test_env_fixture.conf` | sale.order.opportunity_id exists and the disposable database is odoo_test_tpl_ee_c9e8a81f52f23680 | `true` |
| P4 | pre-validation (status `unverified`) | `python3 ops/hooks/plan_memory_prefetch.py` | HIT with conflicts 0 and digest f9e69f08f9a92e10ba5df37f8f63f47d30e1253bc3ddb67f9174c8c12c3bc5d2 | `true` |

## Execution envelope

Mutations outside this envelope are forbidden (PLAN-SCHEMA-004).

### Filesystem

- **write_allow:** `plasticos_crm_bridge/models/opportunity_approval.py`, `plasticos_crm_bridge/models/match_lineage.py`, `plasticos_crm_bridge/models/__init__.py`, `plasticos_crm_bridge/models/crm_lead.py`, `plasticos_crm_bridge/models/web_lead.py`, `plasticos_crm_bridge/models/crm_lead_vanillasoft.py`, `plasticos_crm_bridge/views/crm_lead_views.xml`, `plasticos_crm_bridge/security/ir.model.access.csv`, `plasticos_crm_bridge/__manifest__.py`, `plasticos_crm_bridge/migrations/19.0.3.4.20/post-migrate.py`, `plasticos_crm_bridge/tests/__init__.py`, `plasticos_crm_bridge/tests/test_opportunity_approval.py`, `plasticos_crm_bridge/tests/test_opportunity_migration.py`, `plasticos_matching/models/match_run.py`, `plasticos_matching/models/match_result.py`, `plasticos_matching/models/match_result_link.py`, `plasticos_matching/models/match_orchestrator.py`, `plasticos_matching/models/match_result_writer.py`, `plasticos_matching/models/intake_extension.py`, `plasticos_matching/views/match_run_views.xml`, `plasticos_matching/views/match_result_views.xml`, `plasticos_matching/__manifest__.py`, `plasticos_matching/migrations/19.0.3.1.5/post-migrate.py`, `plasticos_gate/services/gate_builders.py`, `plasticos_gate/services/gate_mappers.py`, `plasticos_gate/__manifest__.py`, `plasticos_gate/migrations/19.0.1.9.7/post-migrate.py`, `plasticos_crm_sync/services/orchestrator.py`, `plasticos_crm_sync/__manifest__.py`, `plasticos_crm_sync/migrations/19.0.1.9.19/post-migrate.py`, `plasticos_intake/models/res_partner_intake.py`, `plasticos_intake/models/material_profile_intake.py`, `plasticos_offer/models/offer.py`, `plasticos_offer/models/intake_offers_bridge.py`, `plasticos_offer/models/offer_price_bridge.py`, `plasticos_offer/wizards/offer_bulk_action_wizard.py`, `plasticos_offer/views/offer_views.xml`, `plasticos_offer/__manifest__.py`, `plasticos_offer/migrations/19.0.1.1.3/post-migrate.py`, `plasticos_transaction/models/offer_bridge.py`, `plasticos_transaction/models/sale_inherit.py`, `plasticos_transaction/__manifest__.py`, `plasticos_transaction/migrations/19.0.2.3.52/post-migrate.py`, `AGENTS.md`, `docs/campaigns/11-03-26/PlasticOS_Native_Opportunity_Canonical_Plan_2026-11-02 2/evidence/FINDING_CONTINUITY.csv`
- **write_deny:** `plasticos_web_leads/models/web_lead.py`, `plasticos_documents/models/load_docs_bridge.py`, `plasticos_documents/business_rules/`, `plasticos_logistics/models/freight_estimate.py`, `plasticos_logistics/models/freight_governance.py`, `plasticos_logistics/models/freight_quote.py`, `plasticos_logistics/models/load.py`, `plasticos_logistics/business_rules/`, `Gate/CEG/EIE repositories`, `production and deployed Staging databases`, `live mail and live orders`, `secrets`
- **delete_allow:** none — no Delete todo

### Commands

- **allow:** `make test-module m=plasticos_crm_bridge`, `make test-module m=plasticos_matching`, `make test-module m=plasticos_offer`, `make test-module m=plasticos_transaction`, `python3 scripts/check_module_wiring.py`, `python3 ci/check_circular_deps.py`, `ruff check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction`, `ruff format --check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction`, `.pre-commit-config.yaml`, `python3 scripts/check_module_wiring.py && python3 ci/check_circular_deps.py`, `ruff check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction && ruff format --check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction && test -f .pre-commit-config.yaml`
- **deny:** `git push --force`, `git reset --hard`, admin merge, committing secrets

### Network

| Field | Value |
|-------|-------|
| mode | `named_services_only` |
| allowed_services | `local docker compose`, `postgres fixture odoo_test_tpl_ee_c9e8a81f52f23680`, `Gate client already configured on that fixture` |

### Secrets

| Field | Value |
|-------|-------|
| access | `runtime_injected_only` |
| redaction_required | `true` |

### Autonomous merge

`autonomous_merge:` `false` always. This plan confers no merge authority.

### Preserved contracts

- Native crm.lead type opportunity is the pursuit owner and Facility is optional
- New fields are only those in contracts/SCHEMA_APPROVAL_2026-11-04.md
- Gate remains the only matcher and the direction stays supply_opportunity_to_buyer_facility
- sale.order.opportunity_id is the order binding and sale.order.action_confirm remains the transaction compiler
- Historical rows stay readable and are not backfilled with guessed lineage
- Web-lead write guards, partner deferral, and _find_or_create_partner stay unchanged

## Side effects and idempotency

Required for every destructive / external-write TODO (PLAN-SCHEMA-005). One row per todo.

| todo_id | side_effects | idempotency | retry | compensation | irreversible |
|---------|--------------|-------------|-------|--------------|--------------|
| T02 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_crm_bridge/models/opportunity_approval.py plasticos_crm_bridge/models/__init__.py plasticos_crm_bridge/security/ir.model.access.csv plasticos_crm_bridge/__manifest__.py plasticos_crm_bridge/migrations/19.0.3.4.20/post-migrate.py plasticos_crm_bridge/tests/__init__.py plasticos_crm_bridge/tests/test_opportunity_approval.py` | `false` |
| T03 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_crm_bridge/models/match_lineage.py plasticos_crm_bridge/models/__init__.py plasticos_crm_bridge/__manifest__.py plasticos_matching/models/match_run.py plasticos_matching/models/match_result.py plasticos_matching/models/match_result_link.py plasticos_matching/__manifest__.py plasticos_matching/migrations/19.0.3.1.5/post-migrate.py` | `false` |
| T04 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_crm_bridge/models/crm_lead.py plasticos_crm_bridge/models/web_lead.py plasticos_crm_bridge/models/crm_lead_vanillasoft.py plasticos_crm_bridge/views/crm_lead_views.xml plasticos_crm_sync/services/orchestrator.py plasticos_crm_sync/__manifest__.py plasticos_crm_sync/migrations/19.0.1.9.19/post-migrate.py plasticos_intake/models/res_partner_intake.py plasticos_intake/models/material_profile_intake.py` | `false` |
| T05 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_matching/models/match_orchestrator.py plasticos_matching/models/match_result_writer.py plasticos_matching/models/intake_extension.py plasticos_matching/__manifest__.py plasticos_gate/services/gate_builders.py plasticos_gate/services/gate_mappers.py plasticos_gate/__manifest__.py plasticos_gate/migrations/19.0.1.9.7/post-migrate.py` | `false` |
| T06 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_offer/models/offer.py plasticos_offer/models/intake_offers_bridge.py plasticos_offer/models/offer_price_bridge.py plasticos_offer/wizards/offer_bulk_action_wizard.py plasticos_offer/__manifest__.py plasticos_offer/migrations/19.0.1.1.3/post-migrate.py plasticos_matching/models/match_result.py` | `false` |
| T07 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_crm_bridge/models/crm_lead.py plasticos_transaction/models/offer_bridge.py plasticos_transaction/models/sale_inherit.py plasticos_transaction/__manifest__.py plasticos_transaction/migrations/19.0.2.3.52/post-migrate.py` | `false` |
| T09 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_crm_bridge/views/crm_lead_views.xml plasticos_matching/views/match_run_views.xml plasticos_matching/views/match_result_views.xml plasticos_offer/views/offer_views.xml` | `false` |
| T08 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_crm_bridge/tests/test_opportunity_migration.py plasticos_crm_bridge/tests/__init__.py` | `false` |
| T10 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- AGENTS.md docs/campaigns/11-03-26/PlasticOS_Native_Opportunity_Canonical_Plan_2026-11-02 2/evidence/FINDING_CONTINUITY.csv` | `false` |

## Architecture impact

| todo_id | bounded_context | layer | owning_contract | prohibited |
|---------|-----------------|-------|-----------------|------------|
| T02 | `plasticos_crm_bridge` | `data_plane` | `Native crm.lead type opportunity is the pursuit owner and Facility is optional`, `New fields are only those in contracts/SCHEMA_APPROVAL_2026-11-04.md`, `Gate remains the only matcher and the direction stays supply_opportunity_to_buyer_facility`, `sale.order.opportunity_id is the order binding and sale.order.action_confirm remains the transaction compiler`, `Historical rows stay readable and are not backfilled with guessed lineage`, `Web-lead write guards, partner deferral, and _find_or_create_partner stay unchanged` | `plasticos_web_leads/models/web_lead.py`, `plasticos_documents/models/load_docs_bridge.py`, `plasticos_logistics/models/freight_estimate.py`, `plasticos_logistics/models/freight_governance.py`, `plasticos_logistics/models/freight_quote.py`, `plasticos_logistics/models/load.py`, `Gate/CEG/EIE repositories`, `production and deployed Staging databases`, `live mail and live orders`, `secrets` |
| T03 | `repository root` | `data_plane` | `Native crm.lead type opportunity is the pursuit owner and Facility is optional`, `New fields are only those in contracts/SCHEMA_APPROVAL_2026-11-04.md`, `Gate remains the only matcher and the direction stays supply_opportunity_to_buyer_facility`, `sale.order.opportunity_id is the order binding and sale.order.action_confirm remains the transaction compiler`, `Historical rows stay readable and are not backfilled with guessed lineage`, `Web-lead write guards, partner deferral, and _find_or_create_partner stay unchanged` | `plasticos_web_leads/models/web_lead.py`, `plasticos_documents/models/load_docs_bridge.py`, `plasticos_logistics/models/freight_estimate.py`, `plasticos_logistics/models/freight_governance.py`, `plasticos_logistics/models/freight_quote.py`, `plasticos_logistics/models/load.py`, `Gate/CEG/EIE repositories`, `production and deployed Staging databases`, `live mail and live orders`, `secrets` |
| T04 | `repository root` | `data_plane` | `Native crm.lead type opportunity is the pursuit owner and Facility is optional`, `New fields are only those in contracts/SCHEMA_APPROVAL_2026-11-04.md`, `Gate remains the only matcher and the direction stays supply_opportunity_to_buyer_facility`, `sale.order.opportunity_id is the order binding and sale.order.action_confirm remains the transaction compiler`, `Historical rows stay readable and are not backfilled with guessed lineage`, `Web-lead write guards, partner deferral, and _find_or_create_partner stay unchanged` | `plasticos_web_leads/models/web_lead.py`, `plasticos_documents/models/load_docs_bridge.py`, `plasticos_logistics/models/freight_estimate.py`, `plasticos_logistics/models/freight_governance.py`, `plasticos_logistics/models/freight_quote.py`, `plasticos_logistics/models/load.py`, `Gate/CEG/EIE repositories`, `production and deployed Staging databases`, `live mail and live orders`, `secrets` |
| T05 | `repository root` | `data_plane` | `Native crm.lead type opportunity is the pursuit owner and Facility is optional`, `New fields are only those in contracts/SCHEMA_APPROVAL_2026-11-04.md`, `Gate remains the only matcher and the direction stays supply_opportunity_to_buyer_facility`, `sale.order.opportunity_id is the order binding and sale.order.action_confirm remains the transaction compiler`, `Historical rows stay readable and are not backfilled with guessed lineage`, `Web-lead write guards, partner deferral, and _find_or_create_partner stay unchanged` | `plasticos_web_leads/models/web_lead.py`, `plasticos_documents/models/load_docs_bridge.py`, `plasticos_logistics/models/freight_estimate.py`, `plasticos_logistics/models/freight_governance.py`, `plasticos_logistics/models/freight_quote.py`, `plasticos_logistics/models/load.py`, `Gate/CEG/EIE repositories`, `production and deployed Staging databases`, `live mail and live orders`, `secrets` |
| T06 | `repository root` | `data_plane` | `Native crm.lead type opportunity is the pursuit owner and Facility is optional`, `New fields are only those in contracts/SCHEMA_APPROVAL_2026-11-04.md`, `Gate remains the only matcher and the direction stays supply_opportunity_to_buyer_facility`, `sale.order.opportunity_id is the order binding and sale.order.action_confirm remains the transaction compiler`, `Historical rows stay readable and are not backfilled with guessed lineage`, `Web-lead write guards, partner deferral, and _find_or_create_partner stay unchanged` | `plasticos_web_leads/models/web_lead.py`, `plasticos_documents/models/load_docs_bridge.py`, `plasticos_logistics/models/freight_estimate.py`, `plasticos_logistics/models/freight_governance.py`, `plasticos_logistics/models/freight_quote.py`, `plasticos_logistics/models/load.py`, `Gate/CEG/EIE repositories`, `production and deployed Staging databases`, `live mail and live orders`, `secrets` |
| T07 | `repository root` | `data_plane` | `Native crm.lead type opportunity is the pursuit owner and Facility is optional`, `New fields are only those in contracts/SCHEMA_APPROVAL_2026-11-04.md`, `Gate remains the only matcher and the direction stays supply_opportunity_to_buyer_facility`, `sale.order.opportunity_id is the order binding and sale.order.action_confirm remains the transaction compiler`, `Historical rows stay readable and are not backfilled with guessed lineage`, `Web-lead write guards, partner deferral, and _find_or_create_partner stay unchanged` | `plasticos_web_leads/models/web_lead.py`, `plasticos_documents/models/load_docs_bridge.py`, `plasticos_logistics/models/freight_estimate.py`, `plasticos_logistics/models/freight_governance.py`, `plasticos_logistics/models/freight_quote.py`, `plasticos_logistics/models/load.py`, `Gate/CEG/EIE repositories`, `production and deployed Staging databases`, `live mail and live orders`, `secrets` |
| T09 | `repository root` | `data_plane` | `Native crm.lead type opportunity is the pursuit owner and Facility is optional`, `New fields are only those in contracts/SCHEMA_APPROVAL_2026-11-04.md`, `Gate remains the only matcher and the direction stays supply_opportunity_to_buyer_facility`, `sale.order.opportunity_id is the order binding and sale.order.action_confirm remains the transaction compiler`, `Historical rows stay readable and are not backfilled with guessed lineage`, `Web-lead write guards, partner deferral, and _find_or_create_partner stay unchanged` | `plasticos_web_leads/models/web_lead.py`, `plasticos_documents/models/load_docs_bridge.py`, `plasticos_logistics/models/freight_estimate.py`, `plasticos_logistics/models/freight_governance.py`, `plasticos_logistics/models/freight_quote.py`, `plasticos_logistics/models/load.py`, `Gate/CEG/EIE repositories`, `production and deployed Staging databases`, `live mail and live orders`, `secrets` |
| T08 | `plasticos_crm_bridge/tests` | `assurance` | `Native crm.lead type opportunity is the pursuit owner and Facility is optional`, `New fields are only those in contracts/SCHEMA_APPROVAL_2026-11-04.md`, `Gate remains the only matcher and the direction stays supply_opportunity_to_buyer_facility`, `sale.order.opportunity_id is the order binding and sale.order.action_confirm remains the transaction compiler`, `Historical rows stay readable and are not backfilled with guessed lineage`, `Web-lead write guards, partner deferral, and _find_or_create_partner stay unchanged` | `plasticos_web_leads/models/web_lead.py`, `plasticos_documents/models/load_docs_bridge.py`, `plasticos_logistics/models/freight_estimate.py`, `plasticos_logistics/models/freight_governance.py`, `plasticos_logistics/models/freight_quote.py`, `plasticos_logistics/models/load.py`, `Gate/CEG/EIE repositories`, `production and deployed Staging databases`, `live mail and live orders`, `secrets` |
| T10 | `repository root` | `docs` | `Native crm.lead type opportunity is the pursuit owner and Facility is optional`, `New fields are only those in contracts/SCHEMA_APPROVAL_2026-11-04.md`, `Gate remains the only matcher and the direction stays supply_opportunity_to_buyer_facility`, `sale.order.opportunity_id is the order binding and sale.order.action_confirm remains the transaction compiler`, `Historical rows stay readable and are not backfilled with guessed lineage`, `Web-lead write guards, partner deferral, and _find_or_create_partner stay unchanged` | `plasticos_web_leads/models/web_lead.py`, `plasticos_documents/models/load_docs_bridge.py`, `plasticos_logistics/models/freight_estimate.py`, `plasticos_logistics/models/freight_governance.py`, `plasticos_logistics/models/freight_quote.py`, `plasticos_logistics/models/load.py`, `Gate/CEG/EIE repositories`, `production and deployed Staging databases`, `live mail and live orders`, `secrets` |

## Rollback

`schema_ref:` `canonical.schema.rollback_contract.v1`
`instance_binding:` `rollback_contract_ref` → `rollback.plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1`

| Field | Value |
|-------|-------|
| rollback_id | `rollback.plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1` |
| source_execution_ref | `plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1` |
| supported | `true` |
| automatic_allowed | `false` |
| approval_required | `false` |
| trigger_conditions | CP1 fails (New fields match contracts/SCHEMA_APPROVAL_2026-11-04.md and the manifest DAG has no cycle) → Stop writes and restore the scoped paths; CP2 fails (V1 V2 and V3 pass, including a match with no facility) → Repair the owning module and do not add a local scorer; CP3 fails (V4 V5 and V6 pass on the Enterprise fixture clone) → Leave live mail and live orders untouched; CP4 fails (V7 passes and finding rows name the fixture result) → Do not publish |

### Strategies (typed — PLAN-SCHEMA-009)

| domain | mode | notes |
|--------|------|-------|
| code | `git_restore_scoped_paths` | git restore the files listed on the failed todo. Database rollback uses the fixture clone from before the module upgrade. Do not restore over unrelated dirty logistics or documents files, and do not replay mail or confirm live orders. |
| data | `none` | PLAN_DOCUMENT declares no data mutation |
| external_state | `none` | PLAN_DOCUMENT declares no external write |
| local_state | `git_restore_scoped_paths` | scoped to todo files |

### Irreversible operations

- none — no todo is marked `irreversible` (PLAN-SCHEMA-010)

### Rollback verification

- re-run `make test-module m=plasticos_crm_bridge`
- re-run `make test-module m=plasticos_matching`
- re-run `make test-module m=plasticos_offer`
- re-run `make test-module m=plasticos_transaction`
- re-run `python3 scripts/check_module_wiring.py`
- re-run `python3 ci/check_circular_deps.py`
- re-run `ruff check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction`
- re-run `ruff format --check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction`
- re-run `.pre-commit-config.yaml`
- re-run `python3 scripts/check_module_wiring.py && python3 ci/check_circular_deps.py`
- re-run `ruff check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction && ruff format --check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction && test -f .pre-commit-config.yaml`

## Complexity and uncertainty

| Field | Value |
|-------|-------|
| complexity | `high` — highest todo risk across 9 todo(s) |
| uncertainty | `medium` — 5 unknown(s), 0 blocking |
| blast_radius | `high` — Partner identity, material approval, match receipts, private offers, sale orders, historical transactions, mail obligations, and multi-company visibility. |
| architectural_boundaries_crossed | `plasticos_crm_bridge`, `plasticos_matching`, `plasticos_gate`, `plasticos_offer`, `plasticos_transaction` |
| external_systems_touched | `Odoo sale_crm`, `existing Gate match client` |
| migration_required | `true` |
| unknown_dependency_count | `5` |

## Inventory and classification *(optional — activate if retire/migrate/replace)*

Not activated — PLAN_DOCUMENT declares no retire / migrate / replace inventory.

## Gated write pipeline *(optional — irreversible or external writes)*

Not activated — PLAN_DOCUMENT declares no irreversible or external write.

## Regeneration extinguishment *(optional — retirement/deprecation)*

Not activated — PLAN_DOCUMENT declares no retirement or deprecation.

## Execution DAG

`schema_ref:` `canonical.schema.dependency_topology.v1`
`instance_binding:` `dependency_topology_ref` → `dag.plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1`
Must be acyclic before status may become `executable` (PLAN-SCHEMA-007).

| Field | Value |
|-------|-------|
| topology_id | `dag.plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1` |
| topology_kind | `execution` |
| graph_type | `directed_acyclic_graph` |

### Nodes / edges

| id | task | owner | risk | effort | depends_on | outputs |
|----|------|-------|------|--------|------------|---------|
| T02 | Add plasticos.opportunity.approval in CRM Bridge with the approved fields, unprefixed ACL rows, version 19.0.3.4.20, and a server-minted immutable create path. | Cursor Build agent | `high` | M | `[]` | `plasticos_crm_bridge/models/opportunity_approval.py`, `plasticos_crm_bridge/models/__init__.py`, `plasticos_crm_bridge/security/ir.model.access.csv`, `plasticos_crm_bridge/__manifest__.py`, `plasticos_crm_bridge/migrations/19.0.3.4.20/post-migrate.py`, `plasticos_crm_bridge/tests/__init__.py`, `plasticos_crm_bridge/tests/test_opportunity_approval.py` |
| T03 | Add opportunity_id and approval_id on the match run, match_result_id on the offer, optional restrict intake links, and the partial uniqueness rules from the 2026-11-04 ledger. | Cursor Build agent | `high` | M | `[T02]` | `plasticos_crm_bridge/models/match_lineage.py`, `plasticos_crm_bridge/models/__init__.py`, `plasticos_crm_bridge/__manifest__.py`, `plasticos_matching/models/match_run.py`, `plasticos_matching/models/match_result.py`, `plasticos_matching/models/match_result_link.py`, `plasticos_matching/__manifest__.py`, `plasticos_matching/migrations/19.0.3.1.5/post-migrate.py` |
| T04 | Send HOT, manual, and VanillaSoft ingress to a verified Partner, Material Profile, and native Opportunity without creating a synthetic Intake or Facility. | Cursor Build agent | `high` | M | `[T02, T03]` | `plasticos_crm_bridge/models/crm_lead.py`, `plasticos_crm_bridge/models/web_lead.py`, `plasticos_crm_bridge/models/crm_lead_vanillasoft.py`, `plasticos_crm_bridge/views/crm_lead_views.xml`, `plasticos_crm_sync/services/orchestrator.py`, `plasticos_crm_sync/__manifest__.py`, `plasticos_crm_sync/migrations/19.0.1.9.19/post-migrate.py`, `plasticos_intake/models/res_partner_intake.py`, `plasticos_intake/models/material_profile_intake.py` |
| T05 | Build the Gate request from the frozen approval, keep one Gate orchestrator, and omit facility evidence when it is absent. | Cursor Build agent | `high` | M | `[T02, T03]` | `plasticos_matching/models/match_orchestrator.py`, `plasticos_matching/models/match_result_writer.py`, `plasticos_matching/models/intake_extension.py`, `plasticos_matching/__manifest__.py`, `plasticos_gate/services/gate_builders.py`, `plasticos_gate/services/gate_mappers.py`, `plasticos_gate/__manifest__.py`, `plasticos_gate/migrations/19.0.1.9.7/post-migrate.py` |
| T06 | Create idempotent unsent offers from reviewed current results, keep terms immutable, and record one explicit commercial winner. | Cursor Build agent | `high` | M | `[T04, T05]` | `plasticos_offer/models/offer.py`, `plasticos_offer/models/intake_offers_bridge.py`, `plasticos_offer/models/offer_price_bridge.py`, `plasticos_offer/wizards/offer_bulk_action_wizard.py`, `plasticos_offer/__manifest__.py`, `plasticos_offer/migrations/19.0.1.1.3/post-migrate.py`, `plasticos_matching/models/match_result.py` |
| T07 | On acceptance, create or reuse one draft sale.order with native opportunity_id and the offer sell terms, then leave confirmation to the existing transaction compiler. | Cursor Build agent | `high` | M | `[T06]` | `plasticos_crm_bridge/models/crm_lead.py`, `plasticos_transaction/models/offer_bridge.py`, `plasticos_transaction/models/sale_inherit.py`, `plasticos_transaction/__manifest__.py`, `plasticos_transaction/migrations/19.0.2.3.52/post-migrate.py` |
| T09 | Expose the Opportunity, Run, Result, and Offer lineage in the existing views without a second matching command. | Cursor Build agent | `medium` | S | `[T07]` | `plasticos_crm_bridge/views/crm_lead_views.xml`, `plasticos_matching/views/match_run_views.xml`, `plasticos_matching/views/match_result_views.xml`, `plasticos_offer/views/offer_views.xml` |
| T08 | Run the Enterprise fixture migration and module suites, including interruption and a two-company visibility check, on a clone of odoo_test_tpl_ee_c9e8a81f52f23680. | Cursor Build agent | `high` | M | `[T09]` | `plasticos_crm_bridge/tests/test_opportunity_migration.py`, `plasticos_crm_bridge/tests/__init__.py` |
| T10 | Append the native Opportunity correction to AGENTS.md and record finding continuity against the final fixture result. | Cursor Build agent | `medium` | S | `[T08]` | `AGENTS.md`, `docs/campaigns/11-03-26/PlasticOS_Native_Opportunity_Canonical_Plan_2026-11-02 2/evidence/FINDING_CONTINUITY.csv` |

**Critical path:** T02 → T03 → T04 → T06 → T07 → T09 → T08 → T10

**Forbidden edges:** any edge not listed above; any todo writing outside `write_allow`.

### Milestones

| id | outcome | unlocks |
|----|---------|---------|
| M1 | Approval model and lineage fields match the 2026-11-04 ledger | T04 and T05 |
| M2 | Both ingress routes share one Gate match command and one offer path | T07 |
| M3 | Enterprise fixture suites and the migration check pass | T10 |
| M4 | AGENTS correction and finding continuity are recorded | Separate publication decision |

### Checkpoints

| id | after | evidence_required | no_go_action |
|----|-------|-------------------|--------------|
| CP1 | M1 | New fields match contracts/SCHEMA_APPROVAL_2026-11-04.md and the manifest DAG has no cycle | Stop writes and restore the scoped paths |
| CP2 | M2 | V1 V2 and V3 pass, including a match with no facility | Repair the owning module and do not add a local scorer |
| CP3 | M3 | V4 V5 and V6 pass on the Enterprise fixture clone | Leave live mail and live orders untouched |
| CP4 | M4 | V7 passes and finding rows name the fixture result | Do not publish |

### Leverage

- **Ranked todos:** `T02`, `T03`, `T04`, `T05`, `T06`, `T07`, `T09`, `T08`, `T10`
- **Shared causes:** Intake is still the required commercial root; Run and Offer lack Opportunity and Result lineage; The web-lead snapshot cannot serve a manual Opportunity
- **Deletions / consolidations:** Retire the separate Lead prospect lifecycle as the ingress; Remove synthetic Intake and Facility creation from the manual route; Retire selected-line and typical-price authority for offer creation

### Doc / root surface impact

| surface | action | todo_ids | reason |
|---------|--------|----------|--------|
| AGENTS.md | `update` | `T10` | Append that the commercial pursuit owner is the native Opportunity and that Facility is optional |
| Gate SDK repositories | `n_a` | — | No Gate repository write is authorized |

## Property evidence matrix

`schema_ref:` `canonical.schema.validation_evidence.v1`
`instance_binding:` `validation_evidence_refs` / `property_evidence_matrix_ref`
Exit-0 alone is insufficient when property needs structural/runtime proof (PLAN-SCHEMA-008).

| evidence_id | claim_id / SP | evidence_kind | method | command | expected_positive | status |
|-------------|---------------|---------------|--------|---------|-------------------|--------|
| E-V1 | SP-01 | `quality_gate_evidence` | command | `make test-module m=plasticos_crm_bridge` | HOT and manual admission tests pass, including two lots for one partner and profile and no synthetic intake | `not_run` |
| E-V2 | SP-02 | `quality_gate_evidence` | command | `make test-module m=plasticos_matching` | A run with no facility is accepted, empty scores stay empty, and the request matches the frozen approval | `not_run` |
| E-V3 | SP-03 | `quality_gate_evidence` | command | `make test-module m=plasticos_offer` | Two reviewed results create two unsent drafts and a second acceptance does not create a second winner | `not_run` |
| E-V4 | SP-04 | `quality_gate_evidence` | command | `make test-module m=plasticos_transaction` | The draft sale order uses opportunity_id, confirmation compiles one transaction, and no Won flag is set from acceptance alone | `not_run` |
| E-V5 | SP-05 | `quality_gate_evidence` | command | `make test-module m=plasticos_crm_bridge` | Historical rows remain readable, null intake is allowed, and source intake uniqueness does not collapse manual lots | `not_run` |
| E-V6 | SP-06 | `quality_gate_evidence` | command | `python3 scripts/check_module_wiring.py && python3 ci/check_circular_deps.py` | CRM Bridge may depend on Matching and Offer. Matching does not depend on CRM Bridge. No cycle is reported. | `not_run` |
| E-V7 | SP-06 | `quality_gate_evidence` | command | `ruff check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction && ruff format --check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction && test -f .pre-commit-config.yaml` | Ruff reports no findings on the touched modules and the hook catalog file is present | `not_run` |

## Stress and disconfirm

### Disconfirming cases

- Can a manual Opportunity match with no Intake and no Facility without a hidden adapter creating either?
- Can a later Material Profile edit rewrite an approved lot or an offered term?
- Does a missing score or a missing facility become zero or a fabricated location?
- Can the same source intake create two Opportunities while two manual lots collapse into one?
- Does CRM Bridge depending on Matching, or Matching depending on CRM Bridge, create a cycle?
- Can an existing purchase-only or sale-only order still compile and mail without this pipeline?
- Can a heading-only green hide a missing Enterprise fixture result?

### Assumption failure conditions

- The 2026-11-02 architecture note is treated as field approval
- HOT triage is treated as partner and material approval
- request_fingerprint is treated as the reconstructable request
- A draft plan status is treated as proof that V1-V7 already passed
- Supply matching is silently treated as demand matching

### Blast radius notes

- Partner identity, material approval, match receipts, private offers, sale orders, historical transactions, mail obligations, and multi-company visibility.

### Rollback constraints

- git restore the files listed on the failed todo. Database rollback uses the fixture clone from before the module upgrade. Do not restore over unrelated dirty logistics or documents files, and do not replay mail or confirm live orders.

### Risks

| risk | mitigation |
|------|------------|
| A field outside the ledger is added during Build | CP1 compares the diff with contracts/SCHEMA_APPROVAL_2026-11-04.md |
| Matching depends on CRM Bridge and the manifest DAG cycles | Lineage fields stay in CRM Bridge, which gains the Matching dependency |
| Historical rows fail the new required flags or uniqueness | New links are not SQL-required, and the new unique indexes are partial |
| sale_crm is absent on the fixture clone | V4 asserts sale.order.opportunity_id before creating a quotation and stops if the field is missing |

## What belongs with logistics and is not installed

BRS-POS-10 is the Native-First chapter whose owner is plasticos_logistics plus Odoo Mail. The chapter file is `plasticos_logistics/business_rules/BRS-POS-10-linda-logistics-commercial-and-physical-communication.md`. Its status is frozen working BRS, pending independent repository adoption. Implementation evidence on that file is NOT_RUN. Build does not edit it.

BRS-POS-09 was kept inside Documents even though its owner line includes Linda external mail. The rules that are actually Linda behavior are the single external reminder writer, the supplier/carrier/buyer clocks, the one-touch-per-day rule, and quiet hours (BRS-POS-09-R006 through R012). Documents OWNERSHIP_AND_INTEROP.md already says only Linda sends the external chase.

These should not move into logistics:

- BRS-POS-04 is commercial weight, owned by transaction/commercial.
- BRS-POS-05 is native stock, owned by Inventory, Purchase, and Sales.
- BRS-POS-06 through BRS-POS-08 are purchase, sales, claims, and accounting.
- BRS-POS-11 and BRS-POS-12 are security and sequencing.

## Recursive alignment 2026-11-05

Kernel: `.cursor-commands/kernels/Recursive Alignment.md` v1.0. The kernel stays audit-only. This section is the authorized correction of this plan.

```yaml
audit_status: PartiallySucceeded
readiness_status: NotReady
convergence_status: Partial
target_binding:
  root: docs/campaigns/11-03-26/PLAN Partners First Native Opportunity Matching Canonical Revision.md
  artifact_type: implementation_plan
  revision: 2026-11-05 rebaseline to origin/Staging c8e7efebb03d79e3a5b220b8a7568a750918b2ed
  planning_checkout: docs/brs-documents-logistics-ownership 8f599abf41d3b3e5dc7e9aa8d11a42c0b6cecad4
authorized_scope: "Correct this plan's baseline, logistics claim, probes, write_deny, out_of_scope, and publication handoff."
excluded_scope: "T02-T10 implementation, stash pop, schema-ledger admission, kernel edits, make pr."
source_authority_used:
  - source: .cursor-commands/kernels/Recursive Alignment.md
    precedence: audit output contract
    scope: this plan
  - source: scripts/pr_stack_parent.sh
    precedence: publication base
    scope: make pr destination Staging
  - source: .cursor-commands/ops/scripts/agent_worktree_start.sh
    precedence: worktree ancestry
    scope: explicit --base origin/Staging with L9_TASK_BASE_AUTHORIZED
  - source: origin/Staging c8e7efebb03d79e3a5b220b8a7568a750918b2ed
    precedence: integration commit
    scope: execution baseline
  conflicts: "PR_STACK=auto resolves pull requests into main. PlasticOS publication targets Staging. Sibling Staging pull requests have no unique stack tip."
architecture_adapters:
  - id: plasticos_publication
    name: make pr into Staging
    version: scripts/pr_stack_parent.sh
    governing_source: scripts/git_push_with_pr.sh
    status: Applied
    scope: publication handoff
  - id: recursive_alignment
    name: recursive_architecture_alignment_auditor
    version: "1.0"
    governing_source: .cursor-commands/kernels/Recursive Alignment.md
    status: Applied
    scope: this plan document
normalized_context: "Historical execution SHA 7d23e632 is not an ancestor of origin/Staging. Local Staging is 4a6af0b and is 36 commits behind. The schema ledger is only in stash@{5}."
artifact_inventory:
  - docs/campaigns/11-03-26/PLAN Partners First Native Opportunity Matching Canonical Revision.md
  - plasticos_crm_bridge/__manifest__.py version 19.0.3.4.19
  - plasticos_offer/models/offer.py commented match_result_id
  - plasticos_logistics/business_rules/BRS-POS-10-linda-logistics-commercial-and-physical-communication.md
boundary_map:
  workflow_owner: plasticos_crm_bridge
  publication_owner: make pr into Staging
  field_authority: contracts/SCHEMA_APPROVAL_2026-11-04.md
  field_authority_status: absent from the branch
  logistics_brs_owner: plasticos_logistics/business_rules
  documents_brs_owner: plasticos_documents/business_rules
alignment_summary: "Baseline and publication handoff now name fetched origin/Staging and plain make pr. P2 remains failed, so the feature build is not executable."
alignment_score:
  overall: Partial
  warning: "Score does not override the P2 release blocker."
  domains:
    intent_and_scope: Partial
    communication_contracts: Partial
    routing_and_integration: Partial
    authority_boundary: Passed
    structure_and_source_of_truth: Partial
    schema_and_configuration: Failed
    security: NotApplicable
    reliability_observability: Unknown
    testing_validation: Failed
  excluded_domains: []
critical_violations: []
high_violations:
  - id: P2_LEDGER_ABSENT
    root_cause: "contracts/SCHEMA_APPROVAL_2026-11-04.md is not on the branch."
    evidence: "Only untracked copy is inside stash@{5}."
    status: open
medium_violations: []
low_violations: []
unknowns:
  - id: P3
    why: "sale_crm and the fixture file were not re-read in this revision."
    affected: "P3 stays unverified."
    evidence_needed: "Read sale_crm and config/test_env_fixture.conf on the execution worktree."
  - id: P4
    why: "plan_memory_prefetch.py was not run in this revision."
    affected: "P4 stays unverified."
    evidence_needed: "Run the prefetch on the execution worktree and record the digest."
intent_and_scope_compliance:
  status: Partial
  governing_rules: "Feature scope stays T02-T10. BRS chapters stay out of scope."
  evidence: "Out of scope and write_deny now name both business_rules trees."
  open_violations: [P2_LEDGER_ABSENT]
  closing_validation: "Admit the schema ledger, then re-run P2."
communication_contract_compliance:
  status: Partial
  governing_rules: "make pr publishes into Staging. PR_STACK=auto is not the PlasticOS base resolver."
  evidence: "Execute banner and machine stub command_ref now say make pr with no PR_STACK."
  open_violations: []
  closing_validation: "A later Build displays the pull request URL."
routing_and_integration_compliance:
  status: Partial
  governing_rules: "agent_worktree_start.sh --base origin/Staging with L9_TASK_BASE_AUTHORIZED."
  evidence: "Historical 7d23e632 and local Staging are refused in P0."
  open_violations: []
  closing_validation: "P0 on the clean worktree."
authority_boundary_compliance:
  status: Passed
  governing_rules: "scripts/pr_stack_parent.sh accepts Staging and refuses main and Production."
  evidence: "Handoff does not stack onto docs/brs-documents-logistics-ownership."
  open_violations: []
  closing_validation: "make pr with no base override."
structure_and_source_of_truth_compliance:
  status: Partial
  governing_rules: "BRS-POS-10 file is the logistics chapter. It is frozen pending adoption."
  evidence: "plasticos_logistics/business_rules/BRS-POS-10-linda-logistics-commercial-and-physical-communication.md exists. Evidence on that file is NOT_RUN."
  open_violations: []
  closing_validation: "Build does not edit business_rules."
schema_and_configuration_compliance:
  status: Failed
  governing_rules: "P2 requires S1-S5 on the branch."
  evidence: "contracts/SCHEMA_APPROVAL_2026-11-04.md is absent."
  open_violations: [P2_LEDGER_ABSENT]
  closing_validation: "Place the ledger on the branch without popping the rest of the stash."
security_compliance:
  status: NotApplicable
  governing_rules: "This revision does not change ACL or secrets."
  evidence: "write_deny still includes secrets and live databases."
  open_violations: []
  closing_validation: "None for this revision."
reliability_observability_compliance:
  status: Unknown
  governing_rules: "P3 and P4 were previously marked passed without a fresh read."
  evidence: "Both probes are unverified."
  open_violations: []
  closing_validation: "Re-run P3 and P4 on the execution worktree."
testing_validation_compliance:
  status: Failed
  governing_rules: "V1-V7 stay not_run. Draft status is not proof."
  evidence: "No Enterprise fixture suite was run in this revision."
  open_violations: [P2_LEDGER_ABSENT]
  closing_validation: "V1-V7 after the ledger is admitted and T02-T10 are implemented."
overbuilt_vs_underbuilt:
  overbuilt: "PR_STACK=auto on a Staging-only board. Removed from the handoff."
  underbuilt: "Schema ledger is not on the branch, so field authority is not enforceable."
  speculative: []
  simplest_correction: "Admit contracts/SCHEMA_APPROVAL_2026-11-04.md, then Build from fetched origin/Staging."
leverage_analysis: "One publication path, plain make pr from a clean origin/Staging worktree, removes the resolver failure. The ledger remains the feature blocker."
correction_roadmap:
  - id: rebaseline
    owner: this revision
    status: applied
    affected: "overview, metadata, mission, immutable baseline, P0"
    closing_validation: "P0 on the clean worktree"
  - id: publication_handoff
    owner: this revision
    status: applied
    affected: "execute banner, Execute via Cursor Build, convergence next, machine stub command_ref"
    closing_validation: "make pr URL"
  - id: logistics_claim
    owner: this revision
    status: applied
    affected: "logistics section, write_deny, out_of_scope"
    closing_validation: "Build diff does not touch business_rules"
  - id: admit_schema_ledger
    owner: follow-on before Build
    status: not_performed
    prerequisite: "Recover only the ledger file. Do not pop stash@{5}."
    affected: contracts/SCHEMA_APPROVAL_2026-11-04.md
    risk: "Building without S1-S5 invents fields."
    expected_value: "P2 can pass and status can become executable."
    closing_validation: "P2 read of the ledger on the branch"
minimum_safe_next_action:
  action: "Admit contracts/SCHEMA_APPROVAL_2026-11-04.md onto the branch, then Build in a clean worktree of fetched origin/Staging and publish with make pr."
  rationale: "The publication ceremony is legal. The feature build is still blocked on the ledger."
  resolves: P2_LEDGER_ABSENT
  expected_evidence: "Ledger file on the branch, then a pull request URL after Build."
validation_gates:
  - id: P2
    status: failed
  - id: V1
    status: not_run
  - id: V2
    status: not_run
  - id: V3
    status: not_run
  - id: V4
    status: not_run
  - id: V5
    status: not_run
  - id: V6
    status: not_run
  - id: V7
    status: not_run
residual_risks:
  - "origin/Staging may move before execution. P0 must be fetched again. baseline_verified stays false."
  - "P3 and P4 were not re-run."
convergence:
  completed_passes: ["baseline text", "publication handoff", "logistics file claim", "write_deny and out_of_scope"]
  skipped_passes:
    - pass: schema ledger admission
      reason: "Copying the stash file is outside this revision."
    - pass: V1-V7
      reason: "Feature code was not implemented."
  remaining: "Admit the ledger, then execute T02-T10 from fetched origin/Staging."
  evidence: "P2 failed. Status remains draft. No success property is marked passed."
```

## Out of scope

- Fields absent from contracts/SCHEMA_APPROVAL_2026-11-04.md
- plasticos_web_leads/models/web_lead.py
- Gate, CEG, and EIE repository writes, demand matching, and local scoring
- Production databases, deployed Staging, live mail, and live orders
- Community test parity
- Dirty logistics and documents files outside the envelope
- `plasticos_logistics/business_rules/` and `plasticos_documents/business_rules/`, including the frozen BRS-POS-10 chapter
- Moving BRS-POS-04, BRS-POS-05, BRS-POS-06 through BRS-POS-08, BRS-POS-11, or BRS-POS-12 into logistics
- Architecture redesign (unless plan_class + redesign_allowed)
- Force-push, hard-reset, admin-merge, secret exfil
- Weakening scanners / gates to obtain PASS
- Follow-on schema/platform evolution

## Follow-on milestone *(optional — keep separate; PLAN-SCHEMA-014)*

Not activated — PLAN_DOCUMENT declares no follow-on milestone; separate_plan_required `true` for any follow-on.

## Convergence

`schema_ref:` `canonical.schema.convergence_contract.v1`
`instance_binding:` `convergence_contract_ref` → `conv.plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1`
Convergence requires all blocking evidence + gates (PLAN-SCHEMA-015).

| Field | Value |
|-------|-------|
| convergence_id | `conv.plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1` |
| source_ref | `plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1` |
| current_state | `draft` |
| implementation_ready | `false` |

### Gates

- **executable_when:**
  - baseline locked + reverified
  - blocking capability probes pass
  - DAG acyclic
  - envelope + side-effect matrix complete for mutate todos
  - no blocking unknowns
- **complete_when:**
  - all blocking success-property evidence `passed`
  - rollback contract still valid / unused-or-verified
  - out_of_scope respected (diff hygiene)
- **blocking_conditions:**
  - `preflight_blocked`
  - envelope breach
  - baseline drift
  - failed blocking property

### Evidence

- **required_evidence_refs:** E-V1, E-V2, E-V3, E-V4, E-V5, E-V6, E-V7
- **observed_evidence_refs:** none
- **missing_evidence:** E-V1, E-V2, E-V3, E-V4, E-V5, E-V6, E-V7

### Blockers / unknowns

| kind | id | note | resolution |
|------|----|------|------------|
| `unknown` | S_APPROVAL | Which S1-S5 delta is approved? — Closed by contracts/SCHEMA_APPROVAL_2026-11-04.md | `accept_bounded` |
| `unknown` | R_INSTALLED | Which native draft-order binding exists? — Use sale.order.opportunity_id from sale_crm. Add no custom order field. | `accept_bounded` |
| `unknown` | R_GATE | Does the source contract admit a missing facility, and which direction is allowed? — Facility is omitted. Direction stays supply_opportunity_to_buyer_facility. | `accept_bounded` |
| `unknown` | R_RUNTIME | Which disposable runtime is authorized? — Enterprise fixture odoo_test_tpl_ee_c9e8a81f52f23680 only. Community parity stays refused. | `accept_bounded` |
| `unknown` | R_IDENTITY | Which identity key is stable? — Source conversion uses the approved crosswalk and one Opportunity per source intake. Manual lots use the selected partner and profile and are not collapsed. | `accept_bounded` |
| `open_blocker` | schema_ledger | contracts/SCHEMA_APPROVAL_2026-11-04.md is not on the branch. The only copy is untracked in stash@{5}. P2 failed. Status stays draft. | admit the ledger before Build |
| `open_blocker` | stop_reason | Planning unknowns that do not depend on the ledger are closed. Derived status stays draft until the ledger is on the branch and V1-V7 pass. | planning convergence `partial` |

### Next

| Field | Value |
|-------|-------|
| next_convergence_gate | `executable_when` |
| minimum_safe_next_action | Admit contracts/SCHEMA_APPROVAL_2026-11-04.md onto the branch. Then press **Build** in a clean worktree of fetched origin/Staging and publish with `make pr` with no `PR_STACK`. Display the PR URL. Do not free-form execute. |
| execute_via | Cursor Build from fetched origin/Staging; plain make pr; display PR URL |
| next_skill | Admit the schema ledger, then Build and make pr |
| broader_work_requires_separate_contract | `true` |

---

## Machine stub (optional YAML instance seed)

Projected from PLAN_DOCUMENT; keep in sync with the sections above.

```yaml
schema_id: "canonical.schema.plan_document.v1"
schema_version: "1.0.0"
metadata:
  plan_id: "plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1"
  name: "Partners First Native Opportunity Matching Canonical Revision"
  overview: "Realize the approved Partners-first native crm.lead Opportunity root from fetched origin/Staging c8e7efebb03d79e3a5b220b8a7568a750918b2ed. Qualified HOT evidence or a manual Partner plus Material Profile converges on one Opportunity matching command, with plasticos.opportunity.approval as the immutable lot, optional Facility, Run to Result to Offer lineage owned by plasticos_crm_bridge, and native sale.order.opportunity_id plus the existing Transaction compiler. The 2026-11-04 schema delta is the field authority once contracts/SCHEMA_APPROVAL_2026-11-04.md is on the branch. Runtime proofs V1-V7 stay pending. Status stays draft until that ledger is admitted."
  status: "draft"
  is_project: false
  owner: "igor_beylin"
architect_framing:
  planning_ssot: "PLAN_DOCUMENT"
  plan_class: "bounded_execution_contract"
  redesign_allowed: false
  follow_on_schema_evolution_separate: true
immutable_baseline:
  repository: "cryptoxdog/IB-Odoo_19"
  branch: "origin/Staging"
  commit_sha: "c8e7efebb03d79e3a5b220b8a7568a750918b2ed"
  historical_commit_sha: "7d23e632d8341424e4faae33a085c12fe7fbe6da"
  local_staging_sha: "4a6af0b2d5bbf8f16e4fa67baafe9d71e3b4f384"
  dirty: "false"
  baseline_verified: false
  drift_detected: true
  overlap_policy: "stop_if_dirty_overlaps_may_modify"
  verification_rule: "reverify_at_execution_start"
  on_drift: "stop_and_replan"
objective:
  mission: "Realize the approved Partners-first native crm.lead Opportunity root from fetched origin/Staging c8e7efebb03d79e3a5b220b8a7568a750918b2ed. Qualified HOT evidence or a manual Partner plus Material Profile converges on one Opportunity matching command, with plasticos.opportunity.approval as the immutable lot, optional Facility, Run to Result to Offer lineage owned by plasticos_crm_bridge, and native sale.order.opportunity_id plus the existing Transaction compiler. The 2026-11-04 schema delta is the field authority once contracts/SCHEMA_APPROVAL_2026-11-04.md is on the branch. Runtime proofs V1-V7 stay pending. Status stays draft until that ledger is admitted."
  success_properties:
    - id: "SP-01"
      property: "V1 proves HOT and manual routes use native Opportunity with verified Partner and Profile, source evidence optional, and independent approval snapshots."
      evidence_type: "quality_gate"
      proof: ["V1"]
      blocking: true
    - id: "SP-02"
      property: "V2 proves Facility is optional on the Gate request, Run, and Result, and missing optional evidence is omitted rather than fabricated."
      evidence_type: "quality_gate"
      proof: ["V2"]
      blocking: true
    - id: "SP-03"
      property: "V3 proves typed Result-to-Offer lineage, idempotent unsent drafts, human review, and one commercial winner."
      evidence_type: "quality_gate"
      proof: ["V3"]
      blocking: true
    - id: "SP-04"
      property: "V4 proves a native sale order with opportunity_id reaches the existing Transaction compiler, with independent purchase orders and truthful mail state."
      evidence_type: "quality_gate"
      proof: ["V4"]
      blocking: true
    - id: "SP-05"
      property: "V5 proves the nullability and partial-unique migration keeps historical rows visible and does not invent lineage."
      evidence_type: "quality_gate"
      proof: ["V5"]
      blocking: true
    - id: "SP-06"
      property: "V6 and V7 prove the Enterprise fixture suites, manifest DAG, and .pre-commit-config.yaml owner gates after implementation."
      evidence_type: "quality_gate"
      proof: ["V6", "V7"]
      blocking: true
capability_preflight_ref: "preflight.plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1"
execution_envelope:
  filesystem:
    write_allow: ["plasticos_crm_bridge/models/opportunity_approval.py", "plasticos_crm_bridge/models/match_lineage.py", "plasticos_crm_bridge/models/__init__.py", "plasticos_crm_bridge/models/crm_lead.py", "plasticos_crm_bridge/models/web_lead.py", "plasticos_crm_bridge/models/crm_lead_vanillasoft.py", "plasticos_crm_bridge/views/crm_lead_views.xml", "plasticos_crm_bridge/security/ir.model.access.csv", "plasticos_crm_bridge/__manifest__.py", "plasticos_crm_bridge/migrations/19.0.3.4.20/post-migrate.py", "plasticos_crm_bridge/tests/__init__.py", "plasticos_crm_bridge/tests/test_opportunity_approval.py", "plasticos_crm_bridge/tests/test_opportunity_migration.py", "plasticos_matching/models/match_run.py", "plasticos_matching/models/match_result.py", "plasticos_matching/models/match_result_link.py", "plasticos_matching/models/match_orchestrator.py", "plasticos_matching/models/match_result_writer.py", "plasticos_matching/models/intake_extension.py", "plasticos_matching/views/match_run_views.xml", "plasticos_matching/views/match_result_views.xml", "plasticos_matching/__manifest__.py", "plasticos_matching/migrations/19.0.3.1.5/post-migrate.py", "plasticos_gate/services/gate_builders.py", "plasticos_gate/services/gate_mappers.py", "plasticos_gate/__manifest__.py", "plasticos_gate/migrations/19.0.1.9.7/post-migrate.py", "plasticos_crm_sync/services/orchestrator.py", "plasticos_crm_sync/__manifest__.py", "plasticos_crm_sync/migrations/19.0.1.9.19/post-migrate.py", "plasticos_intake/models/res_partner_intake.py", "plasticos_intake/models/material_profile_intake.py", "plasticos_offer/models/offer.py", "plasticos_offer/models/intake_offers_bridge.py", "plasticos_offer/models/offer_price_bridge.py", "plasticos_offer/wizards/offer_bulk_action_wizard.py", "plasticos_offer/views/offer_views.xml", "plasticos_offer/__manifest__.py", "plasticos_offer/migrations/19.0.1.1.3/post-migrate.py", "plasticos_transaction/models/offer_bridge.py", "plasticos_transaction/models/sale_inherit.py", "plasticos_transaction/__manifest__.py", "plasticos_transaction/migrations/19.0.2.3.52/post-migrate.py", "AGENTS.md", "docs/campaigns/11-03-26/PlasticOS_Native_Opportunity_Canonical_Plan_2026-11-02 2/evidence/FINDING_CONTINUITY.csv"]
    write_deny: ["plasticos_web_leads/models/web_lead.py", "plasticos_documents/models/load_docs_bridge.py", "plasticos_documents/business_rules/", "plasticos_logistics/models/freight_estimate.py", "plasticos_logistics/models/freight_governance.py", "plasticos_logistics/models/freight_quote.py", "plasticos_logistics/models/load.py", "plasticos_logistics/business_rules/", "Gate/CEG/EIE repositories", "production and deployed Staging databases", "live mail and live orders", "secrets"]
  commands:
    allow: ["make test-module m=plasticos_crm_bridge", "make test-module m=plasticos_matching", "make test-module m=plasticos_offer", "make test-module m=plasticos_transaction", "python3 scripts/check_module_wiring.py", "python3 ci/check_circular_deps.py", "ruff check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction", "ruff format --check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction", ".pre-commit-config.yaml", "python3 scripts/check_module_wiring.py && python3 ci/check_circular_deps.py", "ruff check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction && ruff format --check plasticos_crm_bridge plasticos_matching plasticos_offer plasticos_gate plasticos_crm_sync plasticos_transaction && test -f .pre-commit-config.yaml"]
  network:
    mode: "named_services_only"
  secrets:
    access: "runtime_injected_only"
    redaction_required: true
  autonomous_merge: false
side_effects_and_idempotency:
  - todo_id: "T02"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T03"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T04"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T05"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T06"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T07"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T09"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T08"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T10"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
rollback_contract_ref: "rollback.plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1"
dependency_topology_ref: "dag.plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1"
validation_evidence_refs: ["E-V1", "E-V2", "E-V3", "E-V4", "E-V5", "E-V6", "E-V7"]
stress_and_disconfirm:
  disconfirming_cases: ["Can a manual Opportunity match with no Intake and no Facility without a hidden adapter creating either?", "Can a later Material Profile edit rewrite an approved lot or an offered term?", "Does a missing score or a missing facility become zero or a fabricated location?", "Can the same source intake create two Opportunities while two manual lots collapse into one?", "Does CRM Bridge depending on Matching, or Matching depending on CRM Bridge, create a cycle?", "Can an existing purchase-only or sale-only order still compile and mail without this pipeline?", "Can a heading-only green hide a missing Enterprise fixture result?"]
  assumption_failure_conditions: ["The 2026-11-02 architecture note is treated as field approval", "HOT triage is treated as partner and material approval", "request_fingerprint is treated as the reconstructable request", "A draft plan status is treated as proof that V1-V7 already passed", "Supply matching is silently treated as demand matching"]
out_of_scope: ["Fields absent from contracts/SCHEMA_APPROVAL_2026-11-04.md", "plasticos_web_leads/models/web_lead.py", "Gate, CEG, and EIE repository writes, demand matching, and local scoring", "Production databases, deployed Staging, live mail, and live orders", "Community test parity", "Dirty logistics and documents files outside the envelope", "plasticos_logistics/business_rules/", "plasticos_documents/business_rules/", "Moving BRS-POS-04, BRS-POS-05, BRS-POS-06 through BRS-POS-08, BRS-POS-11, or BRS-POS-12 into logistics"]
convergence_contract_ref: "conv.plan.simple.partners_first_native_opportunity_matching_canonical_revision.v1"
execute_via:
  pipeline: cursor-build
  mention_program: "Cursor Build"
  command_ref: make pr
  authority_order:
    - plan_document
    - cursor_build
todos:
  - id: "T02"
    content: "Add plasticos.opportunity.approval in CRM Bridge with the approved fields, unprefixed ACL rows, version 19.0.3.4.20, and a server-minted immutable create path."
    status: "pending"
  - id: "T03"
    content: "Add opportunity_id and approval_id on the match run, match_result_id on the offer, optional restrict intake links, and the partial uniqueness rules from the 2026-11-04 ledger."
    status: "pending"
  - id: "T04"
    content: "Send HOT, manual, and VanillaSoft ingress to a verified Partner, Material Profile, and native Opportunity without creating a synthetic Intake or Facility."
    status: "pending"
  - id: "T05"
    content: "Build the Gate request from the frozen approval, keep one Gate orchestrator, and omit facility evidence when it is absent."
    status: "pending"
  - id: "T06"
    content: "Create idempotent unsent offers from reviewed current results, keep terms immutable, and record one explicit commercial winner."
    status: "pending"
  - id: "T07"
    content: "On acceptance, create or reuse one draft sale.order with native opportunity_id and the offer sell terms, then leave confirmation to the existing transaction compiler."
    status: "pending"
  - id: "T09"
    content: "Expose the Opportunity, Run, Result, and Offer lineage in the existing views without a second matching command."
    status: "pending"
  - id: "T08"
    content: "Run the Enterprise fixture migration and module suites, including interruption and a two-company visibility check, on a clone of odoo_test_tpl_ee_c9e8a81f52f23680."
    status: "pending"
  - id: "T10"
    content: "Append the native Opportunity correction to AGENTS.md and record finding continuity against the final fixture result."
    status: "pending"
```
