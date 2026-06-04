# PlasticOS Agent Configuration

Central registry for `.claude/agents/` (subagents) and `.claude/skills/` (reusable workflows).

## Subagents

| Agent | File | Preloaded skills | Use when |
|-------|------|------------------|----------|
| **plasticos-code-reviewer** | `agents/code-reviewer.md` | `structured-reasoning` | PR review, invariant checks, architecture compliance |
| **module-auditor** | `agents/module-auditor.md` | `structured-reasoning`, `new-odoo-module`, `new-model-field` | Module structure audit, dependency/wiring review |

Invoke via Claude Code subagent delegation or Cursor Task tool (`plasticos-code-reviewer`, `module-auditor`).

## Skills

| Skill | Path | Trigger |
|-------|------|---------|
| **structured-reasoning** | `skills/structured-reasoning/` | Planning, plan analysis, architecture decisions, debugging |
| **new-odoo-module** | `skills/new-odoo-module/` | Creating a new `plasticos_*` module |
| **new-model-field** | `skills/new-model-field/` | Adding fields or models to existing modules |
| **xml-view** | `skills/xml-view/` | Creating or modifying Odoo XML views |
| **odoo-sh-deploy** | `skills/odoo-sh-deploy/` | Odoo.sh production errors, SSH log diagnosis, deploy fixes |
| **update-agent-docs** | `skills/update-agent-docs/` | Refresh AGENTS.md, ARCHITECTURE.md, INVARIANTS.md, CLAUDE.md |
| **skill-compiler** | `skills/skill-compiler/` | Compile kernels/SOPs into zero-stub skill packs |

> **Legacy duplicate:** `skills/SKILL - Skill Compiler Agent/` is deprecated. Use `skills/skill-compiler/` (canonical).

## Wiring Rules

1. **Skill `name` must match directory name** (Claude Code / Cursor discovery).
2. **Metadata lives in `SKILL.md` frontmatter** — single YAML block (`name`, `description`, audit fields); no separate `SKILL_META` comment.
3. Subagents preload skills via frontmatter `skills:` list (full content injected at startup).
4. Main session agents discover skills from descriptions; load `structured-reasoning` for non-trivial planning and debugging.
5. Domain skills (`new-odoo-module`, `xml-view`, etc.) load after reasoning preflight when the task matches.
6. **New skills must be registered** in this README, `AGENTS.md`, and relevant subagent `skills:` lists — see `skills/skill-compiler/references/repo-wiring.md`.

## Related Config

- **Hooks:** `.claude/settings.json` — PreToolUse/PostToolUse/Stop guards
- **Rules:** `.claude/rules/` — domain reference material (invariants, architecture, testing, XML)
- **Root docs:** `AGENTS.md`, `CLAUDE.md`, `INVARIANTS.md`, `ARCHITECTURE.md`
