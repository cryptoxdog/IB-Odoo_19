---
name: skill-compiler
description: compile prompts, sops, workflows, kernels, operating protocols, review systems, artifact generators, and domain playbooks into standalone zero-stub skill packs. use when the user asks to create, design, analyze, rebuild, validate, package, or improve reusable agent skills, chatgpt-compatible skill folders, model-agnostic skill packs, or tool-using agent workflows.
skill_schema: 1
layer: control_plane
role: skill_entrypoint
tags: [skill, compiler, control_plane, zero_stub, standalone]
owner: igor_beylin
status: active
version: 1.2.0
updated: 2026-06-04
---

# Strict Skill Compiler

## Purpose

Compile prompts, SOPs, workflows, kernels, operating protocols, review systems, artifact generators, and domain playbooks into clean reusable Skill packs.

The generated Skill must stand alone. Do not assume the executing agent has any external Skill creator protocol, hidden conventions, prior memory, or platform-specific build workflow unless the user explicitly supplies it.

## Operating Rules

- Preserve source intent, required outputs, scope, and constraints.
- Compress source material into operational behavior, not archived prose.
- Keep `SKILL.md` lean as the control plane.
- Formalize the complete base Skill protocol only in `references/skill-pack-contract.md`.
- Keep kernels modular and compressed in `references/`.
- Treat prompts, kernels, contracts, checklists, and output modes as first-class operational primitives.
- Use scripts only when deterministic repeatable execution is explicitly useful.
- Use assets only for reusable final-output material.
- Do not invent connectors, tools, file paths, assets, commands, or dependencies.
- Do not ship dummy scaffolds, unfinished sections, unlinked files, or partial artifacts.
- Do not create `agents/openai.yaml` — wire new skills into repo registries instead (see `references/repo-wiring.md`).
- Fail closed when correctness requires information that is missing and cannot be safely labeled `Unknown`.

## Compact Workflow

1. Parse the source into objective, scope, triggers, workflow, constraints, outputs, resources, risks, and unknowns.
2. Apply first-order and compounding-leverage filters to choose the smallest structure with durable reuse.
3. Select mode: discuss, design, analyze, build, rebuild, or package.
4. Design the file tree and resource map before writing files.
5. Build or revise complete files only.
6. **Wire into repo registries** — `.claude/README.md`, `AGENTS.md`, relevant `.claude/agents/*.md` subagents. Load `references/repo-wiring.md`.
7. Validate metadata, structure, references, repo wiring, zero-stub gates, and package readiness.
8. Deliver the requested artifact and, when useful, one highest-leverage next prompt or next action.

For the full standalone creation protocol, load `references/skill-pack-contract.md`.

## Metadata Discipline

`SKILL.md` uses a **single YAML frontmatter block** for discovery + audit (see `references/meta-standard.md`).

Reference files in `references/` may use HTML-comment metadata blocks. Do not duplicate metadata across frontmatter and comments on `SKILL.md`.

For the metadata contract, load `references/meta-standard.md`.

## Reference Map

Load references only when relevant:

- `references/repo-wiring.md`: mandatory PlasticOS repo registration — AGENTS.md, README, subagent `skills:` preload lists.
- `references/skill-pack-contract.md`: complete standalone Skill creation, analysis, rebuild, validation, and packaging protocol.
- `references/meta-standard.md`: file metadata and first-class primitive rules.
- `references/file-contract.md`: file and folder responsibilities, routing, and resource placement rules.
- `references/output-modes.md`: response contracts for discuss, design, analyze, build, rebuild, and package modes.
- `references/validation-checklist.md`: final validation gates before presenting or packaging a Skill.
- `references/kernel-agent-state.md`: deterministic output discipline, no drift, fail-closed behavior, and explicit-write rules.
- `references/kernel-first-order-thinking.md`: highest-leverage sequencing and five gates.
- `references/kernel-compounding-leverage.md`: compounding leverage scoring and decision thresholds.
- `references/kernel-ynp-next-prompt.md`: one-next-prompt discipline for reducing turns after deliverables.
- `references/kernel-zero-stub-build.md`: complete-artifact enforcement and anti-scaffold checks.
- `references/kernel-reasoning-think-strategy.md`: objective-to-delivery reasoning flow.
- `references/kernel-igoros-insights.md`: scoped hydration, bounded execution, meaning compression, and operational convergence.

## Validation

Before final delivery, validate against `references/validation-checklist.md` and confirm repo wiring per `references/repo-wiring.md`.

A Skill may not be considered complete unless required files exist, metadata is present, references are linked, **repo registries are updated**, trigger logic is strong, kernels are compressed, no dummy scaffolds remain, no `agents/openai.yaml` was created, and package readiness is confirmed.

## Failure Handling

When blocked:

- State the exact blocker.
- Label missing or unverifiable information as `Unknown`.
- Do not fabricate missing resources.
- Provide the smallest safe next action.
- If a complete artifact was requested but cannot be validated, do not present it as complete.
