# PlasticOS Agent Configuration

Central registry for `.claude/agents/` (subagents) and `.claude/skills/` (project workflows + review kernels).

**L9 universal skills** live in `@.cursor-commands/skills/l9-*/` (Dropbox SSOT via `.cursor-commands`). Not duplicated under `.claude/skills/` or `.cursor/governance/`.

Canonical law: `@.cursor/governance/CANONICAL_LAW.md`

## Subagents

| Agent | File | Preloaded skills | Use when |
|-------|------|------------------|----------|
| **plasticos-code-reviewer** | `agents/code-reviewer.md` | `l9-structured-reasoning`, `plasticos-pr-review-kernel` | PR review, invariant checks, architecture compliance |
| **module-auditor** | `agents/module-auditor.md` | `l9-structured-reasoning`, `plasticos-new-odoo-module`, `plasticos-new-model-field` | Module structure audit, dependency/wiring review |

Invoke via Claude Code subagent delegation or Cursor Task tool (`plasticos-code-reviewer`, `module-auditor`).

## L9 Global Skills

Personal skills — available in all repos via `~/.cursor/skills/`.

| Skill | Global path | Trigger |
|-------|-------------|---------|
| **l9-structured-reasoning** | `@.cursor-commands/skills/l9-structured-reasoning/` | Planning, plan analysis, architecture decisions, debugging |
| **l9-skill-compiler** | `@.cursor-commands/skills/l9-skill-compiler/` | Compile kernels/SOPs into zero-stub skill packs |
| **l9-wire-skill-into-repo** | `@.cursor-commands/skills/l9-wire-skill-into-repo/` | Register skills in repo agent config after create/compile |
| **l9-create-skill** | `@.cursor-commands/skills/l9-create-skill/` | Author new skills; chains l9-wire-skill-into-repo |
| **l9-update-agent-docs** | `@.cursor-commands/skills/l9-update-agent-docs/` | Refresh AGENTS.md, ARCHITECTURE.md, INVARIANTS.md, CLAUDE.md |
| **l9-gmp-protocol** | `@.cursor-commands/skills/l9-gmp-protocol/` | Deterministic phased (0–6) repo changes with modification lock + signed evidence report |

## Project Skills

Repo-local under `.claude/skills/`.

| Skill | Path | Trigger |
|-------|------|---------|
| **plasticos-new-odoo-module** | `skills/plasticos-new-odoo-module/` | Creating a new `plasticos_*` module |
| **plasticos-new-model-field** | `skills/plasticos-new-model-field/` | Adding fields or models to existing modules |
| **plasticos-xml-view** | `skills/plasticos-xml-view/` | Odoo 19 XML views (PlasticOS conventions) |
| **plasticos-odoo-sh-deploy** | `skills/plasticos-odoo-sh-deploy/` | Odoo.sh production errors, SSH log diagnosis, deploy fixes |
| **plasticos-static-audit-kernel** | `skills/plasticos-static-audit-kernel/` | Static audit command map and evidence contract |
| **plasticos-pr-review-kernel** | `skills/plasticos-pr-review-kernel/` | `PR_REVIEW_MODE`, `REVIEW PR #N` — preloaded on code-reviewer |
| **plasticos-repo-review-kernel** | `skills/plasticos-repo-review-kernel/` | Repo-wide readiness, go-live / pack review |
| **plasticos-final-touches** | `skills/plasticos-final-touches/` | `FINAL_TOUCHES_MODE` — 10 pre-go-live gates |

> **Legacy:** `skills/SKILL - Skill Compiler Agent/` is deprecated. Use global **`l9-skill-compiler`**.

## Adapters

| File | Used by |
|------|---------|
| `adapters/plasticos-repo-wiring.md` | **`l9-wire-skill-into-repo`** Step 3 |
| `adapters/plasticos-update-agent-docs.md` | **`l9-update-agent-docs`** in PlasticOS repos |

## Wiring Rules

1. **Skill `name` must match directory name.**
2. **L9 globals:** `l9-` prefix, live in `~/.cursor/skills/`, register in **L9 Global Skills** + `AGENTS.md`.
3. **Project skills:** live in `.claude/skills/`, register in **Project Skills** + `AGENTS.md`.
4. Subagents preload via frontmatter `skills:` list.
5. Load **`l9-structured-reasoning`** for non-trivial planning and debugging.
6. **New skills:** run **`l9-wire-skill-into-repo`** after **`l9-create-skill`** or **`l9-skill-compiler`**. L9 packs live in `@.cursor-commands/skills/l9-*/` — never repo `.cursor/skills/`. PlasticOS adapter: `adapters/plasticos-repo-wiring.md`. **Law:** `@.cursor/governance/CANONICAL_LAW.md`.

## Related Config

- **Hooks:** `.claude/settings.json`
- **Rules:** `.claude/rules/`
- **Root docs:** `AGENTS.md`, `CLAUDE.md`, `INVARIANTS.md`, `ARCHITECTURE.md`
