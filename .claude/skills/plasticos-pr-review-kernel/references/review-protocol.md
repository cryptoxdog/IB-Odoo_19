<!-- L9_META
skill_schema: 1
parent: plasticos-pr-review-kernel
layer: reference
role: review_protocol
tags: [plasticos, pr, review, migration, test, output]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
/L9_META -->

# PR Review Protocol

## Pre-Review

```bash
make pr-check
```

Must pass or PR is blocked.

## Step 1 — PR Metadata

```yaml
pr_number: ""
title: ""
author: ""
base_branch: ""  # Staging for features; Production for promotions/hotfixes
head_branch: ""
files_changed: []
```

## Step 2 — Changed File Analysis

Per file:

```yaml
file: ""
module: ""
layer: ""
risk_class: blocker | critical | high | medium | low
migration_required: true | false
db_change: none | additive | destructive
test_coverage: yes | partial | none
```

## Step 3 — Module Boundary

Cross-module imports only if listed in manifest `depends`. No new circular deps (pre-existing `commission ↔ transaction` is non-fatal).

## Step 4 — DB Migration Assessment

Additive (safe):

```bash
make update m=<module>
```

Destructive migrations require explicit approval and backup. Never merge destructive without backup.

## Step 5 — Test Coverage

- Root `tests/` is primary layout for Production.
- Tests must use `TransactionCase` or `SavepointCase`.
- No external services without mock.
- web_lead PRs: HOT/COLD, weight parsing, write guard changes need regression tests.
- State guard on `intake_created` must not weaken (`ci/check_state_guard_bypass.py`).

## Step 6 — Zero-Stub Validation

No TODO stubs as implementation, placeholder `pass` in production models, or dummy business returns.

## Step 7 — Security Review

- `sudo()` with inline justification comment.
- New models need `ir.model.access.csv`.
- Record rules reviewed for multi-company/role sensitivity.

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

## Definition of Done

All protocol steps completed; verdict provided; deployment note when migration required.
