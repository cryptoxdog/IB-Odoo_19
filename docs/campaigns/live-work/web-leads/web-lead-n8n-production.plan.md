---
name: Land Cognito leads in Production through the active n8n workflow
overview: "Keep the active n8n workflow Web Lead Triage - PRODUCTION - Attachments v5.5.2 (id 5NjFkIFOBDWsMLyk) as the Cognito ingress and make one real submission create exactly one Production plasticos.web.lead. The workflow was last saved 2026-08-29. Its webhook connects only to POST Raw Cognito to Staging Odoo at https://cryptoxdog-ib-odoo-19-staging-36099032.dev.odoo.com/api/v1/cognito-webhook, a dro..."
todos:
  - id: T1
    content: "On Production only, prove the installed web-lead module, an active config, and that a bearer matching that config is accepted by POST /api/v1/cognito-webhook. Compare the Infisical ODOO_WEB_LEAD_API_KEY, the disabled n8n literal, and the credential named Odoo Staging Web Lead Bearer by equality to the Production key. Do not print secrets. Record HTTP status and whether a synthetic invalid token returns 401."
    status: pending
    phase: execute
    depends_on: []
  - id: T2
    content: "Save a GET export of the workflow outside the repository first, because it contains the literal bearer. In the active workflow, enable POST Raw Cognito to Production Odoo, point the webhook edge at it, authenticate with a Production bearer credential rather than the embedded literal or the staging-named credential, and disconnect the dropped staging host from Normalize Odoo Delivery. Leave the workflow active and keep posting the raw Cognito body. If the n8n API key cannot create or attach credentials, stop and have the operator attach the credential in the n8n editor."
    status: pending
    phase: execute
    depends_on: [T1]
  - id: T3
    content: "Change plasticos_web_leads only if T1 shows Production rejects the live Cognito body or stores empty company, contact, material, or quantity for values the form sent. Read .cursor/rules/50-plasticos-web-lead-guard.mdc first. Edit fix/web-lead-n8n-production, which contains PR #366: create_from_cognito and _merge_ai_data at 19.0.2.8.7, keeping split_material_code and the form/grade split. Bump to 19.0.2.8.8. Run make test-module m=plasticos_web_leads before and after. This fix reaches Production only through a whole Staging promotion, which is an operator decision outside this campaign."
    status: pending
    phase: execute
    depends_on: [T1]
  - id: T4
    content: "Correct ADR-020 so it states the live quote form still posts to n8n workflow 5NjFkIFOBDWsMLyk, which then posts raw JSON to Production /api/v1/cognito-webhook. Replace the line that says n8n is no longer on the path, and mark the step that retires the workflow and the N8N_* Infisical names as not done in this campaign."
    status: pending
    phase: execute
    depends_on: [T2]
  - id: T5
    content: "Submit one synthetic Cognito entry through the existing form, correlate Entry.Number to the n8n execution and to exactly one Production web lead, and confirm the final gate reports odooStatus success with web_lead_id. Check fields against the Production 19.0.2.6.0 mapping, not the PR #366 form/grade split. Do not resubmit a customer entry."
    status: pending
    phase: execute
    depends_on: [T2]
  - id: T6
    content: "Publish stacked on PR #366 from fix/web-lead-n8n-production, which already holds commit 4fb22532 (nested stacking in scripts/pr_stack_parent.sh). Commit the plan JSON, plan markdown, section receipt, the T4 ADR edit, and any T3 change onto that branch. Before publishing, git fetch origin and run git merge-tree --write-tree HEAD against origin/feat/web-lead-material-grade, origin/fix/material-ledger-normalizer, and origin/Staging. If #366 moved, merge origin/feat/web-lead-material-grade into the branch. If #365 merged and #366 now targets Staging, the same command still applies. Resolve every conflict, keeping #366 code and only this campaign's lines, then rerun ruff check, ruff format, python -m pytest tests/test_make_pr_publication.py, and make test-module m=plasticos_web_leads if T3 ran. Publish only with PR_CHECK_SCOPE=full make pr base=feat/web-lead-material-grade so install-smoke runs on the fixture clone."
    status: pending
    phase: execute
    depends_on: [T1, T4]
isProject: false
kind: simple
execute_via: cursor-build
status: current
---

# PLAN: Land Cognito leads in Production through the active n8n workflow

> **Projected by** `scripts/render_plan_pe_autonomy.py` from validated PLAN_DOCUMENT JSON.

> **First-class SSOT (git):** `environment/contracts/execution/templates/canonical.template.executable_plan.v1.plan.md` · metadata sidecar `*.meta.md` · registered in `environment/contracts/execution/MANIFEST.yaml`. Skill path is a symlink; `.cursor/plans/_TEMPLATE.plan.md` is a local mirror only.
> **Schema:** `canonical.schema.plan_document.v1` (status: fill → `executable` only when law holds)
> **Parameters:** every value is projected from PLAN_DOCUMENT. A value reading `unknown — …` or `unbound — …` is absent from PLAN_DOCUMENT and must be resolved before status becomes `executable`.
> **Execute:** when status is `executable`, press **Build**, stack on the unique open-PR tip if any open PR exists (`PR_STACK=auto`; never `origin/main`), then `PR_STACK=auto PR_REMEDIATE=0 make pr` and display the PR URL. Do **not** run `make campaign`, admit a Program Lock, or free-form mutate from this markdown alone.
> **Cursor todos:** frontmatter `todos` project to Build todos. Body is the binding contract.
> **File name:** `land_cognito_leads_in_production_through_the_active_n8n_workflow_b9a799e2.plan.md`
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
| plan_id | `plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1` |
| name | Land Cognito leads in Production through the active n8n workflow |
| overview | Keep the active n8n workflow Web Lead Triage - PRODUCTION - Attachments v5.5.2 (id 5NjFkIFOBDWsMLyk) as the Cognito ingress and make one real submission create exactly one Production plasticos.web.lead. The workflow was last saved 2026-08-29. Its webhook connects only to POST Raw Cognito to Staging Odoo at https://cryptoxdog-ib-odoo-19-staging-36099032.dev.odoo.com/api/v1/cognito-webhook, a dropped host that resolves to 0.0.0.0. POST Raw Cognito to Production Odoo is disabled, absent from connections, uses authentication none, carries a literal Authorization bearer, and attaches the credential named Odoo Staging Web Lead Bearer. Normalize Odoo Delivery and Final Production Gate judge only that staging response, so a dead staging hop fails the run before Production is called. Production git 3318fa646a9f33aed55b9ea8f8596316e30684da (2026-06-04, plasticos_web_leads 19.0.2.6.0) already accepts Bearer POST /api/v1/cognito-webhook through receive_cognito_webhook and create_from_cognito (origin/Production plasticos_web_leads/models/web_lead.py:372) and maps the live form fields. Staging 4a6af0b2d5bbf8f16e4fa67baafe9d71e3b4f384 (19.0.2.8.6) is not required for that contract. Open PR #365 (fix/material-ledger-normalizer into Staging) rewrites plasticos_material_profile/models/material_normalizer.py onto named _Spec slots. Open PR #366 (feat/web-lead-material-grade, head 46aece9f, base fix/material-ledger-normalizer) bumps plasticos_web_leads to 19.0.2.8.7 and splits one material code into form or material grade (material_identity.split_material_code against plasticos_material_profile.grade_codes.GRADE_CODES). Neither PR is on Production. This campaign publishes stacked on #366 with the full smoke gate from branch fix/web-lead-n8n-production, cut from #366 head 46aece9f. Its first commit 4fb22532 lets scripts/pr_stack_parent.sh prove follow a parent PR chain (#366 to #365 to Staging), so publication does not wait for #365 to merge. MEMORY_PREFETCH snapshot_digest f9e69f08f9a92e10ba5df37f8f63f47d30e1253bc3ddb67f9174c8c12c3bc5d2 conflicts 0. The n8n MCP server exposes node documentation only, so the live workflow was read with a GET and was not uploaded. |
| schema_version | `1` |
| status | `draft` — planning convergence is `partial` |
| is_project | `false` |
| owner | igor_beylin |
| created_at | 2026-11-04T21:15:21+00:00 |
| updated_at | 2026-11-04T21:15:21+00:00 |
| depth | `deep` |
| estimate | one execution session after a read-only Production proof, then one stacked make pr |

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
| captured_at | `2026-11-04T21:15:21+00:00` |
| repository | `cryptoxdog/IB-Odoo_19` |
| workspace | `/Users/ib-mac/IB-Odoo_19 (LOCAL)/IB-Odoo_19` |
| branch | `fix/web-lead-n8n-production` |
| commit_sha | `4fb22532fa8aca0d76372a2d1bd975fa9000738b` |
| dirty | `true` |
| artifact_hashes | `{}` — none pinned by PLAN_DOCUMENT |
| allowed_local_dirt | none |
| overlap_policy | `stop_if_dirty_overlaps_may_modify` |
| verification_rule | `reverify_at_execution_start` |
| on_drift | `stop_and_replan` |

