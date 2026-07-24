---
name: plasticos-prompt-pack
description: Router for the PlasticOS prompt-pack reference docs (docs/plasticos_prompt_pack/) — full-context primer, phased code-review/audit protocol, historical stub/gap handoff, pre-code workspace kernel, and 10-block architecture/deployment reasoning chain. Use to pick and load the right doc for the current situation — onboarding to full project context, running a formal tiered audit (AUDIT_MODE), investigating buyer-matching pipeline gaps, any pre-code compliance pass, or before a major architecture/deployment decision.
skill_schema: 1
layer: control_plane
role: skill_entrypoint
tags: [plasticos, prompt-pack, router, audit, reasoning, context]
owner: igor_beylin
status: active
version: 1.0.0
updated: 2026-07-22
---

# PlasticOS Prompt Pack Router

## Purpose

Five standalone prompt-pack docs live in `docs/plasticos_prompt_pack/`. They encode PlasticOS-specific operating modes that predate — and partially overlap — the current `.claude/skills/plasticos-*-kernel` skills. This skill is the discovery layer: it tells the agent WHICH doc to load for the current situation, so those docs get read and followed automatically instead of sitting unused.

## Core Contract

| Doc | Load when | Status |
|---|---|---|
| [`00_master_space_prompt.md`](../../../docs/plasticos_prompt_pack/00_master_space_prompt.md) | Starting a fresh session that needs a single-page project primer — role, module map, deployment `make` commands, 10 hard rules | Snapshot 2026-05-26 — verify module count / open-PR numbers / dispositions against `AGENTS.md` before repeating them as current |
| [`01_code_review_audit_prompt.md`](../../../docs/plasticos_prompt_pack/01_code_review_audit_prompt.md) | User asks for a formal, phase-numbered audit — `AUDIT_MODE = "TIER_1"` (startup blockers) / `"TIER_2"` (UI stability) / `"TIER_3"` (data & flow integrity) / `"FULL"`, or a PR diff review via `"BUILDER_VALIDATOR_GATE"` | Living protocol — pairs with `plasticos-static-audit-kernel` / `plasticos-pr-review-kernel`; adds the 12-phase structure, severity table, and output contract those kernels don't spell out |
| [`02_coding_agent_handoff.md`](../../../docs/plasticos_prompt_pack/02_coding_agent_handoff.md) | Investigating the buyer-matching "three stubs" pattern (ICP feature gate / engine-stub gate / Neo4j credential gap), or wanting the go-live-checklist format for a wiring-gap handoff | **STALE SNAPSHOT** (2026-05-26; cites PR #88/#85/#83 and a 29-module count) — treat every specific gap/PR/file line as `UNKNOWN` until re-verified against current repo state |
| [`03_workspace_kernel.md`](../../../docs/plasticos_prompt_pack/03_workspace_kernel.md) | Before writing or editing ANY code in this repo — pre-code pass: git-as-source-of-truth priority order, Odoo 19 compliance table, ontology layer-boundary enforcement, `pipeline_v2.py` hard-abort check, namespace drift, web_lead regression hotspots, test-impact safety | Broadest applicability of the five — treat as a standing pre-flight checklist, not a one-time read |
| [`04_meta_reasoning_chain.md`](../../../docs/plasticos_prompt_pack/04_meta_reasoning_chain.md) | Before a major architecture, module, or deployment decision — walk the 10-block chain (scope, module/dependency map, known-gaps audit, stakeholders, AI/graph integration, migration risk, bias detection, decision, execution plan, retro) | Use all 10 blocks for High/Critical risk (matching pipeline, HOT/COLD, PR merges, go-live); Blocks 1/2/6 only for Low risk (config/text fix) |

## Authority Order

1. Explicit user invocation of a specific doc, tier, or block (e.g. "run TIER_1 audit", "walk the reasoning chain").
2. Current repo ground truth (`AGENTS.md`, `INVARIANTS.md`, `git log`, `gh pr list`) overrides any repo-state claim inside `00_master_space_prompt.md` or `02_coding_agent_handoff.md` — those two are dated snapshots, not live state.
3. Existing `.claude/skills/plasticos-*-kernel` skills when their scope matches — don't duplicate work; run the more specific kernel and borrow the prompt-pack doc's extra structure (phases, blocks) as the report/response format.
4. This skill's routing table.
5. `Unknown` — if the situation matches no row, say so rather than forcing a fit.

## Compact Workflow

1. Classify the task: onboarding / formal audit / matching-pipeline gap investigation / pre-code check / architecture-or-deployment decision.
2. Match it to a row above. If two rows match (e.g. audit + pre-code), load both.
3. Read the matched doc(s) in full with the Read tool.
4. Follow the doc's own instructions (its `AUDIT_MODE`, `SCOPE`, phases, or blocks) for the rest of the task.
5. For `00_master_space_prompt.md` / `02_coding_agent_handoff.md`, cross-check every cited PR number, module count, and "open gap" against current repo state before repeating it as fact.

## Resource Map

- `docs/plasticos_prompt_pack/00_master_space_prompt.md` — project primer / master system prompt
- `docs/plasticos_prompt_pack/01_code_review_audit_prompt.md` — 12-phase tiered audit protocol
- `docs/plasticos_prompt_pack/02_coding_agent_handoff.md` — dated stub/gap handoff snapshot
- `docs/plasticos_prompt_pack/03_workspace_kernel.md` — pre-code warning-driven execution kernel
- `docs/plasticos_prompt_pack/04_meta_reasoning_chain.md` — 10-block architecture/deployment reasoning chain

## Validation

Routing is correct when the loaded doc's own "Usage"/"Activation" section (present in docs 01 and 04) is followed as written, and any date-sensitive claim from doc 00 or 02 is labeled `VERIFIED` or `STALE — superseded by <source>` rather than repeated blindly.

## Failure Handling

- Situation matches no row → don't invoke; proceed with normal repo rules (`AGENTS.md`, `.cursor/rules/`).
- Doc 00/02 claim conflicts with current `AGENTS.md` / git state → `AGENTS.md`/git wins; flag the conflict once, don't re-litigate.
- User asks for a specific `AUDIT_MODE` phase with no existing automation → run it manually per the doc's phase description, citing file-level evidence per finding.
