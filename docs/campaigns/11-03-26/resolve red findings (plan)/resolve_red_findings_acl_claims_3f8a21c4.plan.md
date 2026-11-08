---
name: Resolve preserved-red findings — claims/transaction-line ACL exposures (F-C1..C3) and recovery-field semantics (F-A1/A2)
overview: "Close the five preserved-red findings from the PR #303 enterprise validation without violating the standing operator decisions of 2026-10-25. Track C (F-C1..C3): adopt an explicit claims/transaction-line role matrix as ADR-129, then make the minimal ACL corrections — delete the two blanket `_all` CRUD rows (`access_claim_all` on plasticos.claim, `access_transaction_line_all` on plasticos.transa..."
todos:
  - id: T1
    content: "Write ADR-129 recording (a) the approved claims role matrix: claims_user = read/write/create no-unlink, claims_manager = full CRUD, qc_manager implies claims_user, operations_manager implies claims_manager, plain internal users = no claim access; (b) transaction lines: internal users read-only, logistics RWC, plasticos manager CRUD, no blanket row; (c) recovery semantics per operator decision 2026-10-25: freight_chargebacks and lightweight_penalties are manual fields, resolving a claim never auto-writes them, archiving never erases them; (d) the T2 probe finding for the unexpected unlink pass. Build approval of this plan constitutes operator sign-off of this matrix."
    status: pending
    phase: execute
    depends_on: []
  - id: T2
    content: "Probe (read-only) why TestTransactionACL.test_base_user_cannot_unlink unexpectedly passes while access_transaction_all grants delete: inspect plasticos_transaction/security/security_hardening.xml and plasticos_security_base/security/record_rules.xml for the denying mechanism; record the identified mechanism in ADR-129. Do not remove access_transaction_all in this PR."
    status: pending
    phase: execute
    depends_on: []
  - id: T3
    content: "Delete the blanket row `access_claim_all` (base.group_system row `access_claim_all` named at CSV line 5 grants base.group_system — verify exact row: the blanket row grants base.group_system per current CSV read; the brief pins the blanket as the row granting full CRUD beyond group rows. Read the CSV first per rule 71, remove only the row granting full CRUD to base.group_user/All-users on plasticos.claim, keep group_claims_user 1,1,1,0 and group_claims_manager 1,1,1,1 and the base.group_system row)."
    status: pending
    phase: execute
    depends_on: [T1]
  - id: T4
    content: "Add security/claims_group_imply.xml in plasticos_claims (crm_group_imply.xml pattern): group_qc_manager gains implied group_claims_user; group_operations_manager gains implied group_claims_manager. Register in manifest data list. This preserves real claim workflows for the roles that legitimately need them after the blanket row is gone."
    status: pending
    phase: execute
    depends_on: [T1, T3]
  - id: T5
    content: "In plasticos_claims/models/document_inherit.py, run the claim search/create for tagged photo uploads via a scoped sudo() with inline justification (uploader may lack claims groups; claim auto-create is a system behavior; uploader attribution preserved in the record body/notes). Keep the rest of the method as-user."
    status: pending
    phase: execute
    depends_on: [T3]
  - id: T6
    content: "Scope claims UI to claims groups: add groups= to the Claims menus (claim_menus.xml) and to the transaction Claims smart button / action so non-claims internal users do not hit AccessError from navigation."
    status: pending
    phase: execute
    depends_on: [T3, T4]
  - id: T7
    content: "Delete `access_transaction_line_all` (the base.group_user full-CRUD duplicate on plasticos.transaction.line) from plasticos_transaction/security/ir.model.access.csv, leaving base.group_user read-only, logistics RWC (security_base), and group_plasticos_manager CRUD. Read the full CSV first per rule 71."
    status: pending
    phase: execute
    depends_on: [T1]
  - id: T8
    content: "Restrict the CSV transaction-import wizard menu to plasticos_transaction.group_plasticos_manager (menu currently ungrouped; wizard creates lines as the current user and would partial-save for users stripped of create rights by T7)."
    status: pending
    phase: execute
    depends_on: [T7]
  - id: T9
    content: "Move TestClaimACL from plasticos_commission/tests/test_security_acl.py (line 194) into a new plasticos_claims/tests/test_claim_acl.py (plasticos_commission does not depend on plasticos_claims, so its setup silently drops the claims group — fragile). Keep TestTransactionACL in place. Wire the new file into plasticos_claims/tests/__init__.py."
    status: pending
    phase: execute
    depends_on: [T3, T4]
  - id: T10
    content: "Remove dead recovery-compute code: delete _compute_chargebacks_penalties override in plasticos_claims/models/transaction_claims.py (lines ~45-70) and the dead fallback in plasticos_transaction/models/transaction.py (~line 843); fix action_resolve docstring in claim.py (references nonexistent _update_transaction_recoveries); correct freight_chargebacks/lightweight_penalties help text and the plasticos_transaction README gross_margin formula to state manual entry per ADR-129."
    status: pending
    phase: execute
    depends_on: [T1]
  - id: T11
    content: "Rewrite test_freight_chargeback_recovery_flows_to_transaction and test_lightweight_penalty_recovery_flows_to_transaction in plasticos_claims/tests/test_depends_transaction_claims_bridge.py to encode manual semantics: resolving a claim leaves transaction recoveries at 0.0; a manual write of freight_chargebacks/lightweight_penalties flows into gross_margin via _compute_financials; archiving a resolved claim does not erase manual values."
    status: pending
    phase: execute
    depends_on: [T10]
  - id: T12
    content: "Bump __manifest__.py versions of every runtime-changed module (plasticos_claims, plasticos_transaction, plasticos_commission) to the next 19.0.X.Y.Z; ruff format manifests after edit. Scoped upgrades only: make update m=plasticos_claims,plasticos_transaction,plasticos_commission equivalents — never update-all."
    status: pending
    phase: execute
    depends_on: [T3, T4, T5, T6, T7, T8, T9, T10, T11]
  - id: T13
    content: "Run the Docker-fixture module tests for the three affected modules, then ruff and the full local gate; attach the test receipt."
    status: pending
    phase: execute
    depends_on: [T12]
isProject: false
kind: simple
execute_via: cursor-build
status: current
---

# PLAN: Resolve preserved-red findings — claims/transaction-line ACL exposures (F-C1..C3) and recovery-field semantics (F-A1/A2)

> **Projected by** `scripts/render_plan_pe_autonomy.py` from validated PLAN_DOCUMENT JSON.

> **First-class SSOT (git):** `environment/contracts/execution/templates/canonical.template.executable_plan.v1.plan.md` · metadata sidecar `*.meta.md` · registered in `environment/contracts/execution/MANIFEST.yaml`. Skill path is a symlink; `.cursor/plans/_TEMPLATE.plan.md` is a local mirror only.
> **Schema:** `canonical.schema.plan_document.v1` (status: fill → `executable` only when law holds)
> **Parameters:** every value is projected from PLAN_DOCUMENT. A value reading `unknown — …` or `unbound — …` is absent from PLAN_DOCUMENT and must be resolved before status becomes `executable`.
> **Execute:** when status is `executable`, press **Build**, stack on the unique open-PR tip if any open PR exists (`PR_STACK=auto`; never `origin/main`), then `PR_STACK=auto PR_REMEDIATE=0 make pr` and display the PR URL. Do **not** run `make campaign`, admit a Program Lock, or free-form mutate from this markdown alone.
> **Cursor todos:** frontmatter `todos` project to Build todos. Body is the binding contract.
> **File name:** `resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2_c8cda47b.plan.md`
> **Law:** executable only when baseline matches, capability probes pass, invariants match, and envelope is respected. Markdown completeness alone is insufficient.

## Execute via Cursor Build

Press **Build**. Plan on the current workspace. Execute on the unique open-PR chain tip.

- If any open PR exists: **never** branch from `origin/main`. Start from the unique chain tip (`PR_STACK=auto`). Use `agent_worktree_start.sh` when this checkout is not already that tip. Sibling open-PR chains fail closed.
- If the board is empty: `origin/main` is allowed.
- Do not run `make campaign`.
- Do not admit a Program Lock or Controller lease.
- Do not write `Lock: origin/main = <sha>`.
- Do not open a new worktree from tip as a **planning** requirement.
- After Build todos complete: scoped-commit (pathspecs), `l4_local.py authorize-release`, then `PR_STACK=auto PR_REMEDIATE=0 make pr`. Do not skip `make pr`.
- The finish reply **must** display the opened PR URL as proof. Without that URL the Build is incomplete.

## Metadata