## Objective

### Mission

Keep the active n8n workflow Web Lead Triage - PRODUCTION - Attachments v5.5.2 (id 5NjFkIFOBDWsMLyk) as the Cognito ingress and make one real submission create exactly one Production plasticos.web.lead. The workflow was last saved 2026-08-29. Its webhook connects only to POST Raw Cognito to Staging Odoo at https://cryptoxdog-ib-odoo-19-staging-36099032.dev.odoo.com/api/v1/cognito-webhook, a dropped host that resolves to 0.0.0.0. POST Raw Cognito to Production Odoo is disabled, absent from connections, uses authentication none, carries a literal Authorization bearer, and attaches the credential named Odoo Staging Web Lead Bearer. Normalize Odoo Delivery and Final Production Gate judge only that staging response, so a dead staging hop fails the run before Production is called. Production git 3318fa646a9f33aed55b9ea8f8596316e30684da (2026-06-04, plasticos_web_leads 19.0.2.6.0) already accepts Bearer POST /api/v1/cognito-webhook through receive_cognito_webhook and create_from_cognito (origin/Production plasticos_web_leads/models/web_lead.py:372) and maps the live form fields. Staging 4a6af0b2d5bbf8f16e4fa67baafe9d71e3b4f384 (19.0.2.8.6) is not required for that contract. Open PR #365 (fix/material-ledger-normalizer into Staging) rewrites plasticos_material_profile/models/material_normalizer.py onto named _Spec slots. Open PR #366 (feat/web-lead-material-grade, head 46aece9f, base fix/material-ledger-normalizer) bumps plasticos_web_leads to 19.0.2.8.7 and splits one material code into form or material grade (material_identity.split_material_code against plasticos_material_profile.grade_codes.GRADE_CODES). Neither PR is on Production. This campaign publishes stacked on #366 with the full smoke gate from branch fix/web-lead-n8n-production, cut from #366 head 46aece9f. Its first commit 4fb22532 lets scripts/pr_stack_parent.sh prove follow a parent PR chain (#366 to #365 to Staging), so publication does not wait for #365 to merge. MEMORY_PREFETCH snapshot_digest f9e69f08f9a92e10ba5df37f8f63f47d30e1253bc3ddb67f9174c8c12c3bc5d2 conflicts 0. The n8n MCP server exposes node documentation only, so the live workflow was read with a GET and was not uploaded.

### Scope in

- Read-only proof of Production /api/v1/cognito-webhook, installed plasticos_web_leads 19.0.2.6.0 or newer, and that the presented bearer matches the Production web-lead config without printing the secret.
- n8n workflow 5NjFkIFOBDWsMLyk: enable and connect the Production POST, set Bearer auth from a Production credential, and remove the dropped staging host from the gate path.
- Conditional plasticos_web_leads change only if that Production proof shows rejection or empty mapping of the live Cognito body. The change is made on the PR #366 code (19.0.2.8.7) and bumps to 19.0.2.8.8.
- A short ADR-020 correction that the live form still enters through this n8n workflow and that n8n retirement is not part of this campaign.
- Publication of this plan, its receipt, the ADR correction, and any T3 change as one branch stacked on PR #366, full smoke, conflicts resolved first.
- Commit 4fb22532 on fix/web-lead-n8n-production: scripts/pr_stack_parent.sh prove walks each parent's single open PR down to Staging (at most five), and tests/test_make_pr_publication.py covers the two-level stack, a chain into Production, a loop, a broken chain, and a chain deeper than five.

### Success properties

Each property's proof is the `final_validation` entry it names (by id or by script/file). A property with no proving validation, or only skipped / not_applicable ones, blocks `executable`.

| id | property | evidence_type | proof | blocking |
|----|----------|---------------|-------|----------|
| SP-01 | V1: the active workflow webhook connects to an enabled Production POST, and the dropped staging host is not an input to Final Production Gate. | `quality_gate` | V1: `GET /api/v1/workflows/5NjFkIFOBDWsMLyk and trace Webhook to Normalize Odoo Delivery` → Workflow active. Enabled Production POST is the webhook successor. Host staging-36099032 is not on that path. Observed: 2026-11-04T21:11Z GET: active true, versionId == activeVersionId 803a3552. Webhook -> POST Raw Cognito to Production Odoo (enabled, httpBearerAuth credential Odoo Production Web Lead Bearer yqUODZ60YnNh1QNT, no literal header) -> Normalize Odoo Delivery. Staging node disabled, no outgoing edge, not an ancestor of Normalize Odoo Delivery or Final Production Gate. | `true` |
| SP-02 | V2: one Cognito Submit on form ScrapManagementInc1/4 creates exactly one Production plasticos.web.lead whose company, contact, material, and CG entry identity match the entry under the Production 19.0.2.6.0 mapping, with n8n odooStatus success and web_lead_id set. | `quality_gate` | V2: `Submit one synthetic Cognito entry and read the Production plasticos.web.lead plus the n8n execution` → One lead, matching company, contact, material, quantity, and CG entry id under the 19.0.2.6.0 mapping. n8n odooStatus success and web_lead_id present. No second lead. Observed: Cognito entry 9233 (Id 4-9233, form 4) -> n8n execution 71414 success in 39 s -> Production web_lead_id 88, lead_id CG-4-9233, decision cold, state skipped, partner_id null, intake_id null. Final Production Gate status success, odooStatus success, odooWebLeadId 88. Airtable recWrmTRFcwwIgH8M. Field values are inferred from origin/Production create_from_cognito and the present body keys; Production SSH port 22 was unreachable, so no direct row read. | `true` |
| SP-03 | V3: workflow 5NjFkIFOBDWsMLyk stays active, the customer form still posts to n8n, and no new middleware is added. | `quality_gate` | V3: `GET workflow active flag and confirm the Cognito form submit URL host is still ibeylin.app.n8n.cloud` → active true and the customer form was not repointed at Odoo. Observed: Workflow active true after the change; execution 71414 ran in webhook mode from the public form, so the form still posts to n8n. No middleware added. | `true` |
| SP-04 | V5: fix/web-lead-n8n-production is published by PR_CHECK_SCOPE=full make pr base=feat/web-lead-material-grade with install-smoke run, after every conflict against origin/feat/web-lead-material-grade and origin/Staging is resolved. | `quality_gate` | V5: `git fetch origin; bash scripts/pr_stack_parent.sh prove feat/web-lead-material-grade; git merge-tree --write-tree HEAD origin/feat/web-lead-material-grade; git merge-tree --write-tree HEAD origin/Staging; PR_CHECK_SCOPE=full make pr base=feat/web-lead-material-grade` → prove exits 0. Both merge-tree checks exit 0. scope.json reason is forced by PR_CHECK_SCOPE=full with smoke 1. install-smoke --resolve and --recheck pass. The PR base is feat/web-lead-material-grade. | `true` |

## Capability preflight

`schema_ref:` `canonical.schema.capability_preflight.v1`
`instance_binding:` `capability_preflight_ref` → `preflight.plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1`

| Field | Value |
|-------|-------|
| preflight_id | `preflight.plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1` |
| source_ref | `plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1` |
| phase_id | `preflight` |
| blocking | `true` |
| immutable_baseline_ref | `baseline.plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1` |
| baseline_verified | `false` — reverify at execution start |
| drift_detected | `false` — baseline captured at render |

### Probes (from PLAN_DOCUMENT `pre_validation`; failed blocking probe → status `preflight_blocked`)

