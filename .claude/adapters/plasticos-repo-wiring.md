# Repo Wiring Contract (PlasticOS)

> **Canonical workflow:** global **`l9-wire-skill-into-repo`** (`@.cursor-commands/skills/l9-wire-skill-into-repo/SKILL.md`).

## Skill Locations

| Scope | Location | Registry |
|-------|----------|----------|
| **L9 global** | `@.cursor-commands/skills/l9-{name}/` | **L9 Global Skills** table + `AGENTS.md` |
| **Project (PlasticOS)** | `.claude/skills/plasticos-*/` | **Project Skills** table + `AGENTS.md` |

All PlasticOS project skills use the **`plasticos-` prefix** on directory name and frontmatter `name`. Do **not** duplicate L9 packs under `.claude/skills/`. Do **not** create `agents/openai.yaml`.

## Register in `.claude/README.md`

**L9 global skill** — add to **L9 Global Skills** table:

```markdown
| **l9-{name}** | `@.cursor-commands/skills/l9-{name}/` | {trigger} |
```

**Project skill** — add to **Project Skills** table:

```markdown
| **plasticos-{name}** | `skills/plasticos-{name}/` | {trigger} |
```

## Register in `AGENTS.md`

Add row to **Agent Skills & Subagents → Skills** with matching `plasticos-*` or `l9-*` name.

## Wire Subagents (`.claude/agents/`)

| Subagent | Preload when skill is… |
|----------|------------------------|
| `code-reviewer.md` | `l9-structured-reasoning`; `plasticos-pr-review-kernel` |
| `module-auditor.md` | `l9-structured-reasoning`, `plasticos-new-odoo-module`, `plasticos-new-model-field` |

Example:

```yaml
skills:
  - l9-structured-reasoning
  - plasticos-new-odoo-module
```

## CLAUDE.md (foundational L9 only)

Add **`l9-structured-reasoning`** to Imports/References when reasoning is foundational.

## Sync `l9-update-agent-docs`

When skill tables change, run **`l9-update-agent-docs`** (adapter: `plasticos-update-agent-docs.md`).

## Validation Gates

- [ ] `name` matches directory (`l9-*` global, `plasticos-*` project)
- [ ] L9 globals in **L9 Global Skills** table only
- [ ] Project skills in **Project Skills** table only
- [ ] Row in `AGENTS.md`
- [ ] Subagent `skills:` updated when preload required
- [ ] No stale unprefixed paths (`new-odoo-module`, `odoo-sh-deploy`, etc.)

## Preload Decision

```text
Cross-cutting reasoning     → l9-structured-reasoning on code-reviewer + module-auditor
L9 tooling                  → AGENTS.md + README only
PlasticOS domain skills     → plasticos-* prefix; preload on matching subagent when needed
```
