---
name: plasticos-repo-review-kernel
description: Repo-wide review kernel for inventory, installability, registry safety, architecture drift, and next-action readiness.
skill_schema: 1
layer: control_plane
role: skill_entrypoint
tags: [plasticos, repo, review, installability, architecture, audit]
owner: igor_beylin
status: active
disable-model-invocation: false
version: 1.1.0
updated: 2026-06-06
---

# Repo Review Kernel

## Purpose

Assess IB-Odoo_19 holistically before broad changes, go-live readiness, pack reviews, or integration planning. Produce an evidence-backed verdict — never claim safety without visibility.

## Core Contract

| Output field | Requirement |
|--------------|-------------|
| `repo_visibility` | `full` \| `partial` \| `limited` — must match actual files inspected |
| `verdict` | `safe_to_continue` \| `conditional` \| `reject` |
| Evidence | Every blocker/critical/high cites file path or command output |
| CI | At minimum review or run `make audit-quick`; `make pr-check` for merge readiness |

## Authority Order

1. Explicit user request and review scope (full repo vs module subset).
2. Verified repo ground truth — git status, manifests, models, tests on disk.
3. `ARCHITECTURE.md` — layer boundaries and module inventory.
4. `INVARIANTS.md` and `AGENTS.md` — CI gates, known false positives.
5. This skill's references.
6. `Unknown` — label gaps; never infer installability without evidence.

## Compact Workflow

1. Establish git visibility (branch, status, diff scope).
2. Run review sequence per [review-sequence.md](references/review-sequence.md).
3. Classify findings: blocker, critical, high, medium, known false positive.
4. Emit `repo_review_report` YAML.

## Resource Map

- [references/review-sequence.md](references/review-sequence.md) — 7-step inventory, registry, architecture, CI sequence.

## Validation

Review complete when:

- All 7 sequence steps addressed or marked `skipped` with reason.
- `modules_scanned` lists actual `plasticos_*` modules inspected.
- `ci_gates_reviewed` lists commands run or log outputs reviewed.
- Verdict matches highest severity finding.

## Failure Handling

- Limited visibility (partial clone, missing modules) → `repo_visibility: limited`; verdict max `conditional`.
- Cannot run CI locally → record `not_run`; do not claim CI pass.
- Blocker found → verdict `reject` or `conditional` with explicit `required_actions`.
- Never claim `safe_to_continue` without current branch status and at least audit-quick evidence.