| id | capability | command_or_action | pass_criteria | blocking |
|----|------------|-------------------|---------------|----------|
| PV1 | pre-validation (status `passed`) | `git rev-parse origin/Staging origin/Production and compare plasticos_web_leads` | Staging is 4a6af0b2 and Production is 3318fa64; Production controller still exposes Bearer POST /api/v1/cognito-webhook and maps YourBusinessCompanyName, WhatIsIt, WeightPerLoad, and UploadPhotosOfYourScrapUpTo10. | `true` |
| PV2 | pre-validation (status `passed`) | `GET https://ibeylin.app.n8n.cloud/api/v1/workflows/5NjFkIFOBDWsMLyk` | Workflow is active. Webhook connects only to the staging node. Production node is disabled and absent from connections. Its credential name is Odoo Staging Web Lead Bearer and its Authorization header is a literal bearer. | `true` |
| PV3 | pre-validation (status `passed`) | `python3 $HOME/.cursor-governance/skills/l9-plan/scripts/route_plan.py --risk high --evidence sufficient --json` | depth deep and omit_gates empty. Hook catalog for any later code edit is .pre-commit-config.yaml. | `true` |
| PV4 | pre-validation (status `passed`) | `gh pr list --state open and gh pr view 365 366 --json files,baseRefName,headRefOid,mergeStateStatus` | #365 is fix/material-ledger-normalizer into Staging, CLEAN. #366 is feat/web-lead-material-grade at 46aece9f into fix/material-ledger-normalizer, CLEAN, CI Gate Result success. #366 changes plasticos_web_leads (web_lead.py, material_identity.py, manifest 19.0.2.8.7) and does not change the controller or the Bearer contract. | `true` |
| PV5 | pre-validation (status `passed`) | `git merge-tree --write-tree HEAD <ref> for origin/feat/web-lead-material-grade, origin/fix/material-ledger-normalizer, and origin/Staging` | All three report no conflict at 2026-11-04. Re-run in T6 against the live heads. | `true` |
| PV6 | pre-validation (status `passed`) | `Read scripts/pr_stack_parent.sh, scripts/git_push_with_pr.sh, and scripts/pr_check_scope.py; run GH_REPO=cryptoxdog/IB-Odoo_19 bash scripts/pr_stack_parent.sh prove feat/web-lead-material-grade on 4fb22532` | On Staging, prove required the parent branch to have one open PR into Staging and refused #366. On 4fb22532, prove follows #366 to fix/material-ledger-normalizer to Staging and exits 0; the Staging copy of the script exits 1 on the same input. PR_CHECK_SCOPE=full forces audit, smoke, and all tests. make pr refuses PR_CHECK_FORCE_SMOKE and PR_CHECK_SKIP_SMOKE. | `true` |
| PV7 | pre-validation (status `passed`) | `python -m pytest tests/test_make_pr_publication.py; shellcheck scripts/pr_stack_parent.sh; pre-commit run --files scripts/pr_stack_parent.sh tests/test_make_pr_publication.py` | 70 passed, shellcheck clean, every pre-commit hook passed on 4fb22532. | `true` |
| PV8 | pre-validation (status `passed`) | `T1 Production probes: GET /api/v1/web-lead/health; POST /api/v1/web-lead with a wrong bearer, the Infisical key, and the n8n literal, body without decision; POST /api/v1/web-lead/inbound/cognito` | Observed 2026-11-04: health 200 ok; wrong bearer 401 Invalid API key on /api/v1/web-lead and /api/v1/cognito-webhook; Infisical ODOO_WEB_LEAD_API_KEY and the n8n literal both 422 Missing required field: decision (accepted, no write); literal equals the Infisical key; inbound route 404, so Production predates 19.0.2.8.x. | `true` |

## Execution envelope

Mutations outside this envelope are forbidden (PLAN-SCHEMA-004).

### Filesystem

- **write_allow:** `n8n workflow 5NjFkIFOBDWsMLyk connections, disabled flag, and Production node auth`, `docs/adr/ADR-020-web-lead-inbound-port.md`, `docs/campaigns/10-29-26/web-leads/web-lead-n8n-production.plan.json, .plan.md, and .plan.section-receipt.json`, `scripts/pr_stack_parent.sh and tests/test_make_pr_publication.py (committed as 4fb22532)`, `plasticos_web_leads/models/web_lead.py and __manifest__.py only after T1 fails the live payload`
- **write_deny:** `Cognito form ScrapManagementInc1/4 submit destination`, `n8n workflow active flag set to false`, `plasticos_web_leads write guard, unlink guard, and partner-deferral path`, `plasticos_web_leads material_identity.split_material_code and the PR #366 form/grade split`, `plasticos_material_profile, plasticos_crm_sync, plasticos_transaction, plasticos_intake_normalizer`, `PR #365 and PR #366 branches, bases, or merge state`, `pipeline_v2.py`, `unrelated Staging modules on the Production promotion`
- **delete_allow:** none — no Delete todo

### Commands

- **allow:** `GET /api/v1/workflows/5NjFkIFOBDWsMLyk`, `POST /api/v1/cognito-webhook with a wrong bearer expects 401`, `one synthetic Cognito submit correlated to one Production web lead`, `GH_REPO=cryptoxdog/IB-Odoo_19 bash scripts/pr_stack_parent.sh prove feat/web-lead-material-grade`, `git merge-tree --write-tree HEAD origin/feat/web-lead-material-grade`, `PR_CHECK_SCOPE=full make pr base=feat/web-lead-material-grade`, `GET /api/v1/workflows/5NjFkIFOBDWsMLyk and trace Webhook to Normalize Odoo Delivery`, `Submit one synthetic Cognito entry and read the Production plasticos.web.lead plus the n8n execution`, `GET workflow active flag and confirm the Cognito form submit URL host is still ibeylin.app.n8n.cloud`, `If T3 edits plasticos_web_leads, run pre-commit against .pre-commit-config.yaml and make test-module m=plasticos_web_leads. If T3 is skipped, do not run a repo-wide hook sweep.`, `git fetch origin; bash scripts/pr_stack_parent.sh prove feat/web-lead-material-grade; git merge-tree --write-tree HEAD origin/feat/web-lead-material-grade; git merge-tree --write-tree HEAD origin/Staging; PR_CHECK_SCOPE=full make pr base=feat/web-lead-material-grade`
- **deny:** `git push --force`, `git reset --hard`, admin merge, committing secrets

### Network

| Field | Value |
|-------|-------|
| mode | `bounded_external_write` |
| allowed_services | `ibeylin.app.n8n.cloud`, `cryptoxdog-ib-odoo-19.odoo.com`, `github.com/cryptoxdog/IB-Odoo_19` |

### Secrets

| Field | Value |
|-------|-------|
| access | `read_only_named` |
| redaction_required | `true` |

### Autonomous merge

`autonomous_merge:` `false` always. This plan confers no merge authority.

### Preserved contracts

- Workflow remains the Cognito ingress
- POST body stays the raw Cognito JSON object
- Production response contract is status ok and web_lead_id
- Auth is Bearer against plasticos.web.lead.config
- No automatic res.partner creation
- make pr is the only publication command, stacked on feat/web-lead-material-grade, with PR_CHECK_SCOPE=full

## Side effects and idempotency

Required for every destructive / external-write TODO (PLAN-SCHEMA-005). One row per todo.

