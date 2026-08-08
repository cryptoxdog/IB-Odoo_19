# PlasticOS Agent Configuration

Central registry for `.claude/agents/` (subagents). PlasticOS project skills live in repo-root `skills/` (SSOT); `.claude/skills/plasticos-*` are discovery symlinks only.

**L9 universal skills** live in `@.cursor-commands/skills/l9-*/` (Dropbox SSOT via `.cursor-commands`). Not duplicated under `.claude/skills/` or `.cursor/governance/`.

**Invocation tiers** (which L9 skills auto-invoke vs explicit-only) are defined in `@.cursor-commands/skills/AUTONOMY_MANIFEST.yaml` — keep it in sync when adding/removing an L9 skill (see Wiring Rules).

PlasticOS law (this repo): `@skills/PLASTICOS_CANONICAL_LAW.md`  
Global L9 law (symlink — do not edit here): `@.cursor/governance/CANONICAL_LAW.md`

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
| **l9-update-agent-docs** | `@.cursor-commands/skills/l9-update-agent-docs/` | Refresh AGENTS.md, ARCHITECTURE.md, INVARIANTS.md, CLAUDE.md |
| **l9-gmp-protocol** | `@.cursor-commands/skills/l9-gmp-protocol/` | Deterministic phased (0–6) repo changes with modification lock + signed evidence report |
| **l9-context7-docs** | `@.cursor-commands/skills/l9-context7-docs/` | Fetch current library/framework/SDK/API docs before coding |
| **l9-plan** | `@.cursor-commands/skills/l9-plan/` | Create an execution plan/spec when scope is unclear |
| **l9-code-analysis** | `@.cursor-commands/skills/l9-code-analysis/` | Explore unfamiliar code, map flows, identify hotspots |
| **l9-gap-analysis** | `@.cursor-commands/skills/l9-gap-analysis/` | Assess readiness, missing pieces, % complete vs target |
| **l9-pr-analysis** | `@.cursor-commands/skills/l9-pr-analysis/` | Review PRs, merge blockers, review comments, PR readiness |
| **l9-ynp** | `@.cursor-commands/skills/l9-ynp/` | Synthesize the single highest-leverage next action |
| **l9-code-graph-rag-mcp** | `@.cursor-commands/skills/l9-code-graph-rag-mcp/` | Operate code-graph-rag MCP — indexing, importers, impact analysis, cross-module discovery (token-safe) |
| **l9-api-smoke-testing** | `@.cursor-commands/skills/l9-api-smoke-testing/` | Smoke-test every API route; report 404/500 regressions |
| **l9-architecture-decision-records** | `@.cursor-commands/skills/l9-architecture-decision-records/` | Capture an architecture/design decision as an ADR |
| **l9-auditing-performance** | `@.cursor-commands/skills/l9-auditing-performance/` | Profile/optimize bundle, render, query, Core Web Vitals |
| **l9-auditing-security** | `@.cursor-commands/skills/l9-auditing-security/` | Systematic security audit — OWASP Top 10, secrets, insecure patterns |
| **l9-monitoring-terminal-errors** | `@.cursor-commands/skills/l9-monitoring-terminal-errors/` | Watch running processes, fix crashes/stack traces live |
| **l9-prompt-engineering** | `@.cursor-commands/skills/l9-prompt-engineering/` | Design/improve LLM prompts, system messages, output schemas |
| **l9-incident-response** | `@.cursor-commands/skills/l9-incident-response/` | Triage/mitigate production incidents; write postmortems |
| **l9-setting-up-ci** | `@.cursor-commands/skills/l9-setting-up-ci/` | Bootstrap GitHub Actions CI (lint/test/type-check/deploy) |
| **l9-python-tdd-with-uv** | `@.cursor-commands/skills/l9-python-tdd-with-uv/` | **Explicit** — Python TDD with uv (red-green-refactor) |
| **l9-kubernetes-deploying** | `@.cursor-commands/skills/l9-kubernetes-deploying/` | **Explicit** — deploy to Kubernetes (manifests, scaling) |
| **l9-setting-up-terraform** | `@.cursor-commands/skills/l9-setting-up-terraform/` | **Explicit** — bootstrap Terraform IaC (modules, state, CI) |
| **l9-chat-extraction** | `@.cursor-commands/skills/l9-chat-extraction/` | **Explicit** — extract learnings from chat to memory or structured output |
| **l9-ci-ops** | `@.cursor-commands/skills/l9-ci-ops/` | **Explicit** — CI/CD status, fix failures, gates, CI policy authoring |
| **l9-code-maintenance** | `@.cursor-commands/skills/l9-code-maintenance/` | **Explicit** — lint-fix, migrate, refactor-sweep via DAG executors |
| **l9-component-verification** | `@.cursor-commands/skills/l9-component-verification/` | **Explicit** — component audit, verify, runtime probe |
| **l9-dag-authoring** | `@.cursor-commands/skills/l9-dag-authoring/` | **Explicit** — create or update L9 workflow DAGs |
| **l9-end-session** | `@.cursor-commands/skills/l9-end-session/` | **Explicit** — session close, pickup context, governance backup |
| **l9-forge** | `@.cursor-commands/skills/l9-forge/` | **Explicit** — autonomous high-velocity execution |
| **l9-governance-wiring** | `@.cursor-commands/skills/l9-governance-wiring/` | **Explicit** — governance symlinks, wire executor, SSOT backup |
| **l9-harvest-pipeline** | `@.cursor-commands/skills/l9-harvest-pipeline/` | **Explicit** — harvest extraction and deployment pipeline |
| **l9-inspect** | `@.cursor-commands/skills/l9-inspect/` | **Explicit** — external code gate and file audit |
| **l9-repo-index** | `@.cursor-commands/skills/l9-repo-index/` | **Explicit** — export repo indexes for fast lookup |
| **l9-update-command** | `@.cursor-commands/skills/l9-update-command/` | **Explicit** — minimize slash commands to DAG triggers |

