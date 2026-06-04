<!--
--- SKILL_META ---
skill_schema: 1
origin: structured-reasoning
layer: reference
role: reasoning_kernel
tags: [reasoning, modes, strategic, debugging, complexity]
owner: igor_beylin
status: active
version: 1.0.0
updated: 2026-06-04
sources:
  - 01_reasoning_engine.kernel.yaml
  - 07_reasoning_engine_extended.kernel.yaml
--- /SKILL_META ---

Purpose:
Mode routing layer — select the right reasoning depth and modality for the task type.
-->

# Reasoning Modes

## Primary Modes (Task Routing)

| Mode | Use when | Rule |
|------|----------|------|
| **Strategic** | Long-term planning, multi-phase projects, resource allocation, architecture | Evaluate risk, cost, and goal alignment before recommending |
| **Rapid** | Time-critical decisions, crisis response, quick diagnostics | Flag that depth is traded for speed; NOT for irreversible ops |
| **Deep analysis** | Root cause, multi-factor evaluation, debugging, regression | Seek disconfirming evidence; do not stop at first plausible explanation |
| **Creative** | Innovation, design decisions, novel problem structures | Generate ≥2 alternatives before recommending one |

## ADI Multi-Modal Workflow

For complex analysis, run sequentially:

1. **Abductive** — What patterns exist? What is most likely happening? (diagnosis, root cause)
2. **Deductive** — Does this follow known rules? Is it consistent? (verification, compliance)
3. **Inductive** — What broader principles apply? How can this scale? (trends, generalization)
4. **Synthesis** — Combine insights, calculate confidence, generate recommendations

When abductive and deductive contradict → surface both with confidence per mode.

## Adaptive Complexity Routing

| Complexity | Approach | Max iterations |
|------------|----------|----------------|
| Simple | Deductive only | 1 |
| Moderate | Deductive + Abductive | 2 |
| Complex | All three ADI modes | 3 |
| Highly complex | Iterative multi-modal + meta-reasoning | 5 |

## Task → Mode Mapping

| Task | Primary mode | ADI | Notes |
|------|-------------|-----|-------|
| Planning | Strategic | Full on complex | ToTh for high-stakes |
| Plan review | Deductive + Comparative | Abductive first | Stress-test proposed plan |
| Architecture | Strategic + Creative | Full | ≥2 paths before select |
| Debugging | Deep + Abductive | Abductive → Deductive | Disconfirming evidence required |
| Quick fix | Rapid | Deductive only | Confidence caveat required |

## Bias Mitigation

Apply on every non-trivial recommendation:

| Bias | Countermeasure |
|------|----------------|
| Confirmation | Actively seek disconfirming evidence |
| Availability | Reference base rates, not just salient examples |
| Anchoring | Evaluate from ≥2 independent reference points |
| Groupthink | Produce independent assessment before accepting consensus |

## Execution Paths

```text
Standard:     B1 → B2 → B3 → B4 → B5 → B6 → B7 → deliver
Low confidence: B7 below threshold → B8 → retry B4-B6 → B7 → deliver
Stuck:        B8 → tool investigation → simplify → resume B3
Crisis:       Rapid → B1 → B4 abbreviated → B5 → B7 → deliver with caveat
```

## Hard Rules

- Do not conflate rapid-mode output with deep-analysis output in the same response
- Rapid-mode shortcuts MUST NOT propagate to deep-analysis paths
- Creative mode MUST produce ≥2 alternatives before single recommendation
