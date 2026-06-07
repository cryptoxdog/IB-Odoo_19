---
name: plasticos-final-touches
description: PlasticOS final-touches kernel — 10 pre-go-live gates, scoped to cleanup/hardening only, no new features. Invoke with FINAL_TOUCHES_MODE.
skill_schema: 1
layer: control_plane
role: skill_entrypoint
tags: [plasticos, odoo, go-live, audit, gates, hardening]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
---

# PlasticOS Final Touches Kernel

## Purpose

Run the 10-gate pre-go-live hardening sequence on IB-Odoo_19 during final optimization. Surgical cleanup and production guard verification only — no new features, no speculative changes.

Invoke with `FINAL_TOUCHES_MODE`.

## Core Contract

| Constraint | Rule |
|------------|------|
| Scope | Debug artifact removal, ACL/XML/cron safety, ORM/wiring guards |
| Out of scope | New models/fields, business logic, HOT/COLD classification, pipeline_v2 activation |
| Gate order | Gates 1–10 in sequence; `make pr-check` is mandatory final gate |
| Verdict | `ready_for_production` only when all gates pass and no scope violations |

## Authority Order

1. Explicit user request and `FINAL_TOUCHES_MODE` invocation.
2. `INVARIANTS.md` — pipeline_v2 guard, dev-tools fence, state guards.
3. `AGENTS.md` — CI Compliance Checklist, pre-commit hooks, audit baselines.
4. `.cursor/rules/00-plasticos-master-context.mdc` — deferred items, known pre-existing issues.
5. This skill's references.
6. `Unknown` — stop rather than invent gate commands or skip evidence.

## Compact Workflow

1. Take DB backup snapshot before any changes.
2. Run gates 1–10 per [gate-sequence.md](references/gate-sequence.md).
3. Fix failures before proceeding to the next gate.
4. Run `make pr-check` as final gate.
5. Emit output per [output-contract.md](references/output-contract.md).

## Resource Map

- [references/gate-sequence.md](references/gate-sequence.md) — gates 1–10 commands, expected outcomes, rollback path.
- [references/output-contract.md](references/output-contract.md) — `final_touches_report` and definition-of-done YAML.

## Validation

Before declaring `ready_for_production`:

- All 10 gates plus `make pr-check` MUST pass with evidence (command + pass/fail).
- No new features, web_lead classification changes, or TODO #1–4 duplication.
- `python3 ci/check_pipeline_v2_guard.py` MUST pass.

## Failure Handling

- Gate failure → fix root cause, re-run failed gate; do not skip.
- Regression after a gate → follow rollback path in gate-sequence (DB restore + `make update m=<module>`).
- Missing evidence → label gate `not_run`; verdict MUST be `needs_remediation`.
- Attempt to activate pipeline_v2 → reject immediately; do not proceed.