| todo_id | side_effects | idempotency | retry | compensation | irreversible |
|---------|--------------|-------------|-------|--------------|--------------|
| T1 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_web_leads/controllers/web_lead_api.py` | `false` |
| T2 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- n8n:workflow/5NjFkIFOBDWsMLyk` | `false` |
| T3 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_web_leads/models/web_lead.py plasticos_web_leads/__manifest__.py` | `false` |
| T4 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- docs/adr/ADR-020-web-lead-inbound-port.md` | `false` |
| T5 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- plasticos_web_leads/controllers/web_lead_api.py` | `false` |
| T6 | `filesystem_mutation` | `safe_with_dedupe` | `retry_once` | `git restore -- scripts/pr_stack_parent.sh tests/test_make_pr_publication.py docs/campaigns/10-29-26/web-leads/web-lead-n8n-production.plan.json docs/campaigns/10-29-26/web-leads/web-lead-n8n-production.plan.md docs/campaigns/10-29-26/web-leads/web-lead-n8n-production.plan.section-receipt.json docs/adr/ADR-020-web-lead-inbound-port.md` | `false` |

## Architecture impact

| todo_id | bounded_context | layer | owning_contract | prohibited |
|---------|-----------------|-------|-----------------|------------|
| T1 | `plasticos_web_leads/controllers` | `runtime` | `Workflow remains the Cognito ingress`, `POST body stays the raw Cognito JSON object`, `Production response contract is status ok and web_lead_id`, `Auth is Bearer against plasticos.web.lead.config`, `No automatic res.partner creation`, `make pr is the only publication command, stacked on feat/web-lead-material-grade, with PR_CHECK_SCOPE=full` | `Cognito form ScrapManagementInc1/4 submit destination`, `n8n workflow active flag set to false`, `plasticos_web_leads write guard, unlink guard, and partner-deferral path`, `plasticos_web_leads material_identity.split_material_code and the PR #366 form/grade split`, `plasticos_material_profile, plasticos_crm_sync, plasticos_transaction, plasticos_intake_normalizer`, `PR #365 and PR #366 branches, bases, or merge state`, `pipeline_v2.py`, `unrelated Staging modules on the Production promotion` |
| T2 | `n8n:workflow` | `external_system` | `Workflow remains the Cognito ingress`, `POST body stays the raw Cognito JSON object`, `Production response contract is status ok and web_lead_id`, `Auth is Bearer against plasticos.web.lead.config`, `No automatic res.partner creation`, `make pr is the only publication command, stacked on feat/web-lead-material-grade, with PR_CHECK_SCOPE=full` | `Cognito form ScrapManagementInc1/4 submit destination`, `n8n workflow active flag set to false`, `plasticos_web_leads write guard, unlink guard, and partner-deferral path`, `plasticos_web_leads material_identity.split_material_code and the PR #366 form/grade split`, `plasticos_material_profile, plasticos_crm_sync, plasticos_transaction, plasticos_intake_normalizer`, `PR #365 and PR #366 branches, bases, or merge state`, `pipeline_v2.py`, `unrelated Staging modules on the Production promotion` |
| T3 | `plasticos_web_leads` | `runtime` | `Workflow remains the Cognito ingress`, `POST body stays the raw Cognito JSON object`, `Production response contract is status ok and web_lead_id`, `Auth is Bearer against plasticos.web.lead.config`, `No automatic res.partner creation`, `make pr is the only publication command, stacked on feat/web-lead-material-grade, with PR_CHECK_SCOPE=full` | `Cognito form ScrapManagementInc1/4 submit destination`, `n8n workflow active flag set to false`, `plasticos_web_leads write guard, unlink guard, and partner-deferral path`, `plasticos_web_leads material_identity.split_material_code and the PR #366 form/grade split`, `plasticos_material_profile, plasticos_crm_sync, plasticos_transaction, plasticos_intake_normalizer`, `PR #365 and PR #366 branches, bases, or merge state`, `pipeline_v2.py`, `unrelated Staging modules on the Production promotion` |
| T4 | `docs/adr` | `docs` | `Workflow remains the Cognito ingress`, `POST body stays the raw Cognito JSON object`, `Production response contract is status ok and web_lead_id`, `Auth is Bearer against plasticos.web.lead.config`, `No automatic res.partner creation`, `make pr is the only publication command, stacked on feat/web-lead-material-grade, with PR_CHECK_SCOPE=full` | `Cognito form ScrapManagementInc1/4 submit destination`, `n8n workflow active flag set to false`, `plasticos_web_leads write guard, unlink guard, and partner-deferral path`, `plasticos_web_leads material_identity.split_material_code and the PR #366 form/grade split`, `plasticos_material_profile, plasticos_crm_sync, plasticos_transaction, plasticos_intake_normalizer`, `PR #365 and PR #366 branches, bases, or merge state`, `pipeline_v2.py`, `unrelated Staging modules on the Production promotion` |
| T5 | `plasticos_web_leads/controllers` | `assurance` | `Workflow remains the Cognito ingress`, `POST body stays the raw Cognito JSON object`, `Production response contract is status ok and web_lead_id`, `Auth is Bearer against plasticos.web.lead.config`, `No automatic res.partner creation`, `make pr is the only publication command, stacked on feat/web-lead-material-grade, with PR_CHECK_SCOPE=full` | `Cognito form ScrapManagementInc1/4 submit destination`, `n8n workflow active flag set to false`, `plasticos_web_leads write guard, unlink guard, and partner-deferral path`, `plasticos_web_leads material_identity.split_material_code and the PR #366 form/grade split`, `plasticos_material_profile, plasticos_crm_sync, plasticos_transaction, plasticos_intake_normalizer`, `PR #365 and PR #366 branches, bases, or merge state`, `pipeline_v2.py`, `unrelated Staging modules on the Production promotion` |
| T6 | `repository root` | `ops` | `Workflow remains the Cognito ingress`, `POST body stays the raw Cognito JSON object`, `Production response contract is status ok and web_lead_id`, `Auth is Bearer against plasticos.web.lead.config`, `No automatic res.partner creation`, `make pr is the only publication command, stacked on feat/web-lead-material-grade, with PR_CHECK_SCOPE=full` | `Cognito form ScrapManagementInc1/4 submit destination`, `n8n workflow active flag set to false`, `plasticos_web_leads write guard, unlink guard, and partner-deferral path`, `plasticos_web_leads material_identity.split_material_code and the PR #366 form/grade split`, `plasticos_material_profile, plasticos_crm_sync, plasticos_transaction, plasticos_intake_normalizer`, `PR #365 and PR #366 branches, bases, or merge state`, `pipeline_v2.py`, `unrelated Staging modules on the Production promotion` |

## Rollback

`schema_ref:` `canonical.schema.rollback_contract.v1`
`instance_binding:` `rollback_contract_ref` → `rollback.plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1`

| Field | Value |
|-------|-------|
| rollback_id | `rollback.plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1` |
| source_execution_ref | `plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1` |
| supported | `true` |
| automatic_allowed | `false` |
| approval_required | `false` |
| trigger_conditions | C1 fails (Production module version, active config, 401 for a wrong bearer, and a match/mismatch result for ODOO_WEB_LEAD_API_KEY, the n8n literal, and the staging-named credential. No secret values.) → Do not enable the Production node while it still sends the staging-named credential or an unproven literal.; C2 fails (GET workflow shows active true, webhook outgoing node is the enabled Production POST, and the staging host URL is not an ancestor of Normalize Odoo Delivery. The pre-change export exists outside the repository.) → Do not submit a form entry. Revert the n8n connections to the previous GET export.; C3 fails (Cognito entry number, n8n execution id, HTTP outcome, Production web_lead_id, and field values for company, contact, material, and quantity.) → If the gate fails or the lead is missing or empty, stop. Do not point the customer form at Odoo directly and do not disable n8n.; C4 fails (bash scripts/pr_stack_parent.sh prove feat/web-lead-material-grade exits 0. git merge-tree reports no conflict against origin/feat/web-lead-material-grade, origin/fix/material-ledger-normalizer, and origin/Staging at the pushed SHA. .cache/pr-check/scope.json records forced by PR_CHECK_SCOPE=full with smoke 1. make pr printed the PR URL with base feat/web-lead-material-grade.) → If prove refuses, read its reason; do not retarget #365 or #366 and do not publish on Staging instead. If a conflict remains or smoke fails, do not publish. |

### Strategies (typed — PLAN-SCHEMA-009)

| domain | mode | notes |
|--------|------|-------|
| code | `git_restore_scoped_paths` | Restore the workflow from the pre-change GET export ~/.cache/plasticos-web-lead/n8n-5NjFkIFOBDWsMLyk-pre-T2-20261104T160934.json (versionId 3e6bb9ef): disable the Production node, reconnect the webhook to the previous staging node, and do not change the Cognito form. If T3 shipped, revert that commit on the campaign branch; do not roll Production back to a build older than 3318fa64. Close the stacked PR if #366 is abandoned. Revert 4fb22532 to return prove to one-level stacking. |
| data | `none` | PLAN_DOCUMENT declares no data mutation |
| external_state | `none` | PLAN_DOCUMENT declares no external write |
| local_state | `git_restore_scoped_paths` | scoped to todo files |

### Irreversible operations

- none — no todo is marked `irreversible` (PLAN-SCHEMA-010)

### Rollback verification

- re-run `GET /api/v1/workflows/5NjFkIFOBDWsMLyk`
- re-run `POST /api/v1/cognito-webhook with a wrong bearer expects 401`
- re-run `one synthetic Cognito submit correlated to one Production web lead`
- re-run `GH_REPO=cryptoxdog/IB-Odoo_19 bash scripts/pr_stack_parent.sh prove feat/web-lead-material-grade`
- re-run `git merge-tree --write-tree HEAD origin/feat/web-lead-material-grade`
- re-run `PR_CHECK_SCOPE=full make pr base=feat/web-lead-material-grade`
- re-run `GET /api/v1/workflows/5NjFkIFOBDWsMLyk and trace Webhook to Normalize Odoo Delivery`
- re-run `Submit one synthetic Cognito entry and read the Production plasticos.web.lead plus the n8n execution`
- re-run `GET workflow active flag and confirm the Cognito form submit URL host is still ibeylin.app.n8n.cloud`
- re-run `If T3 edits plasticos_web_leads, run pre-commit against .pre-commit-config.yaml and make test-module m=plasticos_web_leads. If T3 is skipped, do not run a repo-wide hook sweep.`
- re-run `git fetch origin; bash scripts/pr_stack_parent.sh prove feat/web-lead-material-grade; git merge-tree --write-tree HEAD origin/feat/web-lead-material-grade; git merge-tree --write-tree HEAD origin/Staging; PR_CHECK_SCOPE=full make pr base=feat/web-lead-material-grade`

