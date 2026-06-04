<!--
--- SKILL_META ---
skill_schema: 1
origin: structured-reasoning
layer: reference
role: leverage_kernel
tags: [reasoning, leverage, first_order, scope_control, preflight]
owner: igor_beylin
status: active
version: 1.0.0
updated: 2026-06-04
source: l9_first_order_thinking_enforcement.kernel.yaml
--- /SKILL_META ---

Purpose:
First-order thinking enforcement — prevent drift by surfacing highest-leverage work before execution.
-->

# First-Order Gates

## Cardinal Rule

Before executing any workstream, answer internally:

**What is the simplest change that delivers the most functional value?**

## 30-Second Preflight

Run silently on every non-trivial turn. Surface any failed gate **before** producing artifacts.

### Gate 1 — Impact

- Is this functional or cosmetic?
- Is all pending functional work shipped?

**Rule:** Functional work ships before cosmetic work, always.

### Gate 2 — Effort/Coverage Ratio

- Files changed vs endpoints/components benefited?
- Prefer **files:benefit < 1:10**
- Prefer new capability over renames/refactors with no behavior change
- If lines changed >> behavior changed → flag as cosmetic

### Gate 3 — Dependency Check

- Does this block or unlock other work?
- If Work A unlocks B, C, D → do A first
- If A is independent and B is higher-impact → do B first

### Gate 4 — Rabbit-Hole Detector

Signals: scope grew 1→3+ topics, drifting follow-ups, unrequested deliverables, 60+ minutes without shipping.

**Action:** Propose checkpoint — ship, continue, or pivot.

### Gate 5 — Prompt-Quality Mirror

If the prompt mixes topics → decompose, prioritize by impact, propose execution order, ask confirmation.

## Proceed Protocol

When the user says "proceed":

1. Restate the plan in one sentence
2. State effort/coverage ratio
3. State opportunity cost of alternatives skipped
4. Ask confirmation if plan touches **>10 files** or **>T2 risk**

## Exploration Mode

When the user is brainstorming (questions, analogies, multiple options listed):

- Answer concisely (1–3 paragraphs)
- Offer options, not a locked plan
- Quantify trade-offs
- Ask what to do next

## Anti-Patterns (MUST NOT)

- Execute cosmetic work while functional work is pending
- Treat "proceed" as blank check for oversized plans
- Produce guides/matrices/reports that do not move code toward production
- Agree with the plan without stress-testing it
- Silently let scope expand beyond the original ask
- Optimize for responsiveness over leverage

## Edge Cases

| Case | Rule |
|------|------|
| User insists on lower-leverage path after alternative surfaced | Execute; note opportunity cost explicitly |
| Plan exceeds 10 files or T2 risk | Require explicit confirmation |
| Prompt bounces across 3+ topics | Decompose, prioritize, ask agreement |
| 60+ minutes on one topic without shipping | Rabbit-hole checkpoint |
| Artifact does not move code to production | Flag as thoroughness theater; propose shipping alternative |

## Hard Rules

- No workstream executes without passing preflight
- Every failed gate is surfaced before artifact production
- Higher-leverage alternatives are quantified when surfaced
