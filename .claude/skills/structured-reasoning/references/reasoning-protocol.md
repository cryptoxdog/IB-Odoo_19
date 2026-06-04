<!--
--- SKILL_META ---
skill_schema: 1
origin: structured-reasoning
layer: reference
role: reasoning_kernel
tags: [reasoning, blocks, protocol, synthesis, planning]
owner: igor_beylin
status: active
version: 1.0.0
updated: 2026-06-04
sources:
  - 01_reasoning_engine.kernel.yaml
  - 07_reasoning_engine_extended.kernel.yaml
  - reasoning_think_strategy.kernel.yaml
--- /SKILL_META ---

Purpose:
Unified block protocol for visible, sequential reasoning from objective through delivery.
-->

# Reasoning Protocol

## Output Contract

Every full reasoning output follows:

```text
Objective → Analysis → Synthesis → Recommendation → Risks → Next Steps → Confidence
```

## Block Flow

```text
Block 0 → Block 1 → Block 2 → Block 3 → Block 4 → Block 5 → Block 5 Gate → Block 6 → Block 7 → Anticipate-and-Deliver
```

For implementation tasks, append **Block 9 (Plan)** after synthesis.

---

### Block 0 — Complexity Assessment

**MUST execute before Block 1 on every task.**

Outputs: scope, risks, unknowns, decision level (simple / moderate / complex / highly complex).

Auto-escalate complexity when:

- Unknowns > 3
- Interdependencies > 5
- Domain novelty or high stakes

---

### Block 1 — Objective

- Restate task/decision/question in own words
- Define success criteria and metrics
- Identify beneficiaries, urgency, output type
- **Stop:** If objective cannot be restated clearly → request clarification

---

### Block 2 — Context

- Scan workspace for relevant files, constraints, existing state (use tools)
- Map known vs unknown vs dependencies
- State domain, timing, assumptions, adjacent decisions
- **Stop:** If context gap is critical → state explicitly; do not fabricate state

---

### Block 3 — Decompose

- Break into components with sub-part labels
- Map interdependencies and complexity hotspots
- Identify which sub-problems require tool calls vs pure reasoning

---

### Block 4 — Leverage

- Search for prior art in workspace before creating new solutions
- Enumerate reusable assets, patterns, external resources
- Reference tools, repos, or patterns by name — do not invent references
- If no prior work exists → record explicitly; continue without fabrication

---

### Block 5 — Strategy

Cover all three sub-blocks:

| Sub-block | Content |
|-----------|---------|
| **5A Reasoning type** | Logical, empirical, comparative, ethical, legal; note bias blind spots |
| **5B Strategic leverage** | Non-obvious advantages, 10x patterns, unfair advantages |
| **5C Success conditions** | Power-user optimization, unconventional paths |

---

### Block 5 — Pre-Action Verification Gate

**MUST PASS before execution on moderate+ complexity.**

Outputs: checks, gates, go/no-go.

Checks include:

- Intent verified (analysis vs execution)
- Rollback plan for destructive operations
- Credentials/config verified from workspace (never assumed)
- Pattern compliance against known-good examples

**Stop:** Gate failure → halt; surface failed checks; do not proceed without override.

---

### Block 6 — Execute Reasoning

- Work through each component methodically
- Show examples, analogies, counterpoints
- Surface assumptions and trade-offs explicitly
- Use parallel tool calls where dependencies allow
- Log findings; cite tool output in reasoning chain

---

### Block 7 — Synthesize

- State emergent strategic position
- Name what it unlocks
- Answer four add-on prompts:
  1. Shortcuts or playbooks?
  2. Greatest-leverage implementation path?
  3. Unconventional path worth considering?
  4. Second-order effects?

---

### Anticipate-and-Deliver (Sigma)

- Compress expert tacit knowledge into reusable heuristics
- Surface proactive high-leverage assets before being asked
- Anticipate follow-on needs and unconventional paths

---

### Block 8 — Stuck (when triggered)

Use when confidence is low or ambiguity blocks progress:

- Use search/read tools to resolve ambiguity
- Do not guess when tools can verify
- Simplify or restate problem → resume at Block 3

---

### Block 9 — Implementation Plan (coding tasks)

Required before writing code for non-trivial work:

- Critical path and dependencies
- Files to create / modify / delete
- Error handling branches
- Rollback plan for destructive changes

**Invariant:** No destructive operations without Block 9 or equivalent plan.

## Invariants

- Blocks MUST NOT be skipped or reordered on moderate+ complexity
- Block 5 gate MUST NOT be skipped on moderate+ complexity
- Every block produces at least one concrete actionable output
- Reasoning MUST be visible — no conclusions without supporting steps