## Complexity and uncertainty

| Field | Value |
|-------|-------|
| complexity | `high` — highest todo risk across 6 todo(s) |
| uncertainty | `medium` — 3 unknown(s), 0 blocking |
| blast_radius | `high` — A wrong bearer or a still-connected dead host fails every new quote in the active workflow. A bad Production write creates a web lead and may create a HOT intake. It must not create a partner. Airtable and Drive steps downstream of a successful Odoo response stay in the workflow. The stacked PR adds docs and at most one web-lead change on top of #366; it cannot reach Production on its own. |
| architectural_boundaries_crossed | `Cognito form to n8n webhook`, `n8n HTTP node to Odoo Production cognito-webhook`, `Stacked publication onto PR #366 above PR #365` |
| external_systems_touched | `n8n workflow 5NjFkIFOBDWsMLyk`, `Odoo.sh Production`, `Cognito form ScrapManagementInc1/4`, `GitHub pull requests #365 and #366` |
| migration_required | `false` |
| unknown_dependency_count | `3` |

## Inventory and classification *(optional — activate if retire/migrate/replace)*

Not activated — PLAN_DOCUMENT declares no retire / migrate / replace inventory.

## Gated write pipeline *(optional — irreversible or external writes)*

Not activated — PLAN_DOCUMENT declares no irreversible or external write.

## Regeneration extinguishment *(optional — retirement/deprecation)*

Not activated — PLAN_DOCUMENT declares no retirement or deprecation.

## Execution DAG

`schema_ref:` `canonical.schema.dependency_topology.v1`
`instance_binding:` `dependency_topology_ref` → `dag.plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1`
Must be acyclic before status may become `executable` (PLAN-SCHEMA-007).

| Field | Value |
|-------|-------|
| topology_id | `dag.plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1` |
| topology_kind | `execution` |
| graph_type | `directed_acyclic_graph` |

### Nodes / edges

| id | task | owner | risk | effort | depends_on | outputs |
|----|------|-------|------|--------|------------|---------|
| T1 | On Production only, prove the installed web-lead module, an active config, and that a bearer matching that config is accepted by POST /api/v1/cognito-webhook. Compare the Infisical ODOO_WEB_LEAD_API_KEY, the disabled n8n literal, and the credential named Odoo Staging Web Lead Bearer by equality to the Production key. Do not print secrets. Record HTTP status and whether a synthetic invalid token returns 401. | Cursor Build agent | `medium` | small | `[]` | `plasticos_web_leads/controllers/web_lead_api.py` |
| T2 | Save a GET export of the workflow outside the repository first, because it contains the literal bearer. In the active workflow, enable POST Raw Cognito to Production Odoo, point the webhook edge at it, authenticate with a Production bearer credential rather than the embedded literal or the staging-named credential, and disconnect the dropped staging host from Normalize Odoo Delivery. Leave the workflow active and keep posting the raw Cognito body. If the n8n API key cannot create or attach credentials, stop and have the operator attach the credential in the n8n editor. | Cursor Build agent | `high` | small | `[T1]` | `n8n:workflow/5NjFkIFOBDWsMLyk` |
| T3 | Change plasticos_web_leads only if T1 shows Production rejects the live Cognito body or stores empty company, contact, material, or quantity for values the form sent. Read .cursor/rules/50-plasticos-web-lead-guard.mdc first. Edit fix/web-lead-n8n-production, which contains PR #366: create_from_cognito and _merge_ai_data at 19.0.2.8.7, keeping split_material_code and the form/grade split. Bump to 19.0.2.8.8. Run make test-module m=plasticos_web_leads before and after. This fix reaches Production only through a whole Staging promotion, which is an operator decision outside this campaign. | Cursor Build agent | `high` | medium | `[T1]` | `plasticos_web_leads/models/web_lead.py`, `plasticos_web_leads/__manifest__.py` |
| T4 | Correct ADR-020 so it states the live quote form still posts to n8n workflow 5NjFkIFOBDWsMLyk, which then posts raw JSON to Production /api/v1/cognito-webhook. Replace the line that says n8n is no longer on the path, and mark the step that retires the workflow and the N8N_* Infisical names as not done in this campaign. | Cursor Build agent | `low` | small | `[T2]` | `docs/adr/ADR-020-web-lead-inbound-port.md` |
| T5 | Submit one synthetic Cognito entry through the existing form, correlate Entry.Number to the n8n execution and to exactly one Production web lead, and confirm the final gate reports odooStatus success with web_lead_id. Check fields against the Production 19.0.2.6.0 mapping, not the PR #366 form/grade split. Do not resubmit a customer entry. | Cursor Build agent | `high` | small | `[T2]` | `plasticos_web_leads/controllers/web_lead_api.py` |
| T6 | Publish stacked on PR #366 from fix/web-lead-n8n-production, which already holds commit 4fb22532 (nested stacking in scripts/pr_stack_parent.sh). Commit the plan JSON, plan markdown, section receipt, the T4 ADR edit, and any T3 change onto that branch. Before publishing, git fetch origin and run git merge-tree --write-tree HEAD against origin/feat/web-lead-material-grade, origin/fix/material-ledger-normalizer, and origin/Staging. If #366 moved, merge origin/feat/web-lead-material-grade into the branch. If #365 merged and #366 now targets Staging, the same command still applies. Resolve every conflict, keeping #366 code and only this campaign's lines, then rerun ruff check, ruff format, python -m pytest tests/test_make_pr_publication.py, and make test-module m=plasticos_web_leads if T3 ran. Publish only with PR_CHECK_SCOPE=full make pr base=feat/web-lead-material-grade so install-smoke runs on the fixture clone. | Cursor Build agent | `medium` | small | `[T1, T4]` | `scripts/pr_stack_parent.sh`, `tests/test_make_pr_publication.py`, `docs/campaigns/10-29-26/web-leads/web-lead-n8n-production.plan.json`, `docs/campaigns/10-29-26/web-leads/web-lead-n8n-production.plan.md`, `docs/campaigns/10-29-26/web-leads/web-lead-n8n-production.plan.section-receipt.json`, `docs/adr/ADR-020-web-lead-inbound-port.md` |

**Critical path:** T1 → T2 → T5

**Forbidden edges:** any edge not listed above; any todo writing outside `write_allow`.

### Milestones

| id | outcome | unlocks |
|----|---------|---------|
| M1 | Production bearer contract is proved or the June handler is shown to reject the live body. | T2 can retarget the workflow, or T3 is allowed to change code. |
| M2 | The active workflow posts the raw Cognito body to Production and the dropped staging host is off the gate path. | T5 can submit one real entry. |
| M3 | One Production web lead matches one Cognito entry and the workflow stays active. | T6 can publish the ADR correction with the observed path. |
| M4 | The campaign branch is published as a PR stacked on #366, full smoke passed, no unresolved conflict. | The campaign can stop. Merge and any Staging to Production promotion stay human decisions. A later cutover may remove n8n; this campaign does not. |

### Checkpoints

| id | after | evidence_required | no_go_action |
|----|-------|-------------------|--------------|
| C1 | T1 | Production module version, active config, 401 for a wrong bearer, and a match/mismatch result for ODOO_WEB_LEAD_API_KEY, the n8n literal, and the staging-named credential. No secret values. | Do not enable the Production node while it still sends the staging-named credential or an unproven literal. |
| C2 | T2 | GET workflow shows active true, webhook outgoing node is the enabled Production POST, and the staging host URL is not an ancestor of Normalize Odoo Delivery. The pre-change export exists outside the repository. | Do not submit a form entry. Revert the n8n connections to the previous GET export. |
| C3 | T5 | Cognito entry number, n8n execution id, HTTP outcome, Production web_lead_id, and field values for company, contact, material, and quantity. | If the gate fails or the lead is missing or empty, stop. Do not point the customer form at Odoo directly and do not disable n8n. |
| C4 | T6 | bash scripts/pr_stack_parent.sh prove feat/web-lead-material-grade exits 0. git merge-tree reports no conflict against origin/feat/web-lead-material-grade, origin/fix/material-ledger-normalizer, and origin/Staging at the pushed SHA. .cache/pr-check/scope.json records forced by PR_CHECK_SCOPE=full with smoke 1. make pr printed the PR URL with base feat/web-lead-material-grade. | If prove refuses, read its reason; do not retarget #365 or #366 and do not publish on Staging instead. If a conflict remains or smoke fails, do not publish. |

