<!--
--- SKILL_META ---
skill_schema: 1
origin: skill-compiler
layer: reference
role: pack_contract
tags: [skill, wiring, agents, registry, plasticos]
owner: igor_beylin
status: active
version: 1.0.0
updated: 2026-06-04
--- /SKILL_META ---

Purpose:
Defines mandatory repo wiring after creating or updating a skill in `.claude/skills/` so agents discover it and subagents preload it when delegating.
-->

# Repo Wiring Contract (PlasticOS)

## Purpose

A skill is **not complete** until it is registered in the repo's agent configuration. Cursor and Claude Code discover skills from `SKILL.md` frontmatter, but **subagents only preload skills listed in their frontmatter `skills:` field** and in the central registries.

Do **not** create `agents/openai.yaml`. Metadata belongs in `SKILL.md` only.

## Mandatory Steps After Building a Skill

Execute in order. Do not skip.

### 1. Create the skill pack

```text
.claude/skills/{skill-name}/
├── SKILL.md              # required — single YAML frontmatter + body
└── references/           # optional — load-on-demand detail
```

**SKILL.md requirements** — single frontmatter block:

```yaml
---
name: skill-name          # MUST match directory name
description: lowercase what + when triggers
skill_schema: 1
layer: control_plane
role: skill_entrypoint
tags: [...]
owner: igor_beylin
status: active
version: 1.0.0
updated: YYYY-MM-DD
---
```

Do not add a separate `SKILL_META` HTML comment — redundant with frontmatter.

### 2. Register in `.claude/README.md`

Add a row to the **Skills** table:

| Skill | Path | Trigger |
|-------|------|---------|
| **{skill-name}** | `skills/{skill-name}/` | One-line when-to-load summary |

### 3. Register in `AGENTS.md`

Add a row to **Agent Skills & Subagents → Skills** table (same trigger text as README).

If the skill changes subagent preload lists, update the **Subagents** table too.

### 4. Wire subagents (`.claude/agents/`)

Add the skill to `skills:` frontmatter on every subagent that should preload it at delegation time.

Current subagents:

| Subagent file | Preload when skill is… |
|---------------|------------------------|
| `code-reviewer.md` | Review/analysis skills (e.g. `structured-reasoning`); domain skills invoked via Skill tool |
| `module-auditor.md` | Module/field/structure skills (e.g. `new-odoo-module`, `new-model-field`, `structured-reasoning`) |

Example frontmatter addition:

```yaml
skills:
  - structured-reasoning
  - new-skill-name    # add when this subagent should preload it
```

**Rules:**

- Preload **cross-cutting** skills (reasoning, analysis) on subagents that need them at startup.
- Preload **domain** skills only on subagents whose role matches (module work → module-auditor).
- Do not preload every skill on every subagent — context cost matters.
- If no subagent matches, register in README + AGENTS.md only; main session discovers via description.

### 5. Update `CLAUDE.md` (selective)

Add to **References** or **Imports** only when the skill is foundational (e.g. `structured-reasoning`, repo-wide reasoning).

Do not list every domain skill in CLAUDE.md — AGENTS.md + README are sufficient for routine skills.

### 6. Update `update-agent-docs` sync (if tables changed)

If skill count or subagent preload lists changed, ensure `update-agent-docs` step 7a still documents the Agent Skills section correctly.

## Forbidden

- **Do not** create `agents/openai.yaml` — unused by Cursor/Claude Code; duplicates `SKILL.md` metadata.
- **Do not** create `agents/` folders for display-only metadata.
- **Do not** ship a skill without README + AGENTS.md registration.

## Validation Gates

- [ ] `name` in frontmatter matches directory name
- [ ] `description` is lowercase with explicit triggers
- [ ] Single frontmatter block on `SKILL.md` with all audit fields (no HTML comment duplicate)
- [ ] Row added to `.claude/README.md` Skills table
- [ ] Row added to `AGENTS.md` Skills table
- [ ] Relevant `.claude/agents/*.md` files updated with `skills:` if subagents should preload
- [ ] No `agents/openai.yaml` or empty `agents/` directory created

## Decision: Which Subagents Get the Skill?

```text
Is it cross-cutting reasoning/analysis?  → code-reviewer + module-auditor (if audit-related)
Is it module structure / wiring?         → module-auditor
Is it code review / invariant check?     → code-reviewer (or invoke via Skill tool)
Is it main-session-only (deploy, docs)?  → README + AGENTS.md only
```

When uncertain, register in README + AGENTS.md and note in delivery which subagent(s) could preload it later.
