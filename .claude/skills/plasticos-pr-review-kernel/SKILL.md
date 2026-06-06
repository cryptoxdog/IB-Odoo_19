---
name: plasticos-pr-review-kernel
description: PlasticOS PR review kernel — base branch topology, pipeline_v2 guard, migration assessment, zero-stub validation. Invoke with REVIEW PR #<number> or PR_REVIEW_MODE.
---

# PlasticOS Odoo PR Review Kernel
# Source: docs/plasticos_kernel_pack_v1_2026_05_26/revised_odoo_pr_review_kernel.md

## Purpose

Use this kernel when reviewing or authoring pull requests in IB-Odoo_19. It enforces the production-safe merge criteria, captures deploy/test requirements, and classifies risks before any merge into Staging or Production.

## Branch Topology (Confirmed)

```
Production  ←  Staging  ←  feature/fix branches
```

- PRs into `Staging` are pre-production.
- PRs into `Production` are production-promotions.
- **Never merge directly into Production without Staging validation.**

## Current Open PRs (as of 2026-05-26)

| PR | Base | Status | Risk |
|---|---|---|---|
| #88 — feat: Odoo-specific Cursor rules | `Production` | Open | Low — .mdc + .gitignore only |
| #85 — wire TODO #1-4 intake/match/offer | `Staging` | Open | High — DB migration, new FK, multi-module |
| #83 — web_lead 10X rewrite | `Staging` | Open | High — HOT/COLD classification critical path |

## Pre-Review Checklist

Before reviewing any PR:

```bash
make pr-check
# expands to: make audit-quick semgrep
```

This must pass. If it fails, flag the PR as blocked.

## Hard Reject Conditions

Reject the PR immediately if:

- `plasticos_inference_engine/pipeline_v2.py` is imported or activated by any code in the PR
- `plasticos_dev_tools` is enabled in a non-dev config
- An irreversible migration is present without explicit approval
- A column or table is dropped without explicit user approval
- A force push to `Production` or `Staging` without approval
- Credentials, tokens, or secrets appear in any changed file

## Review Protocol

### 1. PR Metadata

```yaml
pr_number: ""
title: ""
author: ""
base_branch: ""  # must be "Staging" for feature PRs, "Production" for Cursor rules / hotfixes
head_branch: ""
files_changed: []
```

### 2. Base Branch Verification

Confirm whether base is `Staging` or `Production`:

- `Staging` — validate for logic, tests, migration safety, rollback
- `Production` — additionally validate it is not a feature PR (should be merge from Staging only, or low-risk config change)

### 3. Changed File Analysis

For each changed file, determine:

```yaml
file: ""
module: ""
layer: ""
risk_class: blocker | critical | high | medium | low
migration_required: true | false
db_change: none | additive | destructive
test_coverage: yes | partial | none
```

### 4. Module Boundary

Verify the PR does not violate module layer boundaries.

Cross-module imports are acceptable only if:
- listed in manifest `depends`
- no circular dependency created (pre-existing: `commission ↔ transaction`, non-fatal)

### 5. pipeline_v2.py Guard

```yaml
pipeline_v2_check:
  any_import_of_pipeline_v2: false  # must be false
  ci_check_file: ci/check_pipeline_v2_guard.py
  status: must_pass
```

### 6. DB Migration Assessment

If PR includes migration:

```bash
# Additive (safe):
make update m=<module>

# Required for PR #85 specifically:
make update m=plasticos_claims,plasticos_offer,plasticos_intake,plasticos_buyer_match_engine
```

Destructive migrations require explicit user approval. Never merge destructive migrations without backup.

### 7. Test Coverage Assessment

- Root `tests/` flat layout is the primary test location for Production
- PR #85 introduces `tests/plasticos_*/` subdirectory layout — this affects test discovery if merged
- Confirm new tests are in the correct location for the target branch

Tests must:
- use `TransactionCase` or `SavepointCase` from Odoo test base
- not depend on external services without mock
- pass `make test-module m=<module>` without error

### 8. Zero-Stub Validation

Confirm the PR contains no:
- TODO stubs passed as implementation
- placeholder `pass` methods in production model code
- dummy return values in business logic

Exception: `pipeline_v2.py` deferred guard — intentional, not a stub.

### 9. Regression Check

For web_lead related PRs: any change to HOT/COLD classification, weight parsing, or write guard logic must include a matching regression test.

State guard (`write()` protection on `intake_created`) must not be weakened. Validated by `ci/check_state_guard_bypass.py`.

### 10. Security Review

- `sudo()` uses must be justified with inline comment
- new models must have `ir.model.access.csv` entries
- record rules must be reviewed

## Output Contract

```yaml
pr_review_result:
  pr_number: ""
  base_branch: ""
  verdict: approve | request_changes | block
  migration_required: true | false
  migration_command: ""
  test_coverage: yes | partial | none
  blockers: []
  critical_risks: []
  high_risks: []
  required_actions: []
  deployment_note: ""
  pipeline_v2_guard: pass | fail
  pr_check_status: pass | fail | not_run
```

## Deploy Instruction Template

```yaml
deploy:
  command: "make update m=<module>"
  expands_to: "docker compose run --rm odoo -u <module>"
  migration: "additive only — backwards compatible"
  rollback: "make down → restore DB backup → make up"
  requires_restart: true | false
  update_flag_required: "--update <module>"
```

## Objective Definition of Done

```yaml
definition_of_done:
  objective: "review PR for safe merge into Staging or Production"
  pr_metadata_collected: true
  base_branch_verified: true
  pipeline_v2_guard_checked: true
  module_boundary_checked: true
  db_migration_assessed: true
  test_coverage_assessed: true
  zero_stub_validated: true
  regression_check_completed: true
  security_reviewed: true
  pr_check_run_or_output_reviewed: true
  verdict_provided: true
  deployment_note_provided: true
```