### Leverage

- **Ranked todos:** `T1`, `T2`, `T5`, `T6`, `T3`, `T4`
- **Shared causes:** One connected hop targets dropped staging build 36099032 while the Production hop is disabled, so staging checks and missing Production leads are the same fault.
- **Deletions / consolidations:** Remove the dropped staging host from the gate path instead of adding a second webhook or a direct Cognito-to-Odoo cutover.; Publish the ADR correction and any web-lead fix in one stacked PR instead of a parallel PR against Staging that would conflict with #366.

### Doc / root surface impact

| surface | action | todo_ids | reason |
|---------|--------|----------|--------|
| docs/adr/ADR-020-web-lead-inbound-port.md | `update` | `T4` | The live form still enters through n8n. The ADR currently says that path is gone and that the workflow is retired next. |
| AGENTS.md | `n_a` | — | No command, module count, or CI contract changes in the default path. |
| INVARIANTS.md | `n_a` | — | No invariant is added or waived. Partner deferral and the write guard stay. |

## Property evidence matrix

`schema_ref:` `canonical.schema.validation_evidence.v1`
`instance_binding:` `validation_evidence_refs` / `property_evidence_matrix_ref`
Exit-0 alone is insufficient when property needs structural/runtime proof (PLAN-SCHEMA-008).

| evidence_id | claim_id / SP | evidence_kind | method | command | expected_positive | status |
|-------------|---------------|---------------|--------|---------|-------------------|--------|
| E-V1 | SP-01 | `quality_gate_evidence` | command | `GET /api/v1/workflows/5NjFkIFOBDWsMLyk and trace Webhook to Normalize Odoo Delivery` | Workflow active. Enabled Production POST is the webhook successor. Host staging-36099032 is not on that path. Observed: 2026-11-04T21:11Z GET: active true, versionId == activeVersionId 803a3552. Webhook -> POST Raw Cognito to Production Odoo (enabled, httpBearerAuth credential Odoo Production Web Lead Bearer yqUODZ60YnNh1QNT, no literal header) -> Normalize Odoo Delivery. Staging node disabled, no outgoing edge, not an ancestor of Normalize Odoo Delivery or Final Production Gate. | `passed` |
| E-V2 | SP-02 | `quality_gate_evidence` | command | `Submit one synthetic Cognito entry and read the Production plasticos.web.lead plus the n8n execution` | One lead, matching company, contact, material, quantity, and CG entry id under the 19.0.2.6.0 mapping. n8n odooStatus success and web_lead_id present. No second lead. Observed: Cognito entry 9233 (Id 4-9233, form 4) -> n8n execution 71414 success in 39 s -> Production web_lead_id 88, lead_id CG-4-9233, decision cold, state skipped, partner_id null, intake_id null. Final Production Gate status success, odooStatus success, odooWebLeadId 88. Airtable recWrmTRFcwwIgH8M. Field values are inferred from origin/Production create_from_cognito and the present body keys; Production SSH port 22 was unreachable, so no direct row read. | `passed` |
| E-V3 | SP-03 | `quality_gate_evidence` | command | `GET workflow active flag and confirm the Cognito form submit URL host is still ibeylin.app.n8n.cloud` | active true and the customer form was not repointed at Odoo. Observed: Workflow active true after the change; execution 71414 ran in webhook mode from the public form, so the form still posts to n8n. No middleware added. | `passed` |
| E-V4 | regression gate (no SP) | `quality_gate_evidence` | command | `If T3 edits plasticos_web_leads, run pre-commit against .pre-commit-config.yaml and make test-module m=plasticos_web_leads. If T3 is skipped, do not run a repo-wide hook sweep.` | No web-lead diff, or the changed module passes .pre-commit-config.yaml and its module tests on the fixture clone. Observed: T3 skipped: U2 resolved yes. No plasticos_web_leads diff. | `not_run` (not_applicable) |
| E-V5 | SP-04 | `quality_gate_evidence` | command | `git fetch origin; bash scripts/pr_stack_parent.sh prove feat/web-lead-material-grade; git merge-tree --write-tree HEAD origin/feat/web-lead-material-grade; git merge-tree --write-tree HEAD origin/Staging; PR_CHECK_SCOPE=full make pr base=feat/web-lead-material-grade` | prove exits 0. Both merge-tree checks exit 0. scope.json reason is forced by PR_CHECK_SCOPE=full with smoke 1. install-smoke --resolve and --recheck pass. The PR base is feat/web-lead-material-grade. | `not_run` |

## Stress and disconfirm

### Disconfirming cases

- Does enabling the existing Production node without changing its literal bearer authenticate as Production, or as the staging key named on its credential?
- Does Production 19.0.2.6.0 persist the live form fields, or only return status ok around an empty lead?
- If the staging node stays connected and continues on error, can the final gate still fail after Production succeeds?
- Does prove still reach Staging if #365 merges and #366 is retargeted, or if a branch on the chain gains a second open PR?
- Does a T3 fix on Staging change what Production stores before a Staging promotion?

### Assumption failure conditions

- The customer form posts somewhere other than n8n webhook path 631708ea-e339-4667-89b1-5b78fb388fca.
- Production no longer has POST /api/v1/cognito-webhook.
- A dropped Odoo.sh staging build can accept the current webhook.
- PR #366 changes the cognito-webhook route or its Bearer check.

### Blast radius notes

- A wrong bearer or a still-connected dead host fails every new quote in the active workflow. A bad Production write creates a web lead and may create a HOT intake. It must not create a partner. Airtable and Drive steps downstream of a successful Odoo response stay in the workflow. The stacked PR adds docs and at most one web-lead change on top of #366; it cannot reach Production on its own.

### Rollback constraints

- Restore the workflow from the pre-change GET export ~/.cache/plasticos-web-lead/n8n-5NjFkIFOBDWsMLyk-pre-T2-20261104T160934.json (versionId 3e6bb9ef): disable the Production node, reconnect the webhook to the previous staging node, and do not change the Cognito form. If T3 shipped, revert that commit on the campaign branch; do not roll Production back to a build older than 3318fa64. Close the stacked PR if #366 is abandoned. Revert 4fb22532 to return prove to one-level stacking.

### Risks

| risk | mitigation |
|------|------------|
| The literal bearer on the disabled Production node is the staging key, so enabling it unchanged returns 401 and the gate still fails. | T1 compares it to the Production config. T2 replaces it with a Production credential before the node is enabled. |
| Production triage on 19.0.2.6.0 creates a lead but marks state error, and the n8n success check ignores state. | T5 fails the campaign unless the lead fields are populated and the execution gate is success. Do not treat HTTP 200 alone as success. |
| A broad Staging promotion is used to fix a wiring fault and ships #365, #366, and other unrelated modules to Production. | T3 is blocked unless the June handler fails the live body. The default path changes n8n only. Promotion stays an operator decision. |
| #366 moves after the campaign branch is cut and a T3 hunk conflicts in web_lead.py _merge_ai_data or _create_intake_from_merged. | T6 merges the live #366 head and resolves conflicts before make pr, then reruns the module tests. |
| A docs-only scope skips install-smoke. | T6 sets PR_CHECK_SCOPE=full, which forces smoke 1. No smoke bypass variable is set. |
| Nested stacking accepts a chain whose lower parent is stale or not reviewed. | prove requires exactly one open PR per branch in this repository, refuses Production, main, lowercase staging, loops, and depth over five, and still requires HEAD to contain the named parent. Merge order stays human: #365, then #366, then this PR. |

## Out of scope

- Deleting, disabling, or replacing the n8n workflow.
- Repointing the customer Cognito form off n8n.
- Promoting all of Staging to Production. That promotion also ships PR #365 and PR #366 and is a separate operator decision.
- Editing plasticos_material_profile normalizer or grade code, plasticos_crm_sync, plasticos_transaction, or plasticos_intake_normalizer, which PR #365 and PR #366 own.
- PR #363 (chore/repo-index), which is unrelated.
- Partner auto-creation, write/unlink guard edits, a new controller, or pipeline_v2.
- Using the dead staging build 36099032 or the literal bearer already stored on the disabled node.
- make pr-nosmoke, PR_CHECK_SKIP_SMOKE, PR_SMOKE_BYPASS, or PR_CHECK_FORCE_SMOKE (make pr refuses the last one).
- Architecture redesign (unless plan_class + redesign_allowed)
- Force-push, hard-reset, admin-merge, secret exfil
- Weakening scanners / gates to obtain PASS
- Follow-on schema/platform evolution

