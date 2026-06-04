<!--
--- SKILL_META ---
skill_schema: 1
origin: structured-reasoning
layer: reference
role: reasoning_kernel
tags: [reasoning, analysis, dependency, architecture, debugging]
owner: igor_beylin
status: active
version: 1.0.0
updated: 2026-06-04
source: 02_intelligence_analysis_engine.kernel.yaml
--- /SKILL_META ---

Purpose:
Analysis depth modes for codebase, architecture, and system investigation during planning and debugging.
-->

# Analysis Modes

## Mode Selection

| Mode | Use when | Output |
|------|----------|--------|
| **Rapid** | Initial triage, quick diagnostic, scoping | Summary findings + confidence; flag items needing deep analysis |
| **Comprehensive** | Pre-production decisions, plan review, architecture review | Full report with evidence chain and ranked recommendations |
| **Dependency** | Module wiring, circular deps, impact radius | Structured dependency map; circular dependency detection required |
| **Performance** | Bottlenecks, N+1, resource utilization | Ranked issue list with estimated impact |

**Rule:** Rapid mode MUST NOT replace comprehensive analysis for pre-production risk decisions.

## Discovery Workflow

For open-ended investigation (debugging, architecture audit):

```text
1. Initial scan (rapid)
2. Deep dive on flagged areas
3. Pattern identification and classification
4. Insight generation
5. Prioritized recommendation synthesis
```

## Optimization Workflow

For performance or structural improvement:

```text
1. Performance analysis — current state
2. Bottleneck identification
3. Solution generation — ranked options
4. Impact prediction
5. Implementation planning
```

## Task-Specific Analysis Focus

### Planning

- Dependency mode: map what blocks/unlocks downstream work
- Comprehensive mode: validate plan against workspace invariants (AGENTS.md, INVARIANTS.md)
- Document gaps: missing tests, ACL, manifest deps

### Plan Review

- Comprehensive mode: evidence chain for every major claim
- Effort/coverage ratio from first-order gates
- Cross-reference against module layer rules

### Architecture Decisions

- Dependency mode: full graph with blast radius per node
- Performance mode: when scalability or ORM patterns are in scope
- Strategic analysis: missing implementation steps, decision points

### Debugging

- Rapid mode first: reproduce, isolate, hypothesize
- Deep mode if rapid inconclusive: root cause with disconfirming evidence
- Dependency mode if failure spans modules

## Evidence Rules

- Every analysis conclusion MUST cite supporting workspace evidence
- MUST NOT invent findings not supported by data
- Empty scope → report as empty; do not fabricate
- Stale analysis → re-run or flag staleness with timestamp
- Label all Unknown items explicitly

## Invariants

- Circular dependency detection MUST run in every dependency analysis
- Every major finding MUST have traceable source data
- Analysis outputs include scope, methodology, findings, confidence, recommendations