| Field | Value |
|-------|-------|
| plan_id | `plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1` |
| name | Resolve preserved-red findings — claims/transaction-line ACL exposures (F-C1..C3) and recovery-field semantics (F-A1/A2) |
| overview | Close the five preserved-red findings from the PR #303 enterprise validation without violating the standing operator decisions of 2026-10-25. Track C (F-C1..C3): adopt an explicit claims/transaction-line role matrix as ADR-129, then make the minimal ACL corrections — delete the two blanket `_all` CRUD rows (`access_claim_all` on plasticos.claim, `access_transaction_line_all` on plasticos.transaction.line), wire QC/operations managers into the claims groups via the established group-imply pattern, give the claim-photo auto-create a justified scoped sudo, and restrict the CSV transaction-import menu to managers — so TestClaimACL.test_claim_user_cannot_unlink, TestClaimACL.test_no_group_cannot_read and TestTransactionACL.test_base_user_cannot_write_tx_line pass for the right reason. Track A (F-A1/A2): encode the operator-decided manual recovery semantics (BUSINESS_SEMANTICS_UNRESOLVED — no auto-flow from resolved claims) by deleting the dead `_compute_chargebacks_penalties` code in both modules, correcting the misleading docstrings/help text, and rewriting the two claims-bridge tests to assert manual-entry semantics instead of the never-implemented auto-compute contract. No blanket sudo, no multi-addon ACL refactor, no computed conversion or backfill of recovery fields. |
| schema_version | `1.0` |
| status | `draft` — planning convergence is `partial`; remaining unknowns: U1, U3 |
| is_project | `false` |
| owner | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` |
| created_at | 2026-11-03T16:25:23+00:00 |
| updated_at | 2026-11-03T16:25:23+00:00 |
| depth | `deep` |
| estimate | 6-8h including Docker-fixture test runs |

## Architect framing

| Field | Value |
|-------|-------|
| planning_ssot | validated PLAN_DOCUMENT JSON (`validate_plan_document.py`) |
| plan_class | `bounded_execution_contract` — PLAN_DOCUMENT mode `plan` |
| redesign_allowed | `false` |
| follow_on_schema_evolution_separate | `true` |
| framing_notes | Execute via Cursor Build; stacked make pr if any open PR exists; no redesign unless plan_class requires it |

## Immutable baseline

| Field | Value |
|-------|-------|
| captured_at | `2026-11-03T16:25:23+00:00` |
| repository | `cryptoxdog/IB-Odoo_19` |
| workspace | `/Users/ib-mac/IB-Odoo_19 (LOCAL)/IB-Odoo_19` |
| branch | `docs/campaign-reorg-multiload-audit` |
| commit_sha | `50e655701e89405626367f8e0ea8eb7365008281` |
| dirty | `true` |
| artifact_hashes | `{}` — none pinned by PLAN_DOCUMENT |
| allowed_local_dirt | none |
| overlap_policy | `stop_if_dirty_overlaps_may_modify` |
| verification_rule | `reverify_at_execution_start` |
| on_drift | `stop_and_replan` |

## Objective

### Mission

Close the five preserved-red findings from the PR #303 enterprise validation without violating the standing operator decisions of 2026-10-25. Track C (F-C1..C3): adopt an explicit claims/transaction-line role matrix as ADR-129, then make the minimal ACL corrections — delete the two blanket `_all` CRUD rows (`access_claim_all` on plasticos.claim, `access_transaction_line_all` on plasticos.transaction.line), wire QC/operations managers into the claims groups via the established group-imply pattern, give the claim-photo auto-create a justified scoped sudo, and restrict the CSV transaction-import menu to managers — so TestClaimACL.test_claim_user_cannot_unlink, TestClaimACL.test_no_group_cannot_read and TestTransactionACL.test_base_user_cannot_write_tx_line pass for the right reason. Track A (F-A1/A2): encode the operator-decided manual recovery semantics (BUSINESS_SEMANTICS_UNRESOLVED — no auto-flow from resolved claims) by deleting the dead `_compute_chargebacks_penalties` code in both modules, correcting the misleading docstrings/help text, and rewriting the two claims-bridge tests to assert manual-entry semantics instead of the never-implemented auto-compute contract. No blanket sudo, no multi-addon ACL refactor, no computed conversion or backfill of recovery fields.

### Scope in

- plasticos_claims: security CSV, group-imply data XML, document_inherit.py sudo, claim_menus.xml groups, transaction_claims.py dead-code removal, claim.py docstring, rewritten bridge tests, new ACL test file, manifest version bump
- plasticos_transaction: security CSV row deletion, transaction.py dead fallback removal + field help, import wizard menu groups, README formula correction, manifest version bump
- plasticos_commission: move TestClaimACL out of test_security_acl.py, manifest version bump
- docs/adr/ADR-129-claims-roles-and-recovery-semantics.md (new)

### Success properties

Each property's proof is the `final_validation` entry it names (by id or by script/file). A property with no proving validation, or only skipped / not_applicable ones, blocks `executable`.

| id | property | evidence_type | proof | blocking |
|----|----------|---------------|-------|----------|
| SP-01 | TestClaimACL.test_claim_user_cannot_unlink and test_no_group_cannot_read raise AccessError and pass on the Docker fixture — proof V1 | `quality_gate` | V1: `make test-module m=plasticos_claims` → Odoo test summary present: 0 failed, 0 error, tests > 0; receipt written under .l9/runtime/test-env/ | `true` |
| SP-02 | TestTransactionACL.test_base_user_cannot_write_tx_line raises AccessError and passes; the previously-unexpected pass of test_base_user_cannot_unlink has an identified, ADR-documented mechanism — proof V2 | `quality_gate` | V2: `make test-module m=plasticos_commission` → Odoo test summary present: 0 failed, 0 error; TestTransactionACL fully green including test_base_user_cannot_write_tx_line | `true` |
| SP-03 | test_freight_chargeback_recovery_flows_to_transaction and test_lightweight_penalty_recovery_flows_to_transaction are rewritten to the manual-semantics contract and pass; no `_compute_chargebacks_penalties` remains in the codebase — proof V1 | `quality_gate` | V1: `make test-module m=plasticos_claims` → Odoo test summary present: 0 failed, 0 error, tests > 0; receipt written under .l9/runtime/test-env/ | `true` |
| SP-04 | Claim photo upload by a non-claims user still creates the claim (scoped sudo), and the full claims/transaction/commission module test rosters pass — proof V3 | `quality_gate` | V3: `make test-module m=plasticos_transaction` → Odoo test summary present: 0 failed, 0 error | `true` |
| SP-05 | ruff check and format are clean and the full local gate passes — proof V4 and V5 | `quality_gate` | V4: `.venv/bin/ruff check . && .venv/bin/ruff format --check .` → No violations; no reformat needed; V5: `pre-commit run --all-files --config .pre-commit-config.yaml` → All 36 hooks pass (Odoo patterns, ACL checks, gitleaks, wiring) | `true` |

## Capability preflight

`schema_ref:` `canonical.schema.capability_preflight.v1`
`instance_binding:` `capability_preflight_ref` → `preflight.plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1`

| Field | Value |
|-------|-------|
| preflight_id | `preflight.plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1` |
| source_ref | `plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1` |
| phase_id | `preflight` |
| blocking | `true` |
| immutable_baseline_ref | `baseline.plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1` |
| baseline_verified | `false` — reverify at execution start |
| drift_detected | `false` — baseline captured at render |

### Probes (from PLAN_DOCUMENT `pre_validation`; failed blocking probe → status `preflight_blocked`)

| id | capability | command_or_action | pass_criteria | blocking |
|----|------------|-------------------|---------------|----------|
| P1 | pre-validation (status `passed`) | `git rev-parse --abbrev-ref HEAD && git status --porcelain` | Feature branch (not Staging/Production), clean tree before edits | `true` |
| P2 | pre-validation (status `passed`) | `Read plasticos_claims/security/ir.model.access.csv and plasticos_transaction/security/ir.model.access.csv in full` | access_claim_all (line 5) and access_transaction_line_all (line 11 area) present as described in the evidence brief | `true` |
| P3 | pre-validation (status `passed`) | `grep -n _compute_chargebacks_penalties plasticos_claims/models/transaction_claims.py plasticos_transaction/models/transaction.py` | Dead compute present in both files (transaction_claims.py:51, transaction.py:843) | `true` |
| P4 | pre-validation (status `pending`) | `Confirm Docker test fixture available: config/test_env_fixture.conf names odoo_test_tpl_ee_c9e8a81f52f23680` | Fixture file present; make test-module usable per rule 36 | `true` |
| P5 | pre-validation (status `passed`) | `pre-commit hook catalog is .pre-commit-config.yaml (36 hooks)` | File present; hooks run before commit | `true` |

## Execution envelope

Mutations outside this envelope are forbidden (PLAN-SCHEMA-004).

### Filesystem

- **write_allow:** `plasticos_claims/security/ir.model.access.csv`, `plasticos_claims/security/claims_group_imply.xml`, `plasticos_claims/models/document_inherit.py`, `plasticos_claims/models/transaction_claims.py`, `plasticos_claims/models/claim.py`, `plasticos_claims/views/claim_menus.xml`, `plasticos_claims/tests/`, `plasticos_claims/__manifest__.py`, `plasticos_transaction/security/ir.model.access.csv`, `plasticos_transaction/models/transaction.py`, `plasticos_transaction/views/transaction_import_wizard_views.xml`, `plasticos_transaction/README.md`, `plasticos_transaction/__manifest__.py`, `plasticos_commission/tests/test_security_acl.py`, `plasticos_commission/__manifest__.py`, `docs/adr/ADR-129-claims-roles-and-recovery-semantics.md`, `docs/adr/README.md`
- **write_deny:** `pipeline_v2.py (hard CI guard)`, `plasticos_web_leads/** (rule 50 guard; out of scope)`, `plasticos_transaction/security/ir.model.access.csv row access_transaction_all (U1 unresolved)`, `freight_chargebacks/lightweight_penalties field definitions (stay plain Float — operator decision)`, `plasticos_security_base/security/security_groups.xml group definitions (implication lives in plasticos_claims)`, `Any other module's ACL CSV (brief §9 inventory is a separate campaign)`
- **delete_allow:** `plasticos_claims/security/ir.model.access.csv`, `plasticos_transaction/security/ir.model.access.csv`, `plasticos_claims/models/transaction_claims.py`, `plasticos_transaction/models/transaction.py`, `plasticos_claims/models/claim.py`, `plasticos_transaction/README.md`

### Commands

- **allow:** `make test-module m=plasticos_claims`, `make test-module m=plasticos_commission`, `make test-module m=plasticos_transaction`, `.venv/bin/ruff check . && .venv/bin/ruff format --check .`, `make pr-check`, `pre-commit run --all-files --config .pre-commit-config.yaml`
- **deny:** `git push --force`, `git reset --hard`, admin merge, committing secrets

### Network

| Field | Value |
|-------|-------|
| mode | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` |
| allowed_services | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` |

### Secrets

| Field | Value |
|-------|-------|
| access | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` |
| redaction_required | `true` |

### Autonomous merge

`autonomous_merge:` `false` always. This plan confers no merge authority.

### Preserved contracts

- Operator decision 2026-10-25 Decision A: recoveries are manual; no computed conversion, no backfill, no claim-to-margin automation
- Operator decision 2026-10-25 Decision C: no blanket sudo, no casual ACL removal beyond the two named rows, no 13-addon refactor
- Rule 71 ACL contract: read full CSV before editing, no redundant rows, consistent id format
- Rule 89: version bump + scoped module upgrade only
- Claims archiving never erases a recognized recovery

## Side effects and idempotency

Required for every destructive / external-write TODO (PLAN-SCHEMA-005). One row per todo.

| todo_id | side_effects | idempotency | retry | compensation | irreversible |
|---------|--------------|-------------|-------|--------------|--------------|
| T1 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- docs/adr/ADR-129-claims-roles-and-recovery-semantics.md` | `false` |
| T2 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_transaction/security/security_hardening.xml plasticos_security_base/security/record_rules.xml` | `false` |
| T3 | `destructive_filesystem_mutation` | `unsafe_blind_repeat` | `manual_only` | `git restore -- plasticos_claims/security/ir.model.access.csv` | `false` |
| T4 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_claims/security/claims_group_imply.xml plasticos_claims/__manifest__.py` | `false` |
| T5 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_claims/models/document_inherit.py` | `false` |
| T6 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_claims/views/claim_menus.xml plasticos_claims/models/transaction_claims_bridge.py` | `false` |
| T7 | `destructive_filesystem_mutation` | `unsafe_blind_repeat` | `manual_only` | `git restore -- plasticos_transaction/security/ir.model.access.csv` | `false` |
| T8 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_transaction/views/transaction_import_wizard_views.xml` | `false` |
| T9 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_commission/tests/test_security_acl.py plasticos_claims/tests/test_claim_acl.py plasticos_claims/tests/__init__.py` | `false` |
| T10 | `destructive_filesystem_mutation` | `unsafe_blind_repeat` | `manual_only` | `git restore -- plasticos_claims/models/transaction_claims.py plasticos_transaction/models/transaction.py plasticos_claims/models/claim.py plasticos_transaction/README.md` | `false` |
| T11 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_claims/tests/test_depends_transaction_claims_bridge.py` | `false` |
| T12 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_claims/__manifest__.py plasticos_transaction/__manifest__.py plasticos_commission/__manifest__.py` | `false` |
| T13 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- config/test_env_fixture.conf` | `false` |

## Architecture impact

| todo_id | bounded_context | layer | owning_contract | prohibited |
|---------|-----------------|-------|-----------------|------------|
| T1 | `docs/adr` | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` | `Operator decision 2026-10-25 Decision A: recoveries are manual; no computed conversion, no backfill, no claim-to-margin automation`, `Operator decision 2026-10-25 Decision C: no blanket sudo, no casual ACL removal beyond the two named rows, no 13-addon refactor`, `Rule 71 ACL contract: read full CSV before editing, no redundant rows, consistent id format`, `Rule 89: version bump + scoped module upgrade only`, `Claims archiving never erases a recognized recovery` | `pipeline_v2.py (hard CI guard)`, `plasticos_web_leads/** (rule 50 guard; out of scope)`, `plasticos_transaction/security/ir.model.access.csv row access_transaction_all (U1 unresolved)`, `freight_chargebacks/lightweight_penalties field definitions (stay plain Float — operator decision)`, `plasticos_security_base/security/security_groups.xml group definitions (implication lives in plasticos_claims)`, `Any other module's ACL CSV (brief §9 inventory is a separate campaign)` |
| T2 | `repository root` | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` | `Operator decision 2026-10-25 Decision A: recoveries are manual; no computed conversion, no backfill, no claim-to-margin automation`, `Operator decision 2026-10-25 Decision C: no blanket sudo, no casual ACL removal beyond the two named rows, no 13-addon refactor`, `Rule 71 ACL contract: read full CSV before editing, no redundant rows, consistent id format`, `Rule 89: version bump + scoped module upgrade only`, `Claims archiving never erases a recognized recovery` | `pipeline_v2.py (hard CI guard)`, `plasticos_web_leads/** (rule 50 guard; out of scope)`, `plasticos_transaction/security/ir.model.access.csv row access_transaction_all (U1 unresolved)`, `freight_chargebacks/lightweight_penalties field definitions (stay plain Float — operator decision)`, `plasticos_security_base/security/security_groups.xml group definitions (implication lives in plasticos_claims)`, `Any other module's ACL CSV (brief §9 inventory is a separate campaign)` |
| T3 | `plasticos_claims/security` | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` | `Operator decision 2026-10-25 Decision A: recoveries are manual; no computed conversion, no backfill, no claim-to-margin automation`, `Operator decision 2026-10-25 Decision C: no blanket sudo, no casual ACL removal beyond the two named rows, no 13-addon refactor`, `Rule 71 ACL contract: read full CSV before editing, no redundant rows, consistent id format`, `Rule 89: version bump + scoped module upgrade only`, `Claims archiving never erases a recognized recovery` | `pipeline_v2.py (hard CI guard)`, `plasticos_web_leads/** (rule 50 guard; out of scope)`, `plasticos_transaction/security/ir.model.access.csv row access_transaction_all (U1 unresolved)`, `freight_chargebacks/lightweight_penalties field definitions (stay plain Float — operator decision)`, `plasticos_security_base/security/security_groups.xml group definitions (implication lives in plasticos_claims)`, `Any other module's ACL CSV (brief §9 inventory is a separate campaign)` |
| T4 | `plasticos_claims` | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` | `Operator decision 2026-10-25 Decision A: recoveries are manual; no computed conversion, no backfill, no claim-to-margin automation`, `Operator decision 2026-10-25 Decision C: no blanket sudo, no casual ACL removal beyond the two named rows, no 13-addon refactor`, `Rule 71 ACL contract: read full CSV before editing, no redundant rows, consistent id format`, `Rule 89: version bump + scoped module upgrade only`, `Claims archiving never erases a recognized recovery` | `pipeline_v2.py (hard CI guard)`, `plasticos_web_leads/** (rule 50 guard; out of scope)`, `plasticos_transaction/security/ir.model.access.csv row access_transaction_all (U1 unresolved)`, `freight_chargebacks/lightweight_penalties field definitions (stay plain Float — operator decision)`, `plasticos_security_base/security/security_groups.xml group definitions (implication lives in plasticos_claims)`, `Any other module's ACL CSV (brief §9 inventory is a separate campaign)` |
| T5 | `plasticos_claims/models` | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` | `Operator decision 2026-10-25 Decision A: recoveries are manual; no computed conversion, no backfill, no claim-to-margin automation`, `Operator decision 2026-10-25 Decision C: no blanket sudo, no casual ACL removal beyond the two named rows, no 13-addon refactor`, `Rule 71 ACL contract: read full CSV before editing, no redundant rows, consistent id format`, `Rule 89: version bump + scoped module upgrade only`, `Claims archiving never erases a recognized recovery` | `pipeline_v2.py (hard CI guard)`, `plasticos_web_leads/** (rule 50 guard; out of scope)`, `plasticos_transaction/security/ir.model.access.csv row access_transaction_all (U1 unresolved)`, `freight_chargebacks/lightweight_penalties field definitions (stay plain Float — operator decision)`, `plasticos_security_base/security/security_groups.xml group definitions (implication lives in plasticos_claims)`, `Any other module's ACL CSV (brief §9 inventory is a separate campaign)` |
| T6 | `plasticos_claims` | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` | `Operator decision 2026-10-25 Decision A: recoveries are manual; no computed conversion, no backfill, no claim-to-margin automation`, `Operator decision 2026-10-25 Decision C: no blanket sudo, no casual ACL removal beyond the two named rows, no 13-addon refactor`, `Rule 71 ACL contract: read full CSV before editing, no redundant rows, consistent id format`, `Rule 89: version bump + scoped module upgrade only`, `Claims archiving never erases a recognized recovery` | `pipeline_v2.py (hard CI guard)`, `plasticos_web_leads/** (rule 50 guard; out of scope)`, `plasticos_transaction/security/ir.model.access.csv row access_transaction_all (U1 unresolved)`, `freight_chargebacks/lightweight_penalties field definitions (stay plain Float — operator decision)`, `plasticos_security_base/security/security_groups.xml group definitions (implication lives in plasticos_claims)`, `Any other module's ACL CSV (brief §9 inventory is a separate campaign)` |
| T7 | `plasticos_transaction/security` | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` | `Operator decision 2026-10-25 Decision A: recoveries are manual; no computed conversion, no backfill, no claim-to-margin automation`, `Operator decision 2026-10-25 Decision C: no blanket sudo, no casual ACL removal beyond the two named rows, no 13-addon refactor`, `Rule 71 ACL contract: read full CSV before editing, no redundant rows, consistent id format`, `Rule 89: version bump + scoped module upgrade only`, `Claims archiving never erases a recognized recovery` | `pipeline_v2.py (hard CI guard)`, `plasticos_web_leads/** (rule 50 guard; out of scope)`, `plasticos_transaction/security/ir.model.access.csv row access_transaction_all (U1 unresolved)`, `freight_chargebacks/lightweight_penalties field definitions (stay plain Float — operator decision)`, `plasticos_security_base/security/security_groups.xml group definitions (implication lives in plasticos_claims)`, `Any other module's ACL CSV (brief §9 inventory is a separate campaign)` |
| T8 | `plasticos_transaction/views` | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` | `Operator decision 2026-10-25 Decision A: recoveries are manual; no computed conversion, no backfill, no claim-to-margin automation`, `Operator decision 2026-10-25 Decision C: no blanket sudo, no casual ACL removal beyond the two named rows, no 13-addon refactor`, `Rule 71 ACL contract: read full CSV before editing, no redundant rows, consistent id format`, `Rule 89: version bump + scoped module upgrade only`, `Claims archiving never erases a recognized recovery` | `pipeline_v2.py (hard CI guard)`, `plasticos_web_leads/** (rule 50 guard; out of scope)`, `plasticos_transaction/security/ir.model.access.csv row access_transaction_all (U1 unresolved)`, `freight_chargebacks/lightweight_penalties field definitions (stay plain Float — operator decision)`, `plasticos_security_base/security/security_groups.xml group definitions (implication lives in plasticos_claims)`, `Any other module's ACL CSV (brief §9 inventory is a separate campaign)` |
| T9 | `repository root` | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` | `Operator decision 2026-10-25 Decision A: recoveries are manual; no computed conversion, no backfill, no claim-to-margin automation`, `Operator decision 2026-10-25 Decision C: no blanket sudo, no casual ACL removal beyond the two named rows, no 13-addon refactor`, `Rule 71 ACL contract: read full CSV before editing, no redundant rows, consistent id format`, `Rule 89: version bump + scoped module upgrade only`, `Claims archiving never erases a recognized recovery` | `pipeline_v2.py (hard CI guard)`, `plasticos_web_leads/** (rule 50 guard; out of scope)`, `plasticos_transaction/security/ir.model.access.csv row access_transaction_all (U1 unresolved)`, `freight_chargebacks/lightweight_penalties field definitions (stay plain Float — operator decision)`, `plasticos_security_base/security/security_groups.xml group definitions (implication lives in plasticos_claims)`, `Any other module's ACL CSV (brief §9 inventory is a separate campaign)` |
| T10 | `repository root` | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` | `Operator decision 2026-10-25 Decision A: recoveries are manual; no computed conversion, no backfill, no claim-to-margin automation`, `Operator decision 2026-10-25 Decision C: no blanket sudo, no casual ACL removal beyond the two named rows, no 13-addon refactor`, `Rule 71 ACL contract: read full CSV before editing, no redundant rows, consistent id format`, `Rule 89: version bump + scoped module upgrade only`, `Claims archiving never erases a recognized recovery` | `pipeline_v2.py (hard CI guard)`, `plasticos_web_leads/** (rule 50 guard; out of scope)`, `plasticos_transaction/security/ir.model.access.csv row access_transaction_all (U1 unresolved)`, `freight_chargebacks/lightweight_penalties field definitions (stay plain Float — operator decision)`, `plasticos_security_base/security/security_groups.xml group definitions (implication lives in plasticos_claims)`, `Any other module's ACL CSV (brief §9 inventory is a separate campaign)` |
| T11 | `plasticos_claims/tests` | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` | `Operator decision 2026-10-25 Decision A: recoveries are manual; no computed conversion, no backfill, no claim-to-margin automation`, `Operator decision 2026-10-25 Decision C: no blanket sudo, no casual ACL removal beyond the two named rows, no 13-addon refactor`, `Rule 71 ACL contract: read full CSV before editing, no redundant rows, consistent id format`, `Rule 89: version bump + scoped module upgrade only`, `Claims archiving never erases a recognized recovery` | `pipeline_v2.py (hard CI guard)`, `plasticos_web_leads/** (rule 50 guard; out of scope)`, `plasticos_transaction/security/ir.model.access.csv row access_transaction_all (U1 unresolved)`, `freight_chargebacks/lightweight_penalties field definitions (stay plain Float — operator decision)`, `plasticos_security_base/security/security_groups.xml group definitions (implication lives in plasticos_claims)`, `Any other module's ACL CSV (brief §9 inventory is a separate campaign)` |
| T12 | `repository root` | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` | `Operator decision 2026-10-25 Decision A: recoveries are manual; no computed conversion, no backfill, no claim-to-margin automation`, `Operator decision 2026-10-25 Decision C: no blanket sudo, no casual ACL removal beyond the two named rows, no 13-addon refactor`, `Rule 71 ACL contract: read full CSV before editing, no redundant rows, consistent id format`, `Rule 89: version bump + scoped module upgrade only`, `Claims archiving never erases a recognized recovery` | `pipeline_v2.py (hard CI guard)`, `plasticos_web_leads/** (rule 50 guard; out of scope)`, `plasticos_transaction/security/ir.model.access.csv row access_transaction_all (U1 unresolved)`, `freight_chargebacks/lightweight_penalties field definitions (stay plain Float — operator decision)`, `plasticos_security_base/security/security_groups.xml group definitions (implication lives in plasticos_claims)`, `Any other module's ACL CSV (brief §9 inventory is a separate campaign)` |
| T13 | `config` | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` | `Operator decision 2026-10-25 Decision A: recoveries are manual; no computed conversion, no backfill, no claim-to-margin automation`, `Operator decision 2026-10-25 Decision C: no blanket sudo, no casual ACL removal beyond the two named rows, no 13-addon refactor`, `Rule 71 ACL contract: read full CSV before editing, no redundant rows, consistent id format`, `Rule 89: version bump + scoped module upgrade only`, `Claims archiving never erases a recognized recovery` | `pipeline_v2.py (hard CI guard)`, `plasticos_web_leads/** (rule 50 guard; out of scope)`, `plasticos_transaction/security/ir.model.access.csv row access_transaction_all (U1 unresolved)`, `freight_chargebacks/lightweight_penalties field definitions (stay plain Float — operator decision)`, `plasticos_security_base/security/security_groups.xml group definitions (implication lives in plasticos_claims)`, `Any other module's ACL CSV (brief §9 inventory is a separate campaign)` |

## Rollback

`schema_ref:` `canonical.schema.rollback_contract.v1`
`instance_binding:` `rollback_contract_ref` → `rollback.plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1`

| Field | Value |
|-------|-------|
| rollback_id | `rollback.plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1` |
| source_execution_ref | `plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1` |
| supported | `true` |
| automatic_allowed | `false` |
| approval_required | `true` |
| trigger_conditions | C1 fails (ADR-129 committed; role matrix table present; T2 probe finding recorded) → Stop: do not touch any ACL file without the ADR; C2 fails (Manual probe or unit evidence that a non-claims internal user's tagged document upload still creates the claim) → Revert T3/T5, reassess sudo scope before proceeding; C3 fails (make test-module m=plasticos_claims summary: 0 failed, 0 error, >0 tests) → Fix within scope or mark convergence partial; never skipTest; C4 fails (Test receipts for all three modules + make pr-check pass) → Do not publish; report failures verbatim |

### Strategies (typed — PLAN-SCHEMA-009)

| domain | mode | notes |
|--------|------|-------|
| code | `git_restore_scoped_paths` | Every change is additive-or-restorable in git: revert the PR branch. ACL rows restore on module upgrade from the reverted CSVs. No destructive SQL, no data backfill, no column drops anywhere in scope. |
| data | `none` | PLAN_DOCUMENT declares no data mutation |
| external_state | `none` | PLAN_DOCUMENT declares no external write |
| local_state | `git_restore_scoped_paths` | scoped to todo files |

### Irreversible operations

- none — no todo is marked `irreversible` (PLAN-SCHEMA-010)

### Rollback verification

- re-run `make test-module m=plasticos_claims`
- re-run `make test-module m=plasticos_commission`
- re-run `make test-module m=plasticos_transaction`
- re-run `.venv/bin/ruff check . && .venv/bin/ruff format --check .`
- re-run `make pr-check`
- re-run `pre-commit run --all-files --config .pre-commit-config.yaml`

## Complexity and uncertainty

| Field | Value |
|-------|-------|
| complexity | `medium` — highest todo risk across 13 todo(s) |
| uncertainty | `medium` — 3 unknown(s), 0 blocking |
| blast_radius | `medium` — Runtime access control on two business models (plasticos.claim, plasticos.transaction.line) for every internal user; claim auto-create on document upload; CSV import wizard availability; two test files and one test move across three modules. No schema changes, no data migrations expected, no partner/transaction data touched. |
| architectural_boundaries_crossed | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` |
| external_systems_touched | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` |
| migration_required | unknown — not declared in PLAN_DOCUMENT; resolve before status `executable` |
| unknown_dependency_count | `3` |

## Inventory and classification *(optional — activate if retire/migrate/replace)*

Not activated — PLAN_DOCUMENT declares no retire / migrate / replace inventory.

## Gated write pipeline *(optional — irreversible or external writes)*

Not activated — PLAN_DOCUMENT declares no irreversible or external write.

## Regeneration extinguishment *(optional — retirement/deprecation)*

Not activated — PLAN_DOCUMENT declares no retirement or deprecation.

## Execution DAG

`schema_ref:` `canonical.schema.dependency_topology.v1`
`instance_binding:` `dependency_topology_ref` → `dag.plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1`
Must be acyclic before status may become `executable` (PLAN-SCHEMA-007).

| Field | Value |
|-------|-------|
| topology_id | `dag.plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1` |
| topology_kind | `execution` |
| graph_type | `directed_acyclic_graph` |

### Nodes / edges

| id | task | owner | risk | effort | depends_on | outputs |
|----|------|-------|------|--------|------------|---------|
| T1 | Write ADR-129 recording (a) the approved claims role matrix: claims_user = read/write/create no-unlink, claims_manager = full CRUD, qc_manager implies claims_user, operations_manager implies claims_manager, plain internal users = no claim access; (b) transaction lines: internal users read-only, logistics RWC, plasticos manager CRUD, no blanket row; (c) recovery semantics per operator decision 2026-10-25: freight_chargebacks and lightweight_penalties are manual fields, resolving a claim never auto-writes them, archiving never erases them; (d) the T2 probe finding for the unexpected unlink pass. Build approval of this plan constitutes operator sign-off of this matrix. | Cursor Build agent | `low` | 45m | `[]` | `docs/adr/ADR-129-claims-roles-and-recovery-semantics.md` |
| T2 | Probe (read-only) why TestTransactionACL.test_base_user_cannot_unlink unexpectedly passes while access_transaction_all grants delete: inspect plasticos_transaction/security/security_hardening.xml and plasticos_security_base/security/record_rules.xml for the denying mechanism; record the identified mechanism in ADR-129. Do not remove access_transaction_all in this PR. | Cursor Build agent | `low` | 30m | `[]` | `plasticos_transaction/security/security_hardening.xml`, `plasticos_security_base/security/record_rules.xml` |
| T3 | Delete the blanket row `access_claim_all` (base.group_system row `access_claim_all` named at CSV line 5 grants base.group_system — verify exact row: the blanket row grants base.group_system per current CSV read; the brief pins the blanket as the row granting full CRUD beyond group rows. Read the CSV first per rule 71, remove only the row granting full CRUD to base.group_user/All-users on plasticos.claim, keep group_claims_user 1,1,1,0 and group_claims_manager 1,1,1,1 and the base.group_system row). | Cursor Build agent | `medium` | 20m | `[T1]` | `plasticos_claims/security/ir.model.access.csv` |
| T4 | Add security/claims_group_imply.xml in plasticos_claims (crm_group_imply.xml pattern): group_qc_manager gains implied group_claims_user; group_operations_manager gains implied group_claims_manager. Register in manifest data list. This preserves real claim workflows for the roles that legitimately need them after the blanket row is gone. | Cursor Build agent | `medium` | 30m | `[T1, T3]` | `plasticos_claims/security/claims_group_imply.xml`, `plasticos_claims/__manifest__.py` |
| T5 | In plasticos_claims/models/document_inherit.py, run the claim search/create for tagged photo uploads via a scoped sudo() with inline justification (uploader may lack claims groups; claim auto-create is a system behavior; uploader attribution preserved in the record body/notes). Keep the rest of the method as-user. | Cursor Build agent | `medium` | 30m | `[T3]` | `plasticos_claims/models/document_inherit.py` |
| T6 | Scope claims UI to claims groups: add groups= to the Claims menus (claim_menus.xml) and to the transaction Claims smart button / action so non-claims internal users do not hit AccessError from navigation. | Cursor Build agent | `low` | 30m | `[T3, T4]` | `plasticos_claims/views/claim_menus.xml`, `plasticos_claims/models/transaction_claims_bridge.py` |
| T7 | Delete `access_transaction_line_all` (the base.group_user full-CRUD duplicate on plasticos.transaction.line) from plasticos_transaction/security/ir.model.access.csv, leaving base.group_user read-only, logistics RWC (security_base), and group_plasticos_manager CRUD. Read the full CSV first per rule 71. | Cursor Build agent | `medium` | 15m | `[T1]` | `plasticos_transaction/security/ir.model.access.csv` |
| T8 | Restrict the CSV transaction-import wizard menu to plasticos_transaction.group_plasticos_manager (menu currently ungrouped; wizard creates lines as the current user and would partial-save for users stripped of create rights by T7). | Cursor Build agent | `low` | 15m | `[T7]` | `plasticos_transaction/views/transaction_import_wizard_views.xml` |
| T9 | Move TestClaimACL from plasticos_commission/tests/test_security_acl.py (line 194) into a new plasticos_claims/tests/test_claim_acl.py (plasticos_commission does not depend on plasticos_claims, so its setup silently drops the claims group — fragile). Keep TestTransactionACL in place. Wire the new file into plasticos_claims/tests/__init__.py. | Cursor Build agent | `low` | 45m | `[T3, T4]` | `plasticos_commission/tests/test_security_acl.py`, `plasticos_claims/tests/test_claim_acl.py`, `plasticos_claims/tests/__init__.py` |
| T10 | Remove dead recovery-compute code: delete _compute_chargebacks_penalties override in plasticos_claims/models/transaction_claims.py (lines ~45-70) and the dead fallback in plasticos_transaction/models/transaction.py (~line 843); fix action_resolve docstring in claim.py (references nonexistent _update_transaction_recoveries); correct freight_chargebacks/lightweight_penalties help text and the plasticos_transaction README gross_margin formula to state manual entry per ADR-129. | Cursor Build agent | `medium` | 1h | `[T1]` | `plasticos_claims/models/transaction_claims.py`, `plasticos_transaction/models/transaction.py`, `plasticos_claims/models/claim.py`, `plasticos_transaction/README.md` |
| T11 | Rewrite test_freight_chargeback_recovery_flows_to_transaction and test_lightweight_penalty_recovery_flows_to_transaction in plasticos_claims/tests/test_depends_transaction_claims_bridge.py to encode manual semantics: resolving a claim leaves transaction recoveries at 0.0; a manual write of freight_chargebacks/lightweight_penalties flows into gross_margin via _compute_financials; archiving a resolved claim does not erase manual values. | Cursor Build agent | `low` | 1h | `[T10]` | `plasticos_claims/tests/test_depends_transaction_claims_bridge.py` |
| T12 | Bump __manifest__.py versions of every runtime-changed module (plasticos_claims, plasticos_transaction, plasticos_commission) to the next 19.0.X.Y.Z; ruff format manifests after edit. Scoped upgrades only: make update m=plasticos_claims,plasticos_transaction,plasticos_commission equivalents — never update-all. | Cursor Build agent | `low` | 15m | `[T3, T4, T5, T6, T7, T8, T9, T10, T11]` | `plasticos_claims/__manifest__.py`, `plasticos_transaction/__manifest__.py`, `plasticos_commission/__manifest__.py` |
| T13 | Run the Docker-fixture module tests for the three affected modules, then ruff and the full local gate; attach the test receipt. | Cursor Build agent | `low` | 1h | `[T12]` | `config/test_env_fixture.conf` |

**Critical path:** T1 → T3 → T4 → T5 → T7 → T9 → T10 → T11 → T12 → T13

**Forbidden edges:** any edge not listed above; any todo writing outside `write_allow`.

### Milestones

| id | outcome | unlocks |
|----|---------|---------|
| M1 | ADR-129 written: role matrix and recovery semantics are operator-approved law in-repo | All ACL and semantics mutations (T3-T11) |
| M2 | Blanket rows deleted with role implication and sudo guard in place; claims workflows preserved | ACL tests pass for the right reason (T9, T13) |
| M3 | Dead compute removed and bridge tests encode manual semantics | F-A1/F-A2 closed without violating Decision A |
| M4 | All module rosters green on the Docker fixture, gate passes, PR published | Findings F-C1..C3 and F-A1/A2 formally closed |

### Checkpoints

| id | after | evidence_required | no_go_action |
|----|-------|-------------------|--------------|
| C1 | T1 | ADR-129 committed; role matrix table present; T2 probe finding recorded | Stop: do not touch any ACL file without the ADR |
| C2 | T5 | Manual probe or unit evidence that a non-claims internal user's tagged document upload still creates the claim | Revert T3/T5, reassess sudo scope before proceeding |
| C3 | T11 | make test-module m=plasticos_claims summary: 0 failed, 0 error, >0 tests | Fix within scope or mark convergence partial; never skipTest |
| C4 | T13 | Test receipts for all three modules + make pr-check pass | Do not publish; report failures verbatim |

### Leverage

- **Ranked todos:** `T1`, `T3`, `T4`, `T5`, `T7`, `T2`, `T9`, `T6`, `T8`, `T10`, `T11`, `T12`, `T13`
- **Shared causes:** Additive blanket `_all` ACL rows overriding narrow group rows (T3, T7) — the single cause of all three ACL test failures; No written role policy (T1) — the gap the operator decision demanded closed before any remediation; Docstring-promised compute never wired to fields (T10, T11) — the single cause of both claims-semantics failures
- **Deletions / consolidations:** Delete 2 blanket ACL rows instead of adding record rules or guards — net-negative security surface; Delete ~50 lines of dead compute code in two modules; Consolidate claim ACL testing into plasticos_claims where the dependency actually exists

### Doc / root surface impact

| surface | action | todo_ids | reason |
|---------|--------|----------|--------|
| docs/adr/README.md | `update` | `T1` | Index the new ADR-129 |
| AGENTS.md | `n_a` | — | Append-only file; no contract named in it changes — ACL baseline findings live in the audit baseline, checked in T13 |
| INVARIANTS.md | `n_a` | — | Change restores compliance with the existing group-based ACL invariant; no new invariant introduced |
| plasticos_transaction/README.md | `update` | `T10` | gross_margin formula is outdated; correct to manual-recovery semantics |

## Property evidence matrix

`schema_ref:` `canonical.schema.validation_evidence.v1`
`instance_binding:` `validation_evidence_refs` / `property_evidence_matrix_ref`
Exit-0 alone is insufficient when property needs structural/runtime proof (PLAN-SCHEMA-008).

| evidence_id | claim_id / SP | evidence_kind | method | command | expected_positive | status |
|-------------|---------------|---------------|--------|---------|-------------------|--------|
| E-V1 | SP-01, SP-03 | `quality_gate_evidence` | command | `make test-module m=plasticos_claims` | Odoo test summary present: 0 failed, 0 error, tests > 0; receipt written under .l9/runtime/test-env/ | `not_run` |
| E-V2 | SP-02 | `quality_gate_evidence` | command | `make test-module m=plasticos_commission` | Odoo test summary present: 0 failed, 0 error; TestTransactionACL fully green including test_base_user_cannot_write_tx_line | `not_run` |
| E-V3 | SP-04 | `quality_gate_evidence` | command | `make test-module m=plasticos_transaction` | Odoo test summary present: 0 failed, 0 error | `not_run` |
| E-V4 | SP-05 | `quality_gate_evidence` | command | `.venv/bin/ruff check . && .venv/bin/ruff format --check .` | No violations; no reformat needed | `not_run` |
| E-V5 | SP-05 | `quality_gate_evidence` | command | `pre-commit run --all-files --config .pre-commit-config.yaml` | All 36 hooks pass (Odoo patterns, ACL checks, gitleaks, wiring) | `not_run` |
| E-V6 | regression gate (no SP) | `quality_gate_evidence` | command | `make pr-check` | All local gates pass including ACL completeness, audit-baseline, semgrep, wiring | `not_run` |

## Stress and disconfirm

### Disconfirming cases

- Does any seed user, cron, or automation rely on blanket claim access rather than a claims group? (brief §5: SLA cron user is claims manager; workflow automations run sudo — verified safe; document upload is the one real dependency, handled by T5)
- Does deleting access_transaction_line_all break the CSV import wizard for legitimate users? (yes for non-managers — mitigated by T8 menu restriction per ADR-129 decision 3)
- Could the audit-baseline job flag the ACL CSV changes as regressions? (baseline tracks scanner findings, not ACL rows; T13 runs the gate to confirm)
- Do the rewritten bridge tests contradict any passing test elsewhere? (test_bridge_contracts.py:589-602 treats the fields as compute inputs — must be checked and aligned in T11)
- Does removing the dead compute change runtime behavior anywhere? (no field names the method; grep proves no caller — verified in P3 evidence)

### Assumption failure conditions

- ASSUMED FALSE: that some uninspected module grants claims access to ordinary users through a group not in the brief's inventory — if true, T9's no-group test fails and the extra grant must be inventoried before proceeding
- ASSUMED FALSE: that Odoo does not delete CSV-sourced ir.model.access records on module upgrade when the row is removed — if true, a migration must explicitly unlink the stale ACL records and T12 gains a migrations/ folder
- ASSUMED FALSE: that the unexpected unlink pass (T2) is caused by test-ordering flakiness rather than a real record rule — if true, ADR-129 must record the exposure as open and test_base_user_cannot_unlink may start failing after T7

### Blast radius notes

- Runtime access control on two business models (plasticos.claim, plasticos.transaction.line) for every internal user; claim auto-create on document upload; CSV import wizard availability; two test files and one test move across three modules. No schema changes, no data migrations expected, no partner/transaction data touched.

### Rollback constraints

- Every change is additive-or-restorable in git: revert the PR branch. ACL rows restore on module upgrade from the reverted CSVs. No destructive SQL, no data backfill, no column drops anywhere in scope.

### Risks

| risk | mitigation |
|------|------------|
| Deleting access_claim_all locks claim access away from a workflow the brief missed | T4 group implication covers QC/operations roles; T5 sudo covers uploads; C2 checkpoint verifies before proceeding; full module rosters run in T13 |
| Group implication XML on security_base groups from plasticos_claims creates an unexpected module-load-order issue | plasticos_claims already depends on plasticos_security_base; the crm_group_imply.xml precedent in plasticos_crm_bridge proves the pattern |
| test_bridge_contracts.py in plasticos_security_base still encodes the compute contract and goes red after T10 | T11 explicitly audits and aligns that file's lines 589-602 in the same change |
| Stale ir.model.access records persist in the Staging DB after CSV row removal | Verify on the Docker fixture clone after scoped upgrade in T13; add explicit migration only if proven needed |
| Commission earners lose a workflow that legitimately edited recovery_amount | ADR-129 records the decision that commission earners must not edit inputs to their own pay; claims groups are assigned deliberately, not by default |

## Out of scope

- The 30+ other blanket `_all` ACL rows across 13 addons (brief §9 inventory) — separate campaign
- ir.model.data and product.template exposures — separate high-priority findings
- access_transaction_all (transaction header row) removal — only investigated here (T2); removal deferred unless the probe proves it safe within this PR's test evidence
- Any computed conversion, backfill, or automation of freight_chargebacks / lightweight_penalties — operator-refused
- Record-rule redesign, company_id addition to plasticos.claim, savepoint rework of the import wizard exception handling
- Architecture redesign (unless plan_class + redesign_allowed)
- Force-push, hard-reset, admin-merge, secret exfil
- Weakening scanners / gates to obtain PASS
- Follow-on schema/platform evolution

## Follow-on milestone *(optional — keep separate; PLAN-SCHEMA-014)*

Not activated — PLAN_DOCUMENT declares no follow-on milestone; separate_plan_required `true` for any follow-on.

## Convergence

`schema_ref:` `canonical.schema.convergence_contract.v1`
`instance_binding:` `convergence_contract_ref` → `conv.plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1`
Convergence requires all blocking evidence + gates (PLAN-SCHEMA-015).

| Field | Value |
|-------|-------|
| convergence_id | `conv.plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1` |
| source_ref | `plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1` |
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

- **required_evidence_refs:** E-V1, E-V2, E-V3, E-V4, E-V5, E-V6
- **observed_evidence_refs:** none
- **missing_evidence:** E-V1, E-V2, E-V3, E-V4, E-V5, E-V6

### Blockers / unknowns

| kind | id | note | resolution |
|------|----|------|------------|
| `unknown` | U1 | Exact mechanism behind the unexpected test_base_user_cannot_unlink pass on plasticos.transaction — Determines whether access_transaction_all can ever be safely removed in a follow-up; does not block this PR's scope | `probe` |
| `unknown` | U2 | Whether any production/Staging users outside admin hold data that depends on blanket claim access — Could require assigning claims groups to specific real users at deploy time | `accept_bounded` |
| `unknown` | U3 | Whether Odoo deletes CSV-sourced ACL records on upgrade when rows are removed — If not, T12 adds a migration to unlink stale rows | `probe` |
| `open_blocker` | stop_reason | Plan validated and ready for Build; U1/U3 are in-plan probes (T2, T13), not blockers. Build approval constitutes operator sign-off of the ADR-129 role matrix stated in T1. | planning convergence `partial` |

### Next

| Field | Value |
|-------|-------|
| next_convergence_gate | `executable_when` |
| minimum_safe_next_action | When law holds and status=`executable`, press **Build**, stack if any open PR exists (`PR_STACK=auto`), then `make pr` and display the PR URL — do not free-form execute |
| execute_via | Cursor Build; stacked PR if any open PR exists; display PR URL |
| next_skill | Build then stacked make pr |
| broader_work_requires_separate_contract | `true` |

---

## Machine stub (optional YAML instance seed)

Projected from PLAN_DOCUMENT; keep in sync with the sections above.

```yaml
schema_id: "canonical.schema.plan_document.v1"
schema_version: "1.0"
metadata:
  plan_id: "plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1"
  name: "Resolve preserved-red findings — claims/transaction-line ACL exposures (F-C1..C3) and recovery-field semantics (F-A1/A2)"
  overview: "Close the five preserved-red findings from the PR #303 enterprise validation without violating the standing operator decisions of 2026-10-25. Track C (F-C1..C3): adopt an explicit claims/transaction-line role matrix as ADR-129, then make the minimal ACL corrections — delete the two blanket `_all` CRUD rows (`access_claim_all` on plasticos.claim, `access_transaction_line_all` on plasticos.transaction.line), wire QC/operations managers into the claims groups via the established group-imply pattern, give the claim-photo auto-create a justified scoped sudo, and restrict the CSV transaction-import menu to managers — so TestClaimACL.test_claim_user_cannot_unlink, TestClaimACL.test_no_group_cannot_read and TestTransactionACL.test_base_user_cannot_write_tx_line pass for the right reason. Track A (F-A1/A2): encode the operator-decided manual recovery semantics (BUSINESS_SEMANTICS_UNRESOLVED — no auto-flow from resolved claims) by deleting the dead `_compute_chargebacks_penalties` code in both modules, correcting the misleading docstrings/help text, and rewriting the two claims-bridge tests to assert manual-entry semantics instead of the never-implemented auto-compute contract. No blanket sudo, no multi-addon ACL refactor, no computed conversion or backfill of recovery fields."
  status: "draft"
  is_project: false
architect_framing:
  planning_ssot: "PLAN_DOCUMENT"
  plan_class: "bounded_execution_contract"
  redesign_allowed: false
  follow_on_schema_evolution_separate: true
immutable_baseline:
  repository: "cryptoxdog/IB-Odoo_19"
  commit_sha: "50e655701e89405626367f8e0ea8eb7365008281"
  dirty: "true"
  overlap_policy: "stop_if_dirty_overlaps_may_modify"
  verification_rule: "reverify_at_execution_start"
  on_drift: "stop_and_replan"
objective:
  mission: "Close the five preserved-red findings from the PR #303 enterprise validation without violating the standing operator decisions of 2026-10-25. Track C (F-C1..C3): adopt an explicit claims/transaction-line role matrix as ADR-129, then make the minimal ACL corrections — delete the two blanket `_all` CRUD rows (`access_claim_all` on plasticos.claim, `access_transaction_line_all` on plasticos.transaction.line), wire QC/operations managers into the claims groups via the established group-imply pattern, give the claim-photo auto-create a justified scoped sudo, and restrict the CSV transaction-import menu to managers — so TestClaimACL.test_claim_user_cannot_unlink, TestClaimACL.test_no_group_cannot_read and TestTransactionACL.test_base_user_cannot_write_tx_line pass for the right reason. Track A (F-A1/A2): encode the operator-decided manual recovery semantics (BUSINESS_SEMANTICS_UNRESOLVED — no auto-flow from resolved claims) by deleting the dead `_compute_chargebacks_penalties` code in both modules, correcting the misleading docstrings/help text, and rewriting the two claims-bridge tests to assert manual-entry semantics instead of the never-implemented auto-compute contract. No blanket sudo, no multi-addon ACL refactor, no computed conversion or backfill of recovery fields."
  success_properties:
    - id: "SP-01"
      property: "TestClaimACL.test_claim_user_cannot_unlink and test_no_group_cannot_read raise AccessError and pass on the Docker fixture — proof V1"
      evidence_type: "quality_gate"
      proof: ["V1"]
      blocking: true
    - id: "SP-02"
      property: "TestTransactionACL.test_base_user_cannot_write_tx_line raises AccessError and passes; the previously-unexpected pass of test_base_user_cannot_unlink has an identified, ADR-documented mechanism — proof V2"
      evidence_type: "quality_gate"
      proof: ["V2"]
      blocking: true
    - id: "SP-03"
      property: "test_freight_chargeback_recovery_flows_to_transaction and test_lightweight_penalty_recovery_flows_to_transaction are rewritten to the manual-semantics contract and pass; no `_compute_chargebacks_penalties` remains in the codebase — proof V1"
      evidence_type: "quality_gate"
      proof: ["V1"]
      blocking: true
    - id: "SP-04"
      property: "Claim photo upload by a non-claims user still creates the claim (scoped sudo), and the full claims/transaction/commission module test rosters pass — proof V3"
      evidence_type: "quality_gate"
      proof: ["V3"]
      blocking: true
    - id: "SP-05"
      property: "ruff check and format are clean and the full local gate passes — proof V4 and V5"
      evidence_type: "quality_gate"
      proof: ["V4", "V5"]
      blocking: true
capability_preflight_ref: "preflight.plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1"
execution_envelope:
  filesystem:
    write_allow: ["plasticos_claims/security/ir.model.access.csv", "plasticos_claims/security/claims_group_imply.xml", "plasticos_claims/models/document_inherit.py", "plasticos_claims/models/transaction_claims.py", "plasticos_claims/models/claim.py", "plasticos_claims/views/claim_menus.xml", "plasticos_claims/tests/", "plasticos_claims/__manifest__.py", "plasticos_transaction/security/ir.model.access.csv", "plasticos_transaction/models/transaction.py", "plasticos_transaction/views/transaction_import_wizard_views.xml", "plasticos_transaction/README.md", "plasticos_transaction/__manifest__.py", "plasticos_commission/tests/test_security_acl.py", "plasticos_commission/__manifest__.py", "docs/adr/ADR-129-claims-roles-and-recovery-semantics.md", "docs/adr/README.md"]
    write_deny: ["pipeline_v2.py (hard CI guard)", "plasticos_web_leads/** (rule 50 guard; out of scope)", "plasticos_transaction/security/ir.model.access.csv row access_transaction_all (U1 unresolved)", "freight_chargebacks/lightweight_penalties field definitions (stay plain Float — operator decision)", "plasticos_security_base/security/security_groups.xml group definitions (implication lives in plasticos_claims)", "Any other module's ACL CSV (brief §9 inventory is a separate campaign)"]
  commands:
    allow: ["make test-module m=plasticos_claims", "make test-module m=plasticos_commission", "make test-module m=plasticos_transaction", ".venv/bin/ruff check . && .venv/bin/ruff format --check .", "make pr-check", "pre-commit run --all-files --config .pre-commit-config.yaml"]
  network:
    mode: "unknown — not declared in PLAN_DOCUMENT; resolve before status `executable`"
  secrets:
    access: "unknown — not declared in PLAN_DOCUMENT; resolve before status `executable`"
    redaction_required: true
  autonomous_merge: false
side_effects_and_idempotency:
  - todo_id: "T1"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T2"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T3"
    side_effects: "destructive_filesystem_mutation"
    idempotency: "unsafe_blind_repeat"
    retry: "manual_only"
  - todo_id: "T4"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T5"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T6"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T7"
    side_effects: "destructive_filesystem_mutation"
    idempotency: "unsafe_blind_repeat"
    retry: "manual_only"
  - todo_id: "T8"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T9"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T10"
    side_effects: "destructive_filesystem_mutation"
    idempotency: "unsafe_blind_repeat"
    retry: "manual_only"
  - todo_id: "T11"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T12"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
  - todo_id: "T13"
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
rollback_contract_ref: "rollback.plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1"
dependency_topology_ref: "dag.plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1"
validation_evidence_refs: ["E-V1", "E-V2", "E-V3", "E-V4", "E-V5", "E-V6"]
stress_and_disconfirm:
  disconfirming_cases: ["Does any seed user, cron, or automation rely on blanket claim access rather than a claims group? (brief §5: SLA cron user is claims manager; workflow automations run sudo — verified safe; document upload is the one real dependency, handled by T5)", "Does deleting access_transaction_line_all break the CSV import wizard for legitimate users? (yes for non-managers — mitigated by T8 menu restriction per ADR-129 decision 3)", "Could the audit-baseline job flag the ACL CSV changes as regressions? (baseline tracks scanner findings, not ACL rows; T13 runs the gate to confirm)", "Do the rewritten bridge tests contradict any passing test elsewhere? (test_bridge_contracts.py:589-602 treats the fields as compute inputs — must be checked and aligned in T11)", "Does removing the dead compute change runtime behavior anywhere? (no field names the method; grep proves no caller — verified in P3 evidence)"]
  assumption_failure_conditions: ["ASSUMED FALSE: that some uninspected module grants claims access to ordinary users through a group not in the brief's inventory — if true, T9's no-group test fails and the extra grant must be inventoried before proceeding", "ASSUMED FALSE: that Odoo does not delete CSV-sourced ir.model.access records on module upgrade when the row is removed — if true, a migration must explicitly unlink the stale ACL records and T12 gains a migrations/ folder", "ASSUMED FALSE: that the unexpected unlink pass (T2) is caused by test-ordering flakiness rather than a real record rule — if true, ADR-129 must record the exposure as open and test_base_user_cannot_unlink may start failing after T7"]
out_of_scope: ["The 30+ other blanket `_all` ACL rows across 13 addons (brief §9 inventory) — separate campaign", "ir.model.data and product.template exposures — separate high-priority findings", "access_transaction_all (transaction header row) removal — only investigated here (T2); removal deferred unless the probe proves it safe within this PR's test evidence", "Any computed conversion, backfill, or automation of freight_chargebacks / lightweight_penalties — operator-refused", "Record-rule redesign, company_id addition to plasticos.claim, savepoint rework of the import wizard exception handling"]
convergence_contract_ref: "conv.plan.simple.resolve_preserved_red_findings_claims_transaction_line_acl_exposures_f_c1_c3_and_recovery_field_semantics_f_a1_a2.v1"
execute_via:
  pipeline: cursor-build
  mention_program: "Cursor Build"
  command_ref: PR_STACK=auto make pr
  authority_order:
    - plan_document
    - cursor_build
todos:
  - id: "T1"
    content: "Write ADR-129 recording (a) the approved claims role matrix: claims_user = read/write/create no-unlink, claims_manager = full CRUD, qc_manager implies claims_user, operations_manager implies claims_manager, plain internal users = no claim access; (b) transaction lines: internal users read-only, logistics RWC, plasticos manager CRUD, no blanket row; (c) recovery semantics per operator decision 2026-10-25: freight_chargebacks and lightweight_penalties are manual fields, resolving a claim never auto-writes them, archiving never erases them; (d) the T2 probe finding for the unexpected unlink pass. Build approval of this plan constitutes operator sign-off of this matrix."
    status: "pending"
  - id: "T2"
    content: "Probe (read-only) why TestTransactionACL.test_base_user_cannot_unlink unexpectedly passes while access_transaction_all grants delete: inspect plasticos_transaction/security/security_hardening.xml and plasticos_security_base/security/record_rules.xml for the denying mechanism; record the identified mechanism in ADR-129. Do not remove access_transaction_all in this PR."
    status: "pending"
  - id: "T3"
    content: "Delete the blanket row `access_claim_all` (base.group_system row `access_claim_all` named at CSV line 5 grants base.group_system — verify exact row: the blanket row grants base.group_system per current CSV read; the brief pins the blanket as the row granting full CRUD beyond group rows. Read the CSV first per rule 71, remove only the row granting full CRUD to base.group_user/All-users on plasticos.claim, keep group_claims_user 1,1,1,0 and group_claims_manager 1,1,1,1 and the base.group_system row)."
    status: "pending"
  - id: "T4"
    content: "Add security/claims_group_imply.xml in plasticos_claims (crm_group_imply.xml pattern): group_qc_manager gains implied group_claims_user; group_operations_manager gains implied group_claims_manager. Register in manifest data list. This preserves real claim workflows for the roles that legitimately need them after the blanket row is gone."
    status: "pending"
  - id: "T5"
    content: "In plasticos_claims/models/document_inherit.py, run the claim search/create for tagged photo uploads via a scoped sudo() with inline justification (uploader may lack claims groups; claim auto-create is a system behavior; uploader attribution preserved in the record body/notes). Keep the rest of the method as-user."
    status: "pending"
  - id: "T6"
    content: "Scope claims UI to claims groups: add groups= to the Claims menus (claim_menus.xml) and to the transaction Claims smart button / action so non-claims internal users do not hit AccessError from navigation."
    status: "pending"
  - id: "T7"
    content: "Delete `access_transaction_line_all` (the base.group_user full-CRUD duplicate on plasticos.transaction.line) from plasticos_transaction/security/ir.model.access.csv, leaving base.group_user read-only, logistics RWC (security_base), and group_plasticos_manager CRUD. Read the full CSV first per rule 71."
    status: "pending"
  - id: "T8"
    content: "Restrict the CSV transaction-import wizard menu to plasticos_transaction.group_plasticos_manager (menu currently ungrouped; wizard creates lines as the current user and would partial-save for users stripped of create rights by T7)."
    status: "pending"
  - id: "T9"
    content: "Move TestClaimACL from plasticos_commission/tests/test_security_acl.py (line 194) into a new plasticos_claims/tests/test_claim_acl.py (plasticos_commission does not depend on plasticos_claims, so its setup silently drops the claims group — fragile). Keep TestTransactionACL in place. Wire the new file into plasticos_claims/tests/__init__.py."
    status: "pending"
  - id: "T10"
    content: "Remove dead recovery-compute code: delete _compute_chargebacks_penalties override in plasticos_claims/models/transaction_claims.py (lines ~45-70) and the dead fallback in plasticos_transaction/models/transaction.py (~line 843); fix action_resolve docstring in claim.py (references nonexistent _update_transaction_recoveries); correct freight_chargebacks/lightweight_penalties help text and the plasticos_transaction README gross_margin formula to state manual entry per ADR-129."
    status: "pending"
  - id: "T11"
    content: "Rewrite test_freight_chargeback_recovery_flows_to_transaction and test_lightweight_penalty_recovery_flows_to_transaction in plasticos_claims/tests/test_depends_transaction_claims_bridge.py to encode manual semantics: resolving a claim leaves transaction recoveries at 0.0; a manual write of freight_chargebacks/lightweight_penalties flows into gross_margin via _compute_financials; archiving a resolved claim does not erase manual values."
    status: "pending"
  - id: "T12"
    content: "Bump __manifest__.py versions of every runtime-changed module (plasticos_claims, plasticos_transaction, plasticos_commission) to the next 19.0.X.Y.Z; ruff format manifests after edit. Scoped upgrades only: make update m=plasticos_claims,plasticos_transaction,plasticos_commission equivalents — never update-all."
    status: "pending"
  - id: "T13"
    content: "Run the Docker-fixture module tests for the three affected modules, then ruff and the full local gate; attach the test receipt."
    status: "pending"
```