## Follow-on milestone *(optional — keep separate; PLAN-SCHEMA-014)*

Not activated — PLAN_DOCUMENT declares no follow-on milestone; separate_plan_required `true` for any follow-on.

## Convergence

`schema_ref:` `canonical.schema.convergence_contract.v1`
`instance_binding:` `convergence_contract_ref` → `conv.plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1`
Convergence requires all blocking evidence + gates (PLAN-SCHEMA-015).

| Field | Value |
|-------|-------|
| convergence_id | `conv.plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1` |
| source_ref | `plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1` |
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

- **required_evidence_refs:** E-V1, E-V2, E-V3, E-V4, E-V5
- **observed_evidence_refs:** E-V1, E-V2, E-V3
- **missing_evidence:** E-V4, E-V5

### Blockers / unknowns

| kind | id | note | resolution |
|------|----|------|------------|
| `unknown` | U1 | Does the literal bearer on the disabled Production node equal the Production web-lead API key, or only the staging-named credential? — If it mismatches, T2 must install the Production credential before enablement. If it matches, still move auth off the embedded literal. Resolved by T1: the literal equals the Production key. T2 still moved auth to credential Odoo Production Web Lead Bearer. | `accept_bounded` |
| `unknown` | U2 | Does a live Cognito body accepted by Production 19.0.2.6.0 persist company, contact, material, and quantity? — If yes, T3 is skipped. If no, T3 is the only Odoo code change in this campaign, and Production needs an operator promotion to receive it. Resolved by T5: Production stored lead 88 from entry 9233 with every mapped key present; T3 skipped. | `accept_bounded` |
| `unknown` | U3 | Can the N8N_API_KEY create or attach an httpBearerAuth credential through the n8n public API? — If yes, T2 runs through the API. If no, the operator attaches the Production credential in the n8n editor and T2 only rewires connections. Resolved by T2: POST /credentials created yqUODZ60YnNh1QNT; PUT /credentials/{id}/transfer moved it to project Important Workflows (VcaOv7RdSnVF7pYR) before the workflow PUT was accepted. GET /credentials is 403 for this key. | `accept_bounded` |
| `open_blocker` | stop_reason | T1, T2, T4, and T5 are done with observed evidence; T3 is skipped. Only V5 remains: T6 publishes stacked on #366 with PR_CHECK_SCOPE=full make pr. | planning convergence `partial` |

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
schema_version: "1"
metadata:
  plan_id: "plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1"
  name: "Land Cognito leads in Production through the active n8n workflow"
  overview: "Keep the active n8n workflow Web Lead Triage - PRODUCTION - Attachments v5.5.2 (id 5NjFkIFOBDWsMLyk) as the Cognito ingress and make one real submission create exactly one Production plasticos.web.lead. The workflow was last saved 2026-08-29. Its webhook connects only to POST Raw Cognito to Staging Odoo at https://cryptoxdog-ib-odoo-19-staging-36099032.dev.odoo.com/api/v1/cognito-webhook, a dropped host that resolves to 0.0.0.0. POST Raw Cognito to Production Odoo is disabled, absent from connections, uses authentication none, carries a literal Authorization bearer, and attaches the credential named Odoo Staging Web Lead Bearer. Normalize Odoo Delivery and Final Production Gate judge only that staging response, so a dead staging hop fails the run before Production is called. Production git 3318fa646a9f33aed55b9ea8f8596316e30684da (2026-06-04, plasticos_web_leads 19.0.2.6.0) already accepts Bearer POST /api/v1/cognito-webhook through receive_cognito_webhook and create_from_cognito (origin/Production plasticos_web_leads/models/web_lead.py:372) and maps the live form fields. Staging 4a6af0b2d5bbf8f16e4fa67baafe9d71e3b4f384 (19.0.2.8.6) is not required for that contract. Open PR #365 (fix/material-ledger-normalizer into Staging) rewrites plasticos_material_profile/models/material_normalizer.py onto named _Spec slots. Open PR #366 (feat/web-lead-material-grade, head 46aece9f, base fix/material-ledger-normalizer) bumps plasticos_web_leads to 19.0.2.8.7 and splits one material code into form or material grade (material_identity.split_material_code against plasticos_material_profile.grade_codes.GRADE_CODES). Neither PR is on Production. This campaign publishes stacked on #366 with the full smoke gate from branch fix/web-lead-n8n-production, cut from #366 head 46aece9f. Its first commit 4fb22532 lets scripts/pr_stack_parent.sh prove follow a parent PR chain (#366 to #365 to Staging), so publication does not wait for #365 to merge. MEMORY_PREFETCH snapshot_digest f9e69f08f9a92e10ba5df37f8f63f47d30e1253bc3ddb67f9174c8c12c3bc5d2 conflicts 0. The n8n MCP server exposes node documentation only, so the live workflow was read with a GET and was not uploaded."
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
  commit_sha: "4fb22532fa8aca0d76372a2d1bd975fa9000738b"
  dirty: "true"
  overlap_policy: "stop_if_dirty_overlaps_may_modify"
  verification_rule: "reverify_at_execution_start"
  on_drift: "stop_and_replan"
objective:
  mission: "Keep the active n8n workflow Web Lead Triage - PRODUCTION - Attachments v5.5.2 (id 5NjFkIFOBDWsMLyk) as the Cognito ingress and make one real submission create exactly one Production plasticos.web.lead. The workflow was last saved 2026-08-29. Its webhook connects only to POST Raw Cognito to Staging Odoo at https://cryptoxdog-ib-odoo-19-staging-36099032.dev.odoo.com/api/v1/cognito-webhook, a dropped host that resolves to 0.0.0.0. POST Raw Cognito to Production Odoo is disabled, absent from connections, uses authentication none, carries a literal Authorization bearer, and attaches the credential named Odoo Staging Web Lead Bearer. Normalize Odoo Delivery and Final Production Gate judge only that staging response, so a dead staging hop fails the run before Production is called. Production git 3318fa646a9f33aed55b9ea8f8596316e30684da (2026-06-04, plasticos_web_leads 19.0.2.6.0) already accepts Bearer POST /api/v1/cognito-webhook through receive_cognito_webhook and create_from_cognito (origin/Production plasticos_web_leads/models/web_lead.py:372) and maps the live form fields. Staging 4a6af0b2d5bbf8f16e4fa67baafe9d71e3b4f384 (19.0.2.8.6) is not required for that contract. Open PR #365 (fix/material-ledger-normalizer into Staging) rewrites plasticos_material_profile/models/material_normalizer.py onto named _Spec slots. Open PR #366 (feat/web-lead-material-grade, head 46aece9f, base fix/material-ledger-normalizer) bumps plasticos_web_leads to 19.0.2.8.7 and splits one material code into form or material grade (material_identity.split_material_code against plasticos_material_profile.grade_codes.GRADE_CODES). Neither PR is on Production. This campaign publishes stacked on #366 with the full smoke gate from branch fix/web-lead-n8n-production, cut from #366 head 46aece9f. Its first commit 4fb22532 lets scripts/pr_stack_parent.sh prove follow a parent PR chain (#366 to #365 to Staging), so publication does not wait for #365 to merge. MEMORY_PREFETCH snapshot_digest f9e69f08f9a92e10ba5df37f8f63f47d30e1253bc3ddb67f9174c8c12c3bc5d2 conflicts 0. The n8n MCP server exposes node documentation only, so the live workflow was read with a GET and was not uploaded."
  success_properties:
    - id: "SP-01"
      property: "V1: the active workflow webhook connects to an enabled Production POST, and the dropped staging host is not an input to Final Production Gate."
      evidence_type: "quality_gate"
      proof: ["V1"]
      blocking: true
    - id: "SP-02"
      property: "V2: one Cognito Submit on form ScrapManagementInc1/4 creates exactly one Production plasticos.web.lead whose company, contact, material, and CG entry identity match the entry under the Production 19.0.2.6.0 mapping, with n8n odooStatus success and web_lead_id set."
      evidence_type: "quality_gate"
      proof: ["V2"]
      blocking: true
    - id: "SP-03"
      property: "V3: workflow 5NjFkIFOBDWsMLyk stays active, the customer form still posts to n8n, and no new middleware is added."
      evidence_type: "quality_gate"
      proof: ["V3"]
      blocking: true
    - id: "SP-04"
      property: "V5: fix/web-lead-n8n-production is published by PR_CHECK_SCOPE=full make pr base=feat/web-lead-material-grade with install-smoke run, after every conflict against origin/feat/web-lead-material-grade and origin/Staging is resolved."
      evidence_type: "quality_gate"
      proof: ["V5"]
      blocking: true
