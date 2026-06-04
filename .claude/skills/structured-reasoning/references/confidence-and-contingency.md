<!--
--- SKILL_META ---
skill_schema: 1
origin: structured-reasoning
layer: reference
role: reasoning_kernel
tags: [reasoning, confidence, contingency, planning, risk]
owner: igor_beylin
status: active
version: 1.0.0
updated: 2026-06-04
source: 07_reasoning_engine_extended.kernel.yaml
--- /SKILL_META ---

Purpose:
Confidence scoring, pre-action gates, multi-path planning, and fallback contingency for high-stakes decisions.
-->

# Confidence and Contingency

## Confidence Scale

State confidence explicitly on every non-trivial recommendation.

| Range | Label | Action |
|-------|-------|--------|
| 0.90–1.00 | Very high | Proceed |
| 0.80–0.89 | High | Proceed with monitoring |
| 0.70–0.79 | Moderate | Validate first |
| 0.60–0.69 | Low-moderate | Need more info |
| < 0.60 | Low | Continue investigation; do not present as certain |

### Thresholds

- **min_execute:** 0.80 — below this, flag explicitly; do not proceed without human review on high-stakes work
- **min_test_first:** 0.70 — validate or test before committing to implementation

### When Confidence Is Low

- Flag low confidence explicitly in output
- Present best available reasoning with caveats
- Trigger Block 8 (Stuck) investigation path
- **Stop at ≤ 0.40 after investigation:** halt and escalate to human

## Block 5 Pre-Action Gate

On moderate+ complexity, verify before execution:

- [ ] Objective and scope locked
- [ ] Context verified with tools (not assumed)
- [ ] Rollback plan for destructive ops
- [ ] Pattern compliance checked against workspace conventions
- [ ] Intent confirmed (analysis vs execution)

**Gate failure → HALT.** Surface specific failed checks.

## Tree-of-Thought (ToTh)

For high-stakes decisions (architecture, large refactors, production changes):

1. Generate **minimum 2 paths**
2. Score each path with rationale and confidence
3. Rank paths before selecting
4. Output: ranked path list with confidence per path

## RAFA Contingency

Every high-stakes plan MUST include:

- **Primary plan** — recommended path
- **Fallback plan** — what to do if primary fails
- **Trigger condition** — when to activate fallback

## Hallucination Mitigation

| Phase | Actions |
|-------|---------|
| Prevention | Citations, confidence scoring, stepwise reasoning, admit uncertainty |
| Detection | Cross-reference workspace evidence, internal consistency check |
| Correction | Regenerate with constraints, smaller chunks, fact-check pass |

## Mistake Prevention

- Mandatory search for prior art before new solutions
- Intent verification: analysis vs execution — confirm before acting
- Failure analysis before retry — do not retry blindly
- Pattern compliance against known-good examples in workspace

## Stop Conditions

| Condition | Action |
|-----------|--------|
| Block 5 gate FAIL, no override | HALT; surface failed checks |
| Confidence < 0.60, no additional data | HALT; escalate to human |
| Required tools unavailable | HALT; report limitation |
| Conflicting instructions (user vs invariant) | Surface conflict; request resolution |

## Regression Guards

- min_execute MUST NOT be lowered below 0.70
- Block 5 gate MUST NOT be skipped on moderate+ complexity
- Confidence MUST be stated in all reasoning outputs