## Project Skills

Repo SSOT under `skills/` (not an Odoo addon — like `scripts/` / `tools/`). Discovery symlinks: `.claude/skills/plasticos-*`.

| Skill | Path | Trigger |
|-------|------|---------|
| **plasticos-new-odoo-module** | `skills/plasticos-new-odoo-module/` | Creating a new `plasticos_*` module |
| **plasticos-new-model-field** | `skills/plasticos-new-model-field/` | Adding fields or models to existing modules |
| **plasticos-xml-view** | `skills/plasticos-xml-view/` | Odoo 19 XML views (PlasticOS conventions) |
| **plasticos-odoo-version-bump** | `skills/plasticos-odoo-version-bump/` | Manifest version bumps + scoped `make update m=` (mandatory; never ask) |
| **plasticos-odoo-sh-deploy** | `skills/plasticos-odoo-sh-deploy/` | Odoo.sh production errors, SSH log diagnosis, deploy fixes |
| **plasticos-odoo-docker-testing** | `skills/plasticos-odoo-docker-testing/` | Docker install-smoke / runtime tests before Odoo.sh |
| **plasticos-static-audit-kernel** | `skills/plasticos-static-audit-kernel/` | Static audit command map and evidence contract |
| **plasticos-pr-review-kernel** | `skills/plasticos-pr-review-kernel/` | `PR_REVIEW_MODE`, `REVIEW PR #N` — preloaded on code-reviewer |
| **plasticos-repo-review-kernel** | `skills/plasticos-repo-review-kernel/` | Repo-wide readiness, go-live / pack review |
| **plasticos-final-touches** | `skills/plasticos-final-touches/` | `FINAL_TOUCHES_MODE` — 10 pre-go-live gates |
| **plasticos-prompt-pack** | `skills/plasticos-prompt-pack/` | Prompt-pack router (`AUDIT_MODE`, context primer, architecture chain) |

## Adapters

| File | Used by |
|------|---------|
| `adapters/plasticos-repo-wiring.md` | **`l9-wire-skill-into-repo`** Step 3 |
| `adapters/plasticos-update-agent-docs.md` | **`l9-update-agent-docs`** in PlasticOS repos |

## Wiring Rules

1. **Skill `name` must match directory name.**
2. **L9 globals:** `l9-` prefix, live in `~/.cursor/skills/`, register in **L9 Global Skills** + `AGENTS.md`.
3. **Project skills:** SSOT in `skills/`; discovery symlinks under `.claude/skills/plasticos-*`. Register in **Project Skills** + `AGENTS.md` + `skills/PLASTICOS_SKILLS_MANIFEST.yaml`. All `plasticos-*` skills are **auto-invoke** (`disable-model-invocation: false`). Never add `__manifest__.py` under `skills/`.
4. Subagents preload via frontmatter `skills:` list.
5. Load **`l9-structured-reasoning`** for non-trivial planning and debugging.
6. **New skills:** run **`l9-wire-skill-into-repo`** after **`l9-skill-compiler`**. L9 packs live in `@.cursor-commands/skills/l9-*/` — never repo `.cursor/skills/`. PlasticOS adapter: `adapters/plasticos-repo-wiring.md`. **PlasticOS law:** `@skills/PLASTICOS_CANONICAL_LAW.md`. Global: `@.cursor/governance/CANONICAL_LAW.md` (symlink).

## Related Config

- **Hooks:** `.claude/settings.json`
- **Rules:** `.claude/rules/`
- **Root docs:** `AGENTS.md`, `CLAUDE.md`, `INVARIANTS.md`, `ARCHITECTURE.md`