capability_preflight_ref: "preflight.plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1"
execution_envelope:
  filesystem:
    write_allow: ["n8n workflow 5NjFkIFOBDWsMLyk connections, disabled flag, and Production node auth", "docs/adr/ADR-020-web-lead-inbound-port.md", "docs/campaigns/10-29-26/web-leads/web-lead-n8n-production.plan.json, .plan.md, and .plan.section-receipt.json", "scripts/pr_stack_parent.sh and tests/test_make_pr_publication.py (committed as 4fb22532)", "plasticos_web_leads/models/web_lead.py and __manifest__.py only after T1 fails the live payload"]
    write_deny: ["Cognito form ScrapManagementInc1/4 submit destination", "n8n workflow active flag set to false", "plasticos_web_leads write guard, unlink guard, and partner-deferral path", "plasticos_web_leads material_identity.split_material_code and the PR #366 form/grade split", "plasticos_material_profile, plasticos_crm_sync, plasticos_transaction, plasticos_intake_normalizer", "PR #365 and PR #366 branches, bases, or merge state", "pipeline_v2.py", "unrelated Staging modules on the Production promotion"]
  commands:
    allow: ["GET /api/v1/workflows/5NjFkIFOBDWsMLyk", "POST /api/v1/cognito-webhook with a wrong bearer expects 401", "one synthetic Cognito submit correlated to one Production web lead", "GH_REPO=cryptoxdog/IB-Odoo_19 bash scripts/pr_stack_parent.sh prove feat/web-lead-material-grade", "git merge-tree --write-tree HEAD origin/feat/web-lead-material-grade", "PR_CHECK_SCOPE=full make pr base=feat/web-lead-material-grade", "GET /api/v1/workflows/5NjFkIFOBDWsMLyk and trace Webhook to Normalize Odoo Delivery", "Submit one synthetic Cognito entry and read the Production plasticos.web.lead plus the n8n execution", "GET workflow active flag and confirm the Cognito form submit URL host is still ibeylin.app.n8n.cloud", "If T3 edits plasticos_web_leads, run pre-commit against .pre-commit-config.yaml and make test-module m=plasticos_web_leads. If T3 is skipped, do not run a repo-wide hook sweep.", "git fetch origin; bash scripts/pr_stack_parent.sh prove feat/web-lead-material-grade; git merge-tree --write-tree HEAD origin/feat/web-lead-material-grade; git merge-tree --write-tree HEAD origin/Staging; PR_CHECK_SCOPE=full make pr base=feat/web-lead-material-grade"]
  network:
    mode: "bounded_external_write"
  secrets:
    access: "read_only_named"
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
    side_effects: "filesystem_mutation"
    idempotency: "safe_with_dedupe"
    retry: "retry_once"
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
rollback_contract_ref: "rollback.plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1"
dependency_topology_ref: "dag.plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1"
validation_evidence_refs: ["E-V1", "E-V2", "E-V3", "E-V4", "E-V5"]
stress_and_disconfirm:
  disconfirming_cases: ["Does enabling the existing Production node without changing its literal bearer authenticate as Production, or as the staging key named on its credential?", "Does Production 19.0.2.6.0 persist the live form fields, or only return status ok around an empty lead?", "If the staging node stays connected and continues on error, can the final gate still fail after Production succeeds?", "Does prove still reach Staging if #365 merges and #366 is retargeted, or if a branch on the chain gains a second open PR?", "Does a T3 fix on Staging change what Production stores before a Staging promotion?"]
  assumption_failure_conditions: ["The customer form posts somewhere other than n8n webhook path 631708ea-e339-4667-89b1-5b78fb388fca.", "Production no longer has POST /api/v1/cognito-webhook.", "A dropped Odoo.sh staging build can accept the current webhook.", "PR #366 changes the cognito-webhook route or its Bearer check."]
out_of_scope: ["Deleting, disabling, or replacing the n8n workflow.", "Repointing the customer Cognito form off n8n.", "Promoting all of Staging to Production. That promotion also ships PR #365 and PR #366 and is a separate operator decision.", "Editing plasticos_material_profile normalizer or grade code, plasticos_crm_sync, plasticos_transaction, or plasticos_intake_normalizer, which PR #365 and PR #366 own.", "PR #363 (chore/repo-index), which is unrelated.", "Partner auto-creation, write/unlink guard edits, a new controller, or pipeline_v2.", "Using the dead staging build 36099032 or the literal bearer already stored on the disabled node.", "make pr-nosmoke, PR_CHECK_SKIP_SMOKE, PR_SMOKE_BYPASS, or PR_CHECK_FORCE_SMOKE (make pr refuses the last one)."]
convergence_contract_ref: "conv.plan.simple.land_cognito_leads_in_production_through_the_active_n8n_workflow.v1"
execute_via:
  pipeline: cursor-build
  mention_program: "Cursor Build"
  command_ref: PR_STACK=auto make pr
  authority_order:
    - plan_document
    - cursor_build
todos:
  - id: "T1"
    content: "On Production only, prove the installed web-lead module, an active config, and that a bearer matching that config is accepted by POST /api/v1/cognito-webhook. Compare the Infisical ODOO_WEB_LEAD_API_KEY, the disabled n8n literal, and the credential named Odoo Staging Web Lead Bearer by equality to the Production key. Do not print secrets. Record HTTP status and whether a synthetic invalid token returns 401."
    status: "pending"
  - id: "T2"
    content: "Save a GET export of the workflow outside the repository first, because it contains the literal bearer. In the active workflow, enable POST Raw Cognito to Production Odoo, point the webhook edge at it, authenticate with a Production bearer credential rather than the embedded literal or the staging-named credential, and disconnect the dropped staging host from Normalize Odoo Delivery. Leave the workflow active and keep posting the raw Cognito body. If the n8n API key cannot create or attach credentials, stop and have the operator attach the credential in the n8n editor."
    status: "pending"
  - id: "T3"
    content: "Change plasticos_web_leads only if T1 shows Production rejects the live Cognito body or stores empty company, contact, material, or quantity for values the form sent. Read .cursor/rules/50-plasticos-web-lead-guard.mdc first. Edit fix/web-lead-n8n-production, which contains PR #366: create_from_cognito and _merge_ai_data at 19.0.2.8.7, keeping split_material_code and the form/grade split. Bump to 19.0.2.8.8. Run make test-module m=plasticos_web_leads before and after. This fix reaches Production only through a whole Staging promotion, which is an operator decision outside this campaign."
    status: "pending"
  - id: "T4"
    content: "Correct ADR-020 so it states the live quote form still posts to n8n workflow 5NjFkIFOBDWsMLyk, which then posts raw JSON to Production /api/v1/cognito-webhook. Replace the line that says n8n is no longer on the path, and mark the step that retires the workflow and the N8N_* Infisical names as not done in this campaign."
    status: "pending"
  - id: "T5"
    content: "Submit one synthetic Cognito entry through the existing form, correlate Entry.Number to the n8n execution and to exactly one Production web lead, and confirm the final gate reports odooStatus success with web_lead_id. Check fields against the Production 19.0.2.6.0 mapping, not the PR #366 form/grade split. Do not resubmit a customer entry."
    status: "pending"
  - id: "T6"
    content: "Publish stacked on PR #366 from fix/web-lead-n8n-production, which already holds commit 4fb22532 (nested stacking in scripts/pr_stack_parent.sh). Commit the plan JSON, plan markdown, section receipt, the T4 ADR edit, and any T3 change onto that branch. Before publishing, git fetch origin and run git merge-tree --write-tree HEAD against origin/feat/web-lead-material-grade, origin/fix/material-ledger-normalizer, and origin/Staging. If #366 moved, merge origin/feat/web-lead-material-grade into the branch. If #365 merged and #366 now targets Staging, the same command still applies. Resolve every conflict, keeping #366 code and only this campaign's lines, then rerun ruff check, ruff format, python -m pytest tests/test_make_pr_publication.py, and make test-module m=plasticos_web_leads if T3 ran. Publish only with PR_CHECK_SCOPE=full make pr base=feat/web-lead-material-grade so install-smoke runs on the fixture clone."
    status: "pending"
```
