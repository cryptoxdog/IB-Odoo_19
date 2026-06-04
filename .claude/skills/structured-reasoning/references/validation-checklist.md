<!--
--- SKILL_META ---
skill_schema: 1
origin: structured-reasoning
layer: reference
role: validation_contract
tags: [reasoning, validation, quality_gates]
owner: igor_beylin
status: active
version: 1.0.0
updated: 2026-06-04
--- /SKILL_META ---

Purpose:
Pass/fail gates before delivering a reasoning artifact or proceeding to implementation.
-->

# Validation Checklist

## Preflight (First-Order)

- [ ] Cardinal rule answered internally
- [ ] Five gates evaluated on non-trivial turns
- [ ] Failed gates surfaced before artifacts
- [ ] Higher-leverage alternative quantified when proposed path is suboptimal
- [ ] Confirmation captured for >10 files or >T2 risk plans

## Block Protocol

- [ ] Block 0 (complexity) executed before Block 1
- [ ] All required blocks present in order for task complexity level
- [ ] Block 5 includes 5A, 5B, and 5C
- [ ] Block 5 pre-action gate passed on moderate+ complexity
- [ ] Anticipate-and-Deliver block emitted
- [ ] Block 9 plan present for implementation tasks

## Reasoning Quality

- [ ] Reasoning is visible end-to-end (no black-box conclusions)
- [ ] Assumptions and trade-offs stated explicitly
- [ ] Tool/workspace evidence cited where available
- [ ] Unknown items labeled as Unknown
- [ ] No fabricated references or tool results
- [ ] Disconfirming evidence considered (deep/debug modes)

## Mode and Analysis

- [ ] Correct mode selected for task type
- [ ] ADI workflow applied on complex tasks
- [ ] Analysis mode matches decision stakes (rapid not used for pre-production)
- [ ] Dependency analysis includes circular dependency check when applicable

## Confidence and Contingency

- [ ] Confidence score stated on non-trivial recommendations
- [ ] Low confidence flagged explicitly (not presented as certain)
- [ ] ToTh: ≥2 scored paths on high-stakes decisions
- [ ] RAFA: primary + fallback + trigger on high-stakes plans
- [ ] Rollback plan for destructive operations

## Fail Conditions (reject delivery)

- Reasoning output missing confidence score
- Block 5 gate skipped on moderate+ complexity task
- Destructive op without implementation plan
- Analysis finding without traceable evidence
- Failed first-order gate executed without user override

## Acceptance Criteria

- Highest-leverage work surfaced and prioritized
- Scope drift detected and checkpointed when present
- Synthesis compounds insight instead of restating inputs
- User can act on every block's output without reinterpretation
