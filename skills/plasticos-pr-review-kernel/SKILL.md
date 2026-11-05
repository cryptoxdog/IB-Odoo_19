---
name: plasticos-pr-review-kernel
description: PlasticOS PR review kernel — base branch topology, pipeline_v2 guard, migration assessment, zero-stub validation. Invoke with REVIEW PR #<number> or PR_REVIEW_MODE.
skill_schema: 1
layer: control_plane
role: skill_entrypoint
tags: [plasticos, pr, review, merge, migration, security]
owner: igor_beylin
status: active
disable-model-invocation: false
version: 1.1.0
updated: 2026-06-06
---

# PlasticOS PR Review Kernel

## Purpose

Review or author pull requests in IB-Odoo_19 with production-safe merge criteria, migration/test requirements, and risk classification before merge into Staging or Production.

Invoke with `REVIEW PR #<number>` or `PR_REVIEW_MODE`.

## Core Contract

| Check | Requirement |
|-------|-------------|
| Base branch | Feature PRs → `Staging`; production promotion → `Production` only after Staging validation |
| Hard rejects | pipeline_v2 activation, destructive migration, secrets, force-push to protected branches |
| Local gate | `make pr-check` must pass or PR flagged blocked |
| Verdict | `approve` \| `request_changes` \| `block` with evidence |

## Authority Order

1. Explicit review request and PR metadata (number, base, head).
2. `INVARIANTS.md` — pipeline_v2, migrations, security invariants.
3. `AGENTS.md` — CI Compliance Checklist, branch model, test layout.
4. `.cursor/rules/70-github-api-commit.mdc`, `50-plasticos-web-lead-guard.mdc` (web_lead PRs).
5. This skill's references.
6. `Unknown` — do not approve without reviewed diff or CI evidence.

## Compact Workflow

1. Collect PR metadata; verify base branch.
2. Run or review `make pr-check` output.
3. Apply [hard-reject-conditions.md](references/hard-reject-conditions.md) — stop on any match.
4. Execute [review-protocol.md](references/review-protocol.md) steps 1–10.
5. Emit `pr_review_result` YAML per output contract in review-protocol.

## Resource Map

- [references/hard-reject-conditions.md](references/hard-reject-conditions.md) — immediate block conditions.
- [references/review-protocol.md](references/review-protocol.md) — file analysis, migration, tests, security, output contract.

## Validation

Review is complete only when:

- Base branch verified against branch topology.
- pipeline_v2 guard status recorded.
- Migration command provided if `migration_required: true`.
- Verdict and `required_actions` populated with file-level evidence.

## Failure Handling

- `make pr-check` fails → verdict `block`; list failing gate.
- Destructive migration without approval → `block`; require backup plan.
- web_lead HOT/COLD change without regression test → `request_changes`.
- Missing PR diff access → STOP; use `gh pr diff` or ask user.
