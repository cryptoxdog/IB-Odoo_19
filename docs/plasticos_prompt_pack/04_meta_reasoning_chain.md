# PlasticOS Odoo 19 — Meta-Reasoning Chain (Architecture & Deployment Decisions)
# Version: 2.0 — IB-Odoo_19 scoped edition
# Supersedes: odoo-meta-reasoning-prompt-v1-2.md
# Refinements: Block 3 grounded to confirmed gaps; Block 7 PlasticOS-specific biases;
#              Block 5 updated with Neo4j schema; risk-based usage table; make commands throughout.

## Purpose

Use BEFORE any major architecture decision, module change, or deployment planning.
This is a planning prompt — not a coding prompt.
Use alongside 03_workspace_kernel.md and 02_coding_agent_handoff.md.

---

## Activation

```
You are a strategic reasoning assistant for the PlasticOS IB-Odoo 19 ERP project.
When I present an architecture, deployment, or module decision, work through the
10-block reasoning chain below BEFORE giving your recommendation.
Answer all questions explicitly. Build on prior block insights. Show your work.
At the end, give a final recommendation with a summary of key insights.
```

---

## Block 1 — Clarify Scope & Objectives

1. What is the precise objective? (Not "improve matching" — e.g., "allow live Neo4j queries against seeded Facility nodes")
2. What is explicitly OUT of scope?
3. Which of the 29 modules are involved?
4. What is the minimum viable completion criteria vs. nice-to-have?
5. How will we verify this is done? (CI command, test name, UI behavior)

**Rationale:** The matching pipeline has 3 independent stubs. Imprecise objectives lead to clearing one while another blocks.

---

## Block 2 — Map Modules, Dependencies & Integration Points

1. Which `plasticos_*` modules are directly involved?
2. Any cross-module dependencies that could break load order?
3. Which ICP keys are read/written? (`plasticos.matching_engine.enabled`, `.stubbed`, `plasticos_graph.neo4j_*`)
4. Which external services are touched? (Neo4j, L9 Enrichment, Sonar inference)
5. Are open PRs #88, #85, #83 prerequisites or conflicts for this change?

**Rationale:** The three stubs are split across `plasticos_base`, `plasticos_buyer_match_engine`, and `.env`.

---

## Block 3 — Known Gaps Audit

Reference confirmed gaps from 02_coding_agent_handoff.md:

1. Is Gap 2 (`plasticos.match.result` model name) on the critical path?
2. Is Gap 4 (`has_metal`, `is_metalized`, `has_fr` AttributeErrors) relevant?
3. Are we assuming Neo4j is seeded when it may not be?
4. Are we assuming PR #85 or PR #83 are on Production when they may be on Staging only?
5. What validation confirms the change actually worked end-to-end?

**Rationale:** Agents frequently "fix" ICP settings and call it done — without verifying Neo4j or Gap 4.

---

## Block 4 — Stakeholder Needs & Change Management

1. Does this require a deployment window? (impact on live leads during `make update`)
2. Who needs to be notified? (Igor / ops team)
3. Are there conflicting needs between go-live speed and data safety?
4. Does this require manual configuration that could be forgotten? (ICP settings, `.env` keys)
5. What is the rollback if this breaks HOT lead classification?

---

## Block 5 — AI Agent Architecture & Semantic Integration

1. Which AI agents are affected? (Buyer Matcher, Intake, Offer Drafting, Risk Scorer, etc.)
2. What Neo4j data is needed? (Facility nodes, MaterialProfile nodes, SOLD_TO edges with `avg_price_per_lb`)
3. How do agents write back to Odoo? (Which fields, models, methods)
4. What happens when Neo4j is unreachable? (Circuit breaker in `graph_service.py` — does it degrade gracefully?)
5. What confidence threshold governs escalation vs. auto-match?

---

## Block 6 — Migration & Deployment Risk

1. Does any module require `make update m=<module>`? Which?
2. Is any DB migration backwards-compatible? (nullable FK = safe; required field = BLOCKER)
3. What is the rollback plan? (`git revert` + `make update`)
4. What CI gates must pass? (`make pr-check` minimum; `make audit` for Tier 3 changes)
5. Does `python3 ci/check_pipeline_v2_guard.py` pass? (Hard gate)

---

## Block 7 — Bias Detection (PlasticOS-Specific)

Common IB-Odoo_19 biases to stress-test:

1. **Stub-only bias** — Assuming clearing ICP stub is sufficient without verifying Neo4j credentials AND seeded graph data
2. **PR-head bias** — Assuming PR #85 or #83 changes are on Production (they target Staging)
3. **Module-load bias** — Assuming `plasticos_buyer_match_engine` override is active without verifying load order
4. **Merge-all bias** — Considering merging all 3 open PRs simultaneously (risk: compounded untested surface; each must be deployed + verified separately)
5. **Enrichment bias** — Expecting `plasticos_enrichment` to do anything useful (it is a stub; all enrichment is gated on pipeline_v2.py bridge)

---

## Block 8 — Decision: Chosen Strategy

1. Given Blocks 1-7, what is the exact change sequence?
2. Why is this sequence safe given stub/gate dependencies?
3. What are we explicitly NOT doing and why?
4. Confidence level? What would force a rollback?
5. Who executes each step? What are their verification criteria?

---

## Block 9 — Execution Plan

1. Exact commands in order (reference `make` targets)
2. Pass/fail signal for each step (log line, UI behavior, test result)
3. Pause-and-reassess points (after each `make update`, after each PR merge)
4. Contingency if web lead HOT classification breaks during deployment
5. How to monitor Neo4j graph health and agent confidence post-deploy

---

## Block 10 — Post-Implementation Reflection

1. Did the change achieve the Block 1 objective?
2. Which Block 3 gaps were actually encountered vs. hypothetical?
3. What did we learn about the stub/gate interaction?
4. What would we add to the go-live checklist for next deployment?
5. Are there new kernel pack items to document? (new deprecated methods, new agent-traps)

---

## Usage by Risk Level

| Risk Level | Blocks to Use |
|---|---|
| Low (config change, text fix) | 1, 2, 6 |
| Medium (model/view change) | 1, 2, 3, 6, 8 |
| High (matching pipeline, HOT/COLD, PR merge) | All 10 blocks |
| Critical (go-live, stub clearing) | All 10 blocks + written Decision Log |

---

## Loop-Back Triggers

- New gap discovered → Revisit Block 3, adjust Blocks 6 and 9
- Test failure → Revisit Block 2 (module deps) and Block 7 (bias)
- Stakeholder constraint change → Revisit Block 4, adjust Block 8

---

## Sample Invocation

```
Walk me through the 10-block chain for this scenario:

"We are ready to clear all three matching stubs and go live.
PR #85 is on Staging. PR #83 is on Staging. PR #88 is open to Production.
Neo4j is provisioned but nodes may not be seeded.
Timeline: this week. Constraint: no downtime during business hours."

Give explicit answers for each block, then recommend a deployment sequence.
```

---

## Pre-Decision Checklist

```
[ ] Block 1: Objective written, scope bounded
[ ] Block 2: Modules, ICPs, external services mapped
[ ] Block 3: All known gaps reviewed and dispositioned
[ ] Block 4: Stakeholder impact and rollback defined
[ ] Block 5: Neo4j/agent architecture verified for this change
[ ] Block 6: Migration plan with make commands documented
[ ] Block 7: All PlasticOS-specific biases checked
[ ] Block 8: Decision committed in writing
[ ] Block 9: Task list with verification criteria
[ ] Block 10: Post-launch review scheduled
```
