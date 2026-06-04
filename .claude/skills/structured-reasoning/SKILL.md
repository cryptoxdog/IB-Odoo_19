---
name: structured-reasoning
description: structured multi-modal reasoning for planning, plan analysis, architecture decisions, and debugging. use when decomposing complex tasks, evaluating trade-offs, root cause analysis, pre-implementation verification, reviewing proposed plans, or when the user asks for deep reasoning, strategy, or decision support.
skill_schema: 1
layer: control_plane
role: skill_entrypoint
tags: [reasoning, planning, architecture, debugging, analysis, leverage, confidence]
owner: igor_beylin
status: active
version: 1.0.0
updated: 2026-06-04
sources:
  - 01_reasoning_engine.kernel.yaml
  - 02_intelligence_analysis_engine.kernel.yaml
  - 07_reasoning_engine_extended.kernel.yaml
  - l9_first_order_thinking_enforcement.kernel.yaml
  - reasoning_think_strategy.kernel.yaml
---

# Structured Reasoning

## Purpose

Apply disciplined, visible reasoning before and during non-trivial work: planning, analyzing plans, architecture decisions, and debugging. Surface highest-leverage paths, quantify trade-offs, and state confidence explicitly.

## When to Load

Load this skill when the task involves:

- **Planning** — multi-step implementation, sequencing, resource trade-offs
- **Plan analysis** — reviewing a proposed approach, PR strategy, refactor plan
- **Architecture decisions** — module boundaries, dependency choices, pattern selection
- **Debugging** — root cause analysis, failure diagnosis, regression investigation
- **Explicit requests** — "think through this", "analyze options", "what's the best approach"

Skip for trivial one-line fixes with no trade-offs.

## Operating Rules

1. **First-order preflight first** — run the five leverage gates silently on every non-trivial turn; surface failures before producing artifacts. Load `references/first-order-gates.md`.
2. **Verify before asserting** — read workspace state with tools; do not answer from memory when evidence is available.
3. **Visible reasoning** — no black-box conclusions; show logic, assumptions, and trade-offs.
4. **Mode routing** — pick strategic / rapid / deep / creative or ADI (abductive → deductive → inductive) based on task type. Load `references/reasoning-modes.md`.
5. **Block protocol** — execute blocks in order for moderate+ complexity; Block 5 gate must pass before irreversible execution. Load `references/reasoning-protocol.md`.
6. **Analysis depth** — match rapid / comprehensive / dependency / performance mode to the question. Load `references/analysis-modes.md`.
7. **Confidence required** — state confidence on every non-trivial recommendation; include fallback for high-stakes plans. Load `references/confidence-and-contingency.md`.
8. **Fail closed** — when confidence is below threshold or a gate fails, halt, surface the blocker, and request confirmation.

## Compact Workflow

```text
Preflight (5 gates) → Complexity (Block 0) → Objective → Context → Decompose → Leverage
→ Strategy (5A/5B/5C) → Pre-action gate (moderate+) → Execute (visible) → Synthesize
→ Anticipate-and-Deliver → Confidence → Implementation plan (if coding)
```

### Task-Type Shortcuts

| Task type | Preflight | Mode | Analysis | Extra |
|-----------|-----------|------|----------|-------|
| Planning | Required | Strategic + ADI | Dependency | B9 plan + ToTh if high-stakes |
| Plan review | Required | Deductive + Comparative | Comprehensive | Quantify effort/coverage ratio |
| Architecture | Required | Strategic + Deep | Dependency + Performance | ≥2 alternatives before recommend |
| Debugging | Required | Deep + Abductive | Rapid → Deep if needed | Disconfirming evidence required |

## Authority Order

1. Explicit user instruction
2. Workspace invariants (AGENTS.md, INVARIANTS.md, module rules)
3. This skill's operating rules
4. Domain-specific skills loaded after this one

## Reference Map

Load references only when relevant:

- `references/first-order-gates.md` — cardinal rule, five gates, proceed protocol, anti-patterns
- `references/reasoning-protocol.md` — block 0–7 + anticipate-and-deliver + B8/B9 extensions
- `references/reasoning-modes.md` — strategic/rapid/deep/creative, ADI workflow, complexity routing
- `references/analysis-modes.md` — rapid/comprehensive/dependency/performance analysis workflows
- `references/confidence-and-contingency.md` — confidence scale, Block 5 gate, ToTh, RAFA, bias mitigation
- `references/validation-checklist.md` — pass/fail gates before delivery

## Validation

Before delivering a reasoning artifact, validate against `references/validation-checklist.md`.

## Failure Handling

When blocked:

- State the exact blocker and which gate or block failed
- Label unverifiable items as `Unknown`
- Surface the highest-leverage alternative with quantified trade-offs
- Do not proceed on moderate+ complexity when Block 5 gate fails without explicit user override
- Do not present low-confidence output as certain
