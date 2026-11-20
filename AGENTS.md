# AGENTS.md — PlasticOS (Odoo 19)

Read the checked-out `INVARIANTS.md`. Apply the cited `POS-INV-*` ids and `BAN001`. Do not follow a layer diagram, an integer-foreign-key workaround, a local matcher fallback, or a universal `noupdate` rule from older text in this file.

Cross-tool agent instructions for the IB-Odoo_19 repository. Read by Claude Code, Codex, Cursor, Copilot, Jules, Aider, CodeRabbit, and all AGENTS.md-compatible tools.

### Logistics business requirements (BRS)

Linda business-requirements files live inside `plasticos_logistics/business_rules/`. They are not required reading for this instruction set. Keep the seven original BRS files unchanged. For a change that cites them, name the rule id and the observable acceptance evidence. Source status is not runtime proof.

## Project Overview

- **Name**: PlasticOS — Plastics Recycling Brokerage ERP
- **Type**: Odoo 19 custom module suite (**30** `plasticos_*` addons — **28** installable, 2 dev/non-installable; **~33K** lines Python in addons, **~174** XML files in addons).
- **Stage**: Production (`Staging` branch → `Production`)
- **Stack**: Python 3.12, Odoo 19, PostgreSQL 16, Docker

## Commands

```bash
# Linting
ruff check .                              # Python lint
ruff format --check .                     # Format check
ruff format .                             # Auto-format

# Pre-commit (runs all hooks including Odoo-specific)
pre-commit run --all-files

# Odoo-specific checks
python3 scripts/check_module_wiring.py    # Dependency graph integrity
python3 ci/check_circular_deps.py         # Circular dependency detection
python3 ci/check_orphan_model_refs.py     # Orphan model references
python3 ci/check_odoo19_xml.py            # XML view validation
python3 tools/cron_invariant_check.py     # Cron safety invariants

# Roadmap (registry → synced planning docs)
make roadmap                              # Sync + validate (add: domain= phase= kind= title=)
make roadmap-list                         # List registry items

# pr-check = local (ruff, XML, wiring, semgrep, pytest) + remote when PR/CI exists
#   (GitHub Actions job logs, SonarCloud, CodeRabbit, Gemini, human reviews via pr_autopilot)
#   Target a PR: make pr-check pr=100
#     or: make pr-check https://github.com/cryptoxdog/IB-Odoo_19/pull/100
#   Skip remote: PR_CHECK_SKIP_REMOTE=1 make pr-check

# Publication: make pr validates the committed HEAD, pushes the feature branch,
# and opens or verifies the PR into Staging. make push is retired.
make pr                                   # publish the committed feature branch into Staging

# Docker
docker-compose up -d                      # Start Odoo + PostgreSQL + Redis
docker-compose exec web odoo -u plasticos_base --stop-after-init  # Update module

# Data imports (canonical commands — odoo-intent-1 ingestion milestone)
make import-erp                           # ERP import through SQL (DRY=1 preview)
make import-vanillasoft                   # VanillaSoft full import: preflight + reconciliation + summary
python3 scripts/validate_import_summary.py .l9/pr/import-*-summary.json  # validate machine summaries

# Tests (requires running Odoo instance)
python -m pytest tests/ -v                # All tests
python -m pytest tests/contracts/ -v      # Contract tests
python -m pytest tests/integration/ -v    # Integration tests
```

## Repo Index — Check Before Grepping

`reports/repo-index/` holds pre-generated, grep-friendly indexes of the codebase (classes, functions, methods, imports, inheritance, Odoo models/views/crons/security groups/automations/email templates/routes, tests, READMEs). Check these **before** running a broad `grep`/`rg` sweep across the repo:

```bash
grep "ClassName" reports/repo-index/class_definitions.txt
grep "plasticos.transaction" reports/repo-index/odoo_model_registry.txt
grep "def action_" reports/repo-index/method_catalog.txt
```

Regenerate when stale via the `l9-repo-index` skill (synced generator script; no repo-local generator exists in this repo). See `@.cursor-commands/skills/l9-repo-index/SKILL.md`.

## Tooling SSOT (editor + CI)

This repo is an **Odoo addon suite**, not a pip/uv package. No `[project]` table in `pyproject.toml`.

| Concern | File | Notes |
|---------|------|-------|
| Ruff / pytest / mypy / Pyright policy | `pyproject.toml` | Pyright is **editor-only** (`typeCheckingMode = basic`) |
| Odoo import paths (Pylance) | `.vscode/settings.json` | `${env:HOME}/dev/odoo-19` — clone Odoo 19 CE on each machine |
| Dev venv | `make venv` + `.envrc` | ruff, pytest, semgrep — Odoo runtime is separate |
| Runtime deps | `requirements.txt` | Odoo.sh |
| Dev/CI deps | `requirements-dev.txt` | GitHub Actions Tier 3 |

Cursor overlay: `.cursor/rules/88-plasticos-odoo-python-tooling.mdc`. Global `20-lang-python` applies only to L9 `src/` repos, not PlasticOS.

**Fresh clone runbook:** [docs/LOCAL_DEV_SETUP.md](docs/LOCAL_DEV_SETUP.md)

## OdooLS

Editor semantics for Odoo models, XML, and JavaScript come from the official `Odoo.odoo` extension. The workspace profile is `default`. Configuration is `odools.toml`. Runtime and deployment stay on Odoo.sh.

| Source | Path | Indexed | OdooLS diagnostics |
|--------|------|---------|--------------------|
| Community | `${userHome}/dev/odoo-19` | yes | suppressed |
| Enterprise | `${userHome}/Dropbox/Repo_Dropbox_IB/IB-Odoo_19/odoo-enterprise` on `addons_paths`. `$autoDetectAddons` still skips the gitignored `odoo-enterprise` symlink | yes | suppressed |
| PlasticOS | this workspace | yes | published |

`diagnostic_filters` uses `path_type = "in"` on those two upstream trees and does not name diagnostic codes. Do not globally disable OLS codes. Do not set `disable_javascript` or an empty `tsserver_command`. JavaScript semantics need TypeScript 6 `tsserver` on `PATH` (`npm install -g typescript@6`).

Ruff and basedpyright use the same boundary, and neither expands `${env:HOME}`. Opened upstream files sit outside this workspace, so workspace `ruff.exclude` does not apply to them: the user-level `ruff.exclude` lists the Community and Enterprise trees. basedpyright skips editor `analysis.ignore` when `[tool.pyright]` exists, so those paths are in `pyproject.toml` `ignore` (editor-only; Pyright is not a CI gate). PlasticOS files stay diagnosed. Do not turn either tool off.

## Testing

- Contract tests: `tests/contracts/` — 8 contract test files
- Integration tests: `tests/integration/` — 10 integration test files
- Unit tests: `tests/test_*.py` — **32** standalone test modules at `tests/` root (plus deeper `tests/` tree; run `pytest tests/ --collect-only` for full count)
- Every new model/field needs at least one test
- Tests must not mutate seed data
- Run `pre-commit run --all-files` before opening a PR

## Agent Skills & Subagents

**PlasticOS law (this repo):** `skills/PLASTICOS_CANONICAL_LAW.md`
**Global L9 law (symlink — do not edit from IB-Odoo_19):** `.cursor/governance/CANONICAL_LAW.md`

| Class | SSOT | Notes |
|-------|------|-------|
| PlasticOS project skills (`plasticos-*`) | `skills/` | Repo-owned; not an Odoo addon (like `scripts/` / `tools/`) |
| Manifest | `skills/PLASTICOS_SKILLS_MANIFEST.yaml` | All `invocation: auto` |
| Discovery adapters | `.claude/skills/plasticos-*` | Symlinks into `skills/` only — edit SSOT, not the link |
| L9 global skills (`l9-*`) | `@.cursor-commands/skills/l9-*/` | Cursor-Governance / GlobalCommands |
| Invocation tiers (L9 only) | `@.cursor-commands/skills/AUTONOMY_MANIFEST.yaml` | PlasticOS skills are always auto-invoke |

Full project registry: `.claude/README.md`. Validate: `make check-plasticos-skills`.

| Skill | When to load | Primary `make` targets |
|-------|--------------|------------------------|
| `l9-structured-reasoning` | Planning, plan review, architecture decisions, debugging | — |
| `l9-skill-compiler` | Compile kernels/SOPs into zero-stub skill packs | — |
| `l9-wire-skill-into-repo` | Register skills after create/compile | — |
| `l9-update-agent-docs` | Refresh AGENTS.md / ARCHITECTURE.md / INVARIANTS.md / CLAUDE.md | — |
| `l9-gmp-protocol` | Deterministic phased (0–6) repo changes with modification lock + signed evidence report | `pr-check` |
| `l9-context7-docs` | Fetch current library/framework/SDK/API docs before coding | — |
| `l9-plan` | Create an execution plan/spec when scope is unclear | — |
| `l9-code-analysis` | Explore unfamiliar code, map flows, identify hotspots | — |
| `l9-gap-analysis` | Assess readiness, missing pieces, % complete vs target | — |
| `l9-pr-analysis` | Review PRs, merge blockers, review comments | `pr-check` |
| `l9-ynp` | Synthesize the single highest-leverage next action | — |
| `l9-code-graph-rag-mcp` | Operate code-graph-rag MCP — indexing, importers, impact analysis, cross-module discovery | — |
| `l9-api-smoke-testing` | Smoke-test every API route; report 404/500 regressions | — |
| `l9-architecture-decision-records` | Capture an architecture/design decision as an ADR | — |
| `l9-auditing-performance` | Profile/optimize bundle, render, query, Core Web Vitals | — |
| `l9-auditing-security` | Systematic security audit — OWASP Top 10, secrets, insecure patterns | — |
| `l9-monitoring-terminal-errors` | Watch running processes, fix crashes/stack traces live | — |
| `l9-prompt-engineering` | Design/improve LLM prompts, system messages, output schemas | — |
| `l9-incident-response` | Triage/mitigate production incidents; write postmortems | — |
| `l9-setting-up-ci` | Bootstrap GitHub Actions CI (lint/test/type-check/deploy) | — |
| `l9-python-tdd-with-uv` | **Explicit** — Python TDD with uv (red-green-refactor) | — |
| `l9-kubernetes-deploying` | **Explicit** — deploy to Kubernetes (manifests, scaling) | — |
| `l9-setting-up-terraform` | **Explicit** — bootstrap Terraform IaC (modules, state, CI) | — |
| `l9-chat-extraction` | **Explicit** — extract learnings and content from chat to memory or structured output | — |
| `l9-ci-ops` | **Explicit** — CI/CD status, fix failures, list gates, author CI regression policies | — |
| `l9-code-maintenance` | **Explicit** — lint-fix, migrate, clean/compress, consolidate, refactor-sweep via DAG executors | — |
| `l9-component-verification` | **Explicit** — component audit, verify, runtime probe escalation ladder | — |
| `l9-dag-authoring` | **Explicit** — create or update L9 workflow DAGs via dag-authoring-v1 | — |
| `l9-end-session` | **Explicit** — close session, pickup context, governance backup | — |
| `l9-forge` | **Explicit** — autonomous high-velocity execution, batch GMP runs | — |
| `l9-governance-wiring` | **Explicit** — governance symlinks, wire executor, confirm-wiring, SSOT backup | — |
| `l9-harvest-pipeline` | **Explicit** — harvest extraction and use-harvest deployment pipeline | — |
| `l9-inspect` | **Explicit** — inspect external code before it enters L9 | — |
| `l9-repo-index` | **Explicit** — export repo indexes for fast lookup | — |
| `l9-update-command` | **Explicit** — minimize slash commands to DAG triggers | — |
| `plasticos-new-odoo-module` | Scaffolding a new `plasticos_*` module | `wiring`, `pr-check` |
| `plasticos-new-model-field` | Adding fields or models to existing modules | `wiring`, `pr-check` |
| `plasticos-xml-view` | Creating or modifying Odoo XML views | `odoo19-check`, `xml-check` |
| `plasticos-odoo-version-bump` | Changing plasticos_* runtime code/XML/migrations — **mandatory** version bump + scoped `-u` only | `update` |
| `plasticos-odoo-sh-deploy` | Odoo.sh production errors — SSH diagnose before fix | `logs`, `update`, `test-module` |
| `plasticos-odoo-docker-testing` | Docker install-smoke + Odoo runtime tests before Odoo.sh | `install-smoke`, `test-odoo`, `test-module` |
| `plasticos-pr-integration` | Combine open pull requests in a disposable worktree and run full Enterprise install-smoke | `install-smoke`, `runtime-test` |
| `plasticos-static-audit-kernel` | Broad static audit / evidence report | `audit`, `audit-quick` |
| `plasticos-pr-review-kernel` | `PR_REVIEW_MODE`, `REVIEW PR #N` | `pr-check`, `audit` |
| `plasticos-repo-review-kernel` | Repo-wide readiness / pack review | `audit`, `wiring` |
| `plasticos-final-touches` | `FINAL_TOUCHES_MODE` | `audit` + `pr-check` |
| `plasticos-branch-promotion-rehearsal` | Staging → Production promotion: rehearse the post-cutover imports at 10% volume, five evidence files max | `import-erp`, `import-vanillasoft` |
| `plasticos-prompt-pack` | Router for `docs/plasticos_prompt_pack/` — context primer, tiered audit (`AUDIT_MODE`), matching-pipeline gap handoff, pre-code kernel, 10-block architecture/deployment reasoning chain | `audit`, `pr-check` |

| Subagent | Preloaded skills | Delegate for |
|----------|------------------|--------------|
| `plasticos-code-reviewer` | `l9-structured-reasoning`, `plasticos-pr-review-kernel` | PR review, invariant compliance |
| `module-auditor` | `l9-structured-reasoning`, `plasticos-new-odoo-module`, `plasticos-new-model-field`, `plasticos-odoo-version-bump`, `plasticos-odoo-docker-testing` | Module audit — attach `plasticos-repo-review-kernel` or `plasticos-static-audit-kernel` |

## Project Structure

```
skills/                # PlasticOS agent skills SSOT (NOT an Odoo addon; see PLASTICOS_CANONICAL_LAW)
plasticos_base/              # Layer 1: Core seed data, feature gates, partner tags
plasticos_security_base/     # Layer 1: RBAC roles, record rules, ACL
plasticos_material_profile/  # Layer 1: Material master (polymer, form, color, source)
plasticos_product/           # Layer 1: Scrap plastic product catalog
plasticos_facility_profile/  # Layer 2: Facility capabilities, equipment, tolerances
plasticos_intake/            # Layer 2: Material intake with contact intelligence
plasticos_intake_normalizer/ # Layer 2: L9 packet normalization
plasticos_matching/          # Layer 2: Gate match orchestrator + result store (ADR-015; CEG scores)
plasticos_geolocalize/       # Layer 2: Auto-geocode + nightly backfill
plasticos_gate/              # Layer 2: Sole TransportPacket client (ADR-002 / ADR-011)
plasticos_enrichment/        # Layer 2: Gate converge orchestrator + writeback shell (ADR-012/015; ranking ADR-009)
plasticos_web_leads/         # Layer 2: AI lead triage local Phase 1 (ADR-016; not enrichment ranking)
plasticos_accounting/        # Layer 3: Chart of accounts, payment terms, incoterms
plasticos_offer/             # Layer 3: Offer lifecycle (match → negotiation → deal)
plasticos_order_lines/       # Layer 3: PO/SO lines with material specs
plasticos_automation/        # Layer 3: Workflow automation, SLA monitoring
plasticos_partner_import/    # Layer 3: Partner import wizard
plasticos_crm_bridge/        # Layer 3: CRM integration bridge
plasticos_commission/        # Layer 3: Commission calculation engine
plasticos_documents/         # Layer 4: Document validation matrices
plasticos_documents_native/  # Layer 4: Enterprise Documents bridge
plasticos_transaction/       # Layer 5: Transaction spine + commission
plasticos_logistics/         # Layer 5: Load management, BOL, dispatch
plasticos_claims/            # Layer 5: QC cases, claims, chargebacks
plasticos_website/           # UI: Website extensions (installable: False — disabled)
plasticos_admin_dashboard/   # Layer 3: RevOps KPI dashboard (admin)
plasticos_odoo_standard_apps/ # Meta: auto-install bundle of standard Odoo CE apps (optional)
plasticos_dev_tools/         # Dev-only: audit scripts, integrity checks
tests/                       # Cross-module test suite
ci/                          # CI audit scripts (Odoo/XML/ORM/deps; ~27 Python tools)
tools/                       # Cron checks, validators
```

## Code Style

- Python 3.12+, Odoo 19 ORM patterns
- `ruff format` (120-char line length) before commit
- Model names: `plasticos.model_name` (always `plasticos.` prefix)
- External IDs: `plasticos_module.external_id`
- Module names: `plasticos_*` prefix
- Model string constants at module top: `RES_PARTNER = "res.partner"`
- Logging: `_logger = logging.getLogger(__name__)`
- Fields: Odoo `fields.*` with `help=`, `tracking=True` for business fields
- No `@api.one` or `@api.multi` (removed in Odoo 13)
- No `_sql_constraints` (use `models.Constraint` in Odoo 19)

## Git Workflow

- Branch from `Staging`, PR to `Staging` (branch names are capitalized; macOS case-insensitivity makes `git checkout staging` resolve to `Staging`)
- Merge `Staging` → `Production` for production — never merge feature branches directly to `Production`
- Branch naming: `feat/short-description`, `fix/short-description`, `docs/short-description`, `refactor/short-description`, `test/short-description`
- Commit messages: conventional commits with optional module scope — `feat(module): ...`, `fix(views): ...`, `docs: ...`, `refactor(intake): ...`, `test(integration): ...`
- **`make commit` omits `.cursor-commands`** — local symlink to Dropbox governance SSOT; that tree is pushed from a separate repo, never from IB-Odoo_19. Publication is `make pr`
- PRs require passing CI: ruff + XML validation + Odoo pattern checks + secret scan (gitleaks)

## CI Compliance Checklist (MANDATORY before commit/PR)

Every code change MUST pass these checks. CI will reject PRs that fail. This section is the authoritative reference for all CI gates.

### When you create a NEW Python file

1. Add `from . import <filename>` to the parent `__init__.py`:
   - `models/__init__.py` for model files
   - `controllers/__init__.py` for controller files
   - `wizards/__init__.py` for wizard files
2. The root module `__init__.py` must NOT be empty (CI check #7)
3. If the file defines a new Odoo model (`_name = "plasticos.something"`):
   - Add ACL entry in `security/ir.model.access.csv`
   - Add the CSV to `__manifest__.py` `data` list if not already there
4. Cross-addon imports (`from odoo.addons.plasticos_*`) MUST be inside functions, never at module top level

### When you create a NEW model

1. `_name` MUST be a string literal (`_name = "plasticos.foo"`) — NEVER a variable or constant. CI enforces this with `grep _name = [A-Z]` in `ci.yml`
2. Add `security/ir.model.access.csv` entry with manager (CRUD) and user (CRU) rows minimum
3. Every `fields.Many2one` MUST have `ondelete=` parameter (`"restrict"`, `"set null"`, or `"cascade"`)
4. Every `@api.constrains(...)` field name must exist on the model (CI validates this)
5. Use `models.Constraint` / `UniqueConstraint` — NEVER `_sql_constraints`
6. Class name MUST use `Plasticos` prefix (not `Plastos`) — CI check #8

### When you create or modify XML files

1. Use `<list>` not `<tree>` for list views (CI check #12)
2. No `string="..."` on `<search>` views (CI check #13)
3. No `string="..."` on `<group>` inside search (CI check #14)
4. No `attrs="{...}"` on any element — use `invisible=`, `readonly=`, `required=` directly (CI check #19)
5. No `states=` attribute on fields (CI check #20)
6. No `decoration-secondary=` (CI check #15)
7. No `t-esc=` — use `t-out=` (CI check #16)
8. Font Awesome `<i>` tags MUST have `title="..."` for accessibility (CI check #21)
9. All `&` must be escaped as `&amp;` (CI check #6)
10. `eval="..."` — no nested double quotes; use single quotes inside: `eval="[ref('module.id')]"` (CI check #11)
11. Cron `model_id` refs MUST include module prefix: `ref="plasticos_module.model_plasticos_model"` (CI check #10)
12. No `numbercall` on `ir.cron` (CI check #5)
13. No `category_id` on `res.groups` records (CI check #4)
14. Stable reference data that must survive an upgrade may use `<odoo noupdate="1">`. That is not a rule for every XML record.

### When you modify `__manifest__.py`

1. Every module you `from <module> import ...` MUST be in the `depends` list
2. Every XML/CSV file in `data/` or `security/` MUST be in the `data` list
3. No circular dependencies: if A depends on B, B cannot depend on A
4. `__manifest__.py` must be valid Python syntax (CI validates via `exec()`)

### When you write Python code

1. **Ruff line length**: 120 characters (NOT 100) — configured in `pyproject.toml`
2. **Import sorting**: `isort` via ruff (I001) — Odoo `__init__.py` files are exempt (F401, I001)
3. **No `@api.depends("id")`** (CI check #2)
4. **No `@api.one` or `@api.multi`** (CI check #3)
5. **No `self.env.get("model.name")`** — use `self.env["model.name"]` (CI check #24)
6. **No `x_` prefixed fields** (CI check #23)
7. **No string writes to Many2one fields** — write `record.id` not `"value_string"` to relational fields (CI check #22)
8. Related fields using old intake paths must use `_id` suffix (CI check #18)

### Before committing

Run these checks (all must pass):

```bash
ruff check --fix .                        # Fix lint issues
ruff format .                             # Format code
python3 scripts/check_module_wiring.py    # Dependency + __init__.py wiring
python3 ci/check_circular_deps.py         # No circular deps
python3 ci/check_odoo19_xml.py            # XML pattern compliance
pre-commit run --all-files                # Run ALL 36 hooks at once
```

### CI Architecture — `ci.yml` is the Single Gate (9 Workflow Files)
`ci.yml` is the **only check workflow that runs automatically on PRs and pushes and blocks merge**, alongside the GATE-01 baseline ratchet. The legacy check workflows (`pr-gate.yml`, `odoo-audit.yml`, `module-check.yml`, `test-quality.yml`) were **deleted** during GATE-01 adoption (#112): they were manual-only, and most of their checks were already duplicated in `ci.yml`. **2026-07 correction:** a follow-up audit found #112 had also silently dropped several checks that were NOT duplicates (mypy, shellcheck, `_name` string-literal enforcement, manifest field validation via `scripts/validate_manifest.py`, ACL CSV header/format check, test-attribute-guard, and the `odoo_audit.py`/`run_all_audits.py` baseline-regression audit with PR auto-comment) — all were restored into `ci.yml` as new checks/jobs (see inline `restored 2026-07` comments in the workflow file). `l9-analysis.yml` was added as a new, additive, non-duplicating governed-semgrep pipeline (see `.github/governance/README.md`) — it does not block merge yet (advisory-first rollout).

**2026-07 fail-slow correction:** `ci.yml`'s `lint`/`static-checks`/`pure-python-tests` previously ran as a sequential `needs:` chain (Tier 1 → 2 → 3), so a `lint` failure hid every static-analysis and test failure until fixed and re-pushed — the opposite of "identify all errors in one CI run." They now run in **parallel** (no `needs:` between them) alongside `secret-scan` and the new `audit-baseline` job; a final `ci-gate-result` job (`needs:` all of them, `if: always()`) is the single fail-closed verdict. `ci/check_github_actions_kernel.sh`'s `merge_gate_logic` check enforces this contract structurally (no `needs:` on the three tiers, an aggregator job present).

**Cross-workflow order (max concurrent → aggregator last):** On each PR push, **CI Gate**, **Baseline Ratchet**, and **L9 Analysis** start together (Wave 1 collectors). Do **not** serialize them with `workflow_run`. Wave 2 aggregators (`CI Gate Result`, `Ratchet Verdict`) and L9 `publish` run last within their own workflows. Prefer required merge checks on those aggregators; keep L9 advisory-first until `.github/governance/` promotes rules. **GitGuardian** is an external app (not a workflow) — it scans the PR commit range and does not cancel GHA; tip-only secret fixes leave GG red if an earlier PR commit still contains the secret (squash/rewrite the feature branch, or resolve the occurrence after rotation). Each workflow uses its own `concurrency` group with `cancel-in-progress: true` — treat only the latest **non-cancelled** HEAD run as signal.

**Active workflows and their triggers:**
| Workflow | Trigger | Purpose |
|----------|---------|---------|
| **`ci.yml`** | push + PR (all branches) | Single CI gate — lint / static / pytest / secret-scan / audit-baseline run in parallel (fail-slow), `ci-gate-result` aggregates last |
| **`baseline-ratchet.yml`** | push + PR → Staging | GATE-01 baseline ratchet (l9-ci-core reusable workflow, SHA-pinned) |
| `l9-analysis.yml` | push → Staging + PR + manual | l9-ci-core governed semgrep pipeline (generic `p/python`), publishes a GitHub Check; advisory-first, not yet a required check |
| `security.yml` | push + PR → staging/main + weekly | pip-audit, Trivy, Gitleaks |
| `changelog.yml` | push → Production + manual | Auto-update CHANGELOG.md |
| `auto-merge.yml` | PR events → staging/main | Auto-merge — arms ONLY when the PR carries the `automerge` label |
| `auto-review-request.yml` | PR opened/sync → staging/main | Auto-request reviewers |
| `release.yml` | tag `v*.*.*` + manual | GitHub Release creation |
| `pr-autopilot.yml` | manual only | Scan open PRs for CI/SonarCloud signals |

**`ci.yml` blocking jobs** (must pass for merge) — **fail-slow, not fail-fast**: `lint`, `static-checks`, `pure-python-tests`, `secret-scan`, and `audit-baseline` run **concurrently** (no `needs:` between them; each job still aggregates ALL of its own checks before exiting). A final `ci-gate-result` job (`needs: [lint, static-checks, pure-python-tests, secret-scan, audit-baseline]`, `if: always()`) runs last and is the single fail-closed verdict for the workflow — every job still must pass, this just surfaces every failure in one run instead of stopping at whichever tier failed first.

| CI Job | Phase | What it checks | Common failure |
|--------|-------|---------------|----------------|
| `lint` | 1 (parallel) | `ruff check` + `ruff format --check` | Unsorted imports (I001), unformatted code |
| `static-checks` | 1 (parallel) | XML syntax, bash syntax, manifest syntax + field validation (`scripts/validate_manifest.py`), `_name` string-literal enforcement, shellcheck, Semgrep Odoo/security rules (`.semgrep/odoo-patterns.yml`), circular deps, module wiring, orphan refs, XPath stability, model inheritance, ORM integrity, Odoo 19 hook/XML patterns, dev-tools fence, pipeline-v2 guard, critical manifest, enhanced audit, antipatterns, ACL completeness, package init, field integrity, state-guard bypass, weak-test detection | Missing `__init__.py` import, broken XPath, phantom dep, semgrep rule hit, shellcheck warning, `_name = CONSTANT` |
| `pure-python-tests` | 1 (parallel) | pytest suite (no Odoo runtime): dependency integrity, compat, cron invariants, XML patterns, enum alignment | Test assertion failure, missing fixture |
| `secret-scan` | 1 (parallel) | Gitleaks (blocking — GATE-01 fail-closed; no `continue-on-error`) | Leaked token/password in git history of the push |
| `audit-baseline` | 1 (parallel) | `scripts/audit/odoo_audit.py` (field/required-field/compute/security/constraint/state-machine/onchange bugs; baseline CRITICAL=0 HIGH=0) + `scripts/audit/run_all_audits.py` (extended: business-logic/performance/security N+1 queries; baseline HIGH≤4 — pre-existing `plasticos_logistics/load.py` + `plasticos_transaction/transaction.py`); auto-comments on the PR and uploads an `odoo-audit-reports` artifact on regression | New CRITICAL/HIGH issue vs tracked baseline — read the PR comment or artifact |
| `ci-gate-result` | 2 (sequential, always last) | Aggregates the 5 Phase 1 jobs above; fails if any is not `success` | One of the Phase 1 jobs failed — read ITS log, not this job's |

**Advisory-only checks inside `static-checks`** (logged but never fail the job): `mypy` (type checking — not a CI gate per `.cursor/rules/88-plasticos-odoo-python-tooling`, pre-commit only), ACL CSV header/format check, test-attribute-guard (`self.*_rec` warn). These same checks ARE blocking as local pre-commit hooks where applicable (see Pre-commit Hooks table) — the CI/pre-commit blocking status differs per check.

**Non-blocking (advisory):**

| CI Job | Workflow | Notes |
|--------|----------|-------|
| `dependency-scan` | `security.yml` | `pip-audit \|\| true` |
| `trivy-scan` | `security.yml` | `exit-code: 0` |
| `l9-analysis.yml` (all jobs) | `l9-analysis.yml` | Governed semgrep findings default to `mode: advisory` in `.github/governance/semgrep-policy.yaml` — no individual rule is promoted to blocking yet |

**External Odoo.sh checks (NOT GitHub Actions — cannot disable in `.github/workflows/`):**

| Status context | When it appears | Repo gate? |
|----------------|-----------------|------------|
| `ci/odoo.sh (dev)` | PRs from feature branches (`fix/*`, `feat/*`) | **No** |
| `ci/odoo.sh (staging)` | Commits on `Staging` | **No** |
| `ci/odoo.sh (production)` | Commits on `Production` | **No** |

These are **commit statuses** pushed by Odoo.sh (webhook: `https://www.odoo.sh/paas/webhook/github`), not jobs in `ci.yml`. There is no workflow file to delete.

**To stop `ci/odoo.sh (dev)` showing on PRs (keeps Odoo.sh deploys working):**

1. Open https://www.odoo.sh/project/cryptoxdog-ib-odoo-19 → **Settings** (Admin only)
2. Section **GitHub commit statuses** → **remove / clear the GitHub token**
3. Save — Odoo.sh still receives pushes via deploy key + webhook; it just stops posting statuses to GitHub

Optional: on a specific dev branch → Settings → **Test suite** → untick validation (stops `--test-enable` runs; status may still post if token remains).

**Odoo runtime tests (local Docker — not GitHub):**

```bash
make test-odoo              # Docker --test-enable; clones config/test_env_fixture.conf
make test-module m=<module> # same fixture: odoo_test_tpl_ee_c9e8a81f52f23680
```

`make test-module`, `make test-odoo`, and `scripts/test_env.sh` clone only that database. Another test database is not a substitute. A new template is refused unless that database is absent and `TEST_ENV_ALLOW_NEW_TEMPLATE` equals its name. `TEST_ENV_PARITY=community` is refused unless `TEST_ENV_SAFETY_HARNESS=1`.

### Odoo 19 patterns that CI rejects (24 checks in `check_odoo_patterns.sh`)

| # | Pattern | Detection |
|---|---------|-----------|
| 2 | `@api.depends("id")` | grep for `id` in depends list |
| 3 | `@api.one` / `@api.multi` | grep for decorator |
| 4 | `category_id` on `res.groups` | XML grep |
| 5 | `numbercall` on `ir.cron` | XML grep |
| 6 | Unescaped `&` in XML | grep + entity filter |
| 7 | Empty `__init__.py` in modules | file size check |
| 8 | `Plastos*` class name (not `Plasticos*`) | class name grep |
| 9 | Empty inherit files (<5 lines of real code) | line count heuristic |
| 10 | Cron `model_id` ref without module prefix | grep in cron XML |
| 11 | Nested double quotes in XML `eval` | regex match |
| 12 | `<tree>` instead of `<list>` | XML grep |
| 13 | `string=` on `<search>` | XML grep |
| 14 | `string=` on search `<group>` | XML grep |
| 15 | `decoration-secondary=` | XML grep |
| 16 | `t-esc=` (deprecated) | XML grep |
| 17 | Module dependency wiring | delegates to `check_module_wiring.py` |
| 18 | Related fields old intake paths without `_id` | regex |
| 19 | `attrs=` attribute in views | XML grep |
| 20 | `states=` attribute on fields | XML grep |
| 21 | Font Awesome `<i>` without `title=` | XML grep + filter |
| 22 | String writes to Many2one fields | Python grep with exclusions |
| 23 | `x_` prefixed fields | Python grep |
| 24 | `self.env.get("model.name")` anti-pattern | Python grep |

### Known False Positives (excluded from CI)

These files are intentionally excluded from specific checks:

| Check | Excluded | Reason |
|-------|----------|--------|
| Many2one string write (#22) | `ai_normalizer.py` | LLM prompt JSON schema, not field assignment |
| Many2one string write (#22) | `graph_service.py`, `matcher.py`, `enrichment_service.py`, `material_profile.py`, `transaction_import` | Dict/API payloads, not ORM writes |
| `self.env.get()` (#24) | `ci/*.py` | CI detection scripts contain pattern examples |
| mypy | `plasticos_web_leads`, `plasticos_enrichment` | Complex patterns, gradual typing |
| ACL completeness | all modules | Non-blocking hook (warn-only) |
| Odoo patterns script | CI workflows | `|| true` — tracked separately |
| YAML syntax | `plasticos_enrichment/knowledge_base/*.yaml` | Complex YAML not standard Odoo |
| All pre-commit hooks | `odoo-enterprise/**`, `plasticos_graph_*/**` | External/experimental code |
| All pre-commit hooks | `docs/**` | Documentation files |

### Pre-commit Hooks (36 total)

| Hook | Type | Blocking? | What it catches |
|------|------|-----------|-----------------|
| `ruff` | Lint | Yes | Python lint violations (E/W/F/I/B/UP/C90/S/A/FLY/INT/LOG/YTT) |
| `ruff-format` | Format | Yes | Unformatted Python code |
| `check-xml` | Syntax | Yes | Malformed XML |
| `check-yaml` | Syntax | Yes | Malformed YAML |
| `end-of-file-fixer` | Format | Yes | Missing newline at EOF |
| `trailing-whitespace` | Format | Yes | Trailing whitespace |
| `check-added-large-files` | Guard | Yes | Files over 1000 KB |
| `check-merge-conflict` | Guard | Yes | Leftover merge conflict markers |
| `conventional-pre-commit` | Format | Yes (commit-msg stage) | Non-conventional commit messages |
| `odoo-patterns` | Odoo | Yes | 24 Odoo 19 pattern checks |
| `module-wiring` | Odoo | Yes | Manifest deps + `__init__.py` imports |
| `cron-invariants` | Odoo | Yes | Cron safety rules |
| `circular-deps` | Odoo | Yes | Circular module dependencies |
| `orphan-model-refs` | Odoo | Yes | Orphaned model references |
| `package-init` | Odoo | Yes | Package `__init__.py` completeness |
| `xpath-stability` | Odoo | Yes | Fragile XPath expressions |
| `odoo19-hooks` | Odoo | Yes | Odoo 19 hook patterns |
| `odoo19-xml` | Odoo | Yes | Odoo 19 XML deprecations |
| `field-integrity` | Odoo | Yes | Field reference validity |
| `model-inheritance` | Odoo | Yes | Inheritance pattern compliance |
| `orm-integrity` | Odoo | Yes | ORM usage patterns |
| `constraint-patterns` | Odoo | Yes | Constraint style validation |
| `disabled-actions` | Odoo | Yes | Disabled action references |
| `odoo-antipatterns` | Odoo | Yes | Known Odoo anti-patterns |
| `automation-field-refs` | Odoo | Yes | Automation field references |
| `state-guard-bypass` | Odoo | Yes | State guard bypass detection |
| `acl-completeness` | Odoo | **No** | ACL coverage (warn-only) |
| `phantom-enum-values` | Odoo | Yes (pre-push) | `tests/test_phantom_enum_values.py` |
| `manifest-contract` | Odoo | Yes (pre-push) | `tests/test_repo_dependency_integrity.py` (version, resolvable dependencies) |
| `pipeline-v2-guard` | Odoo | Yes | Import fence for pipeline v2 |
| `dev-tools-fence` | Odoo | Yes | Dev tools not imported from production |
| `critical-manifest` | Odoo | Yes | Critical manifest rules |
| `enhanced-audit` | Odoo | Yes | Enhanced code audit |
| `gitleaks-commit` | Security | Yes | Secret scan on staged files (commit stage) |
| `gitleaks-push` | Security | Yes (pre-push) | Full repo secret scan on push |
| `mypy` | Type | **No** | Type checking (excludes many modules) |

Hooks marked "Yes (pre-push)" only run at the `pre-push` git stage, not on every commit — see `.pre-commit-config.yaml` `stages:`.

### Ruff Configuration (from `pyproject.toml`)

| Setting | Value |
|---------|-------|
| Line length | **120** (not 100) |
| Target Python | 3.12 |
| Rules selected | E, W, F, I, B, UP, C90, S, A, FLY, INT, LOG, YTT |
| McCabe max-complexity | 25 |
| Ignored | E501 (formatter), E731 (lambdas), B008 (Odoo field defaults), B905 (zip strict) |
| `__init__.py` exempt from | F401 (unused imports), I001 (import order) |
| `__manifest__.py` exempt from | B018 (bare dict) |
| `test_*.py` exempt from | F841, B011, F821, B017 |

### Audit Baselines (enforced by `ci.yml`'s `audit-baseline` job — separate parallel Phase 1 job, not `static-checks`)

CI diffs each scanner's findings against a **per-finding fingerprint log**
(`ci/baselines/*.json`), not a raw count — see `ci/baselines/README.md` for the
full workflow and `scripts/audit/baseline_utils.py` for the fingerprinting
logic. Any finding not already logged fails the gate, so "count stayed the
same" can never mask "one known issue got fixed, one new one appeared."
Run `make audit-baseline` locally to reproduce.

| Audit | Baseline file | Gated severities | Notes |
|-------|--------------|-------------------|-------|
| `scripts/audit/odoo_audit.py` | `ci/baselines/odoo_audit_baseline.json` | CRITICAL, HIGH | 444x `FIELD_NOT_FOUND` (CRITICAL) — script misattributes `ir.ui.view`/`ir.actions.act_window` container fields (`arch`, `inherit_id`, `name`, `view_mode`, `res_model`, `context`, `help`, `search_view_id`, `target`, `priority`) as fields of the model the view displays; 1x `INVALID_CONSTRAINT_FIELD` (HIGH) on `plasticos_transaction/models/transaction.py` (`commission_override_pct`) — field is added via cross-module `_inherit` from `plasticos_commission`, the single-file scanner can't see it |
| `scripts/audit/run_all_audits.py` | `ci/baselines/extended_audit_baseline.json` | HIGH | 9x `N_PLUS_ONE_QUERY` (`transaction.py`, `purchase_inherit.py`, `load.py` x3, `facility_profile.py` x2, `intake_extension.py`, `commission_rule.py`) — real pattern, accepted as low-impact debt (small recordsets); 6x `SENSITIVE_DATA_LOGGED` keyword false positives on "token"/"api_key" substrings in log messages (`pr_autopilot.py`, `pr_check_remote_feedback.py`, `web_leads` post-migrate) — none log actual secret values |
| XPath CRITICAL | — (count-based, unchanged) | — | 0 — no new CRITICAL XPath issues allowed |
| XPath HIGH | — (count-based, unchanged) | — | 0 — no new HIGH XPath issues allowed |

To log a newly-reviewed false positive or accepted-debt finding (never edit the
scanner scripts to special-case it): `python3 scripts/audit/check_baseline.py
<report.json> <baseline.json> --severities ... --dump-new`, review the printed
entries, then merge them into the baseline file's `entries` array. Full
workflow: `ci/baselines/README.md`.

### Version Lockstep

| Tool | Pre-commit | CI (`ci.yml`) | Local (`make venv` / `requirements-dev.txt`) | `pyproject.toml` |
|------|-----------|--------------|------------------------------------------------|-------------------|
| Ruff | `v0.16.0` | `0.16.0` | `make venv` pins `ruff==0.16.0` explicitly | `required-version = "==0.16.0"` (hard-fails on any drift — this is the enforcement mechanism, not a lockfile) |
| mypy | `v1.14.0` | `1.14.0` | `requirements-dev.txt` pins `mypy==1.14.0` | `[tool.mypy]` config (no version field — mypy has no `required-version` equivalent) |
| Semgrep | n/a (not a hook) | `1.164.0` | `make venv` pins `semgrep==1.164.0` explicitly | n/a |
| pytest | n/a (not a hook) | `8.3.5` / `pytest-timeout==2.4.0` / `pytest-cov==5.0.0` | `requirements-dev.txt` — same three pins | `[tool.pytest.ini_options]` |
| gitleaks | pre-commit hook (`gitleaks-commit`/`gitleaks-push`, unpinned local binary) | SHA-pinned action (`gitleaks/gitleaks-action@ff98106e...`, tag `v2`) | local `gitleaks` binary version, unpinned | n/a |
| shellcheck | not yet a pre-commit hook | unpinned (`apt-get install -y shellcheck` = whatever Ubuntu ships) | unpinned (`brew install shellcheck`) | n/a |

Ruff is the only tool with a **hard version gate** (`required-version` in `pyproject.toml` — this is
what caught the drift on 2026-07: a global `ruff==0.14.11` on PATH refused to run against a repo
then pinned to `0.15.5`). The live pin is `0.16.0` in this table, `.pre-commit-config.yaml` (`v0.16.0`),
`ci.yml`, and `requirements-dev.txt`. This repo intentionally has **no `uv.lock`** — see
`.cursor/rules/88-plasticos-odoo-python-tooling.mdc` "Non-goals": there's no `[project]` table in
`pyproject.toml` because this is an Odoo addon suite, not a pip/uv-installable package. The
equivalent of a lockfile here is **pins repeated at each of the three sites above** (pre-commit,
CI, local `requirements-dev.txt`/`make venv`), kept in lockstep manually. Bump a tool by updating
all applicable cells in one PR; `make venv` and `pre-commit autoupdate` regenerate the local/hook
pins, `pyproject.toml`'s `required-version` (Ruff only) is what actually blocks a stale local tool
from running silently. Always run `pre-commit run --all-files` locally before pushing.

## Boundaries

### ✅ Always
- Use `plasticos_` prefix for all module/model/external ID names
- Add `security/ir.model.access.csv` for every new model
- Use `sanitize_label()` patterns — no f-string SQL/Cypher
- Declare dependencies in `__manifest__.py` before importing
- Stable reference data may use `noupdate="1"` with external IDs. Views and records that must refresh on upgrade do not.
- Run `python3 scripts/check_module_wiring.py` before commit
- Keep PlasticOS skills under `skills/` (repo law: `skills/PLASTICOS_CANONICAL_LAW.md`); run `make check-plasticos-skills` when adding or moving skills

### ⚠️ Ask First
- Adding new modules (affects dependency graph and install order)
- Modifying `plasticos_base` (affects all downstream modules)
- Changing security groups or record rules
- Adding new `ir.cron` scheduled actions
- Neo4j integration changes (graph boundary rules apply)
- Gate / CEG / EIE integration (follow `docs/adr/ADR-003-single-external-intelligence-authority.md`, ADR-002 topology, ADR-009–018 convergence set, and `docs/GATE_AUTONOMY_ROADMAP.md`)
- Schema changes to `res.partner` (partner model constraints)

### 🚫 Never
- Use `_sql_constraints` → use `models.Constraint` (Odoo 19)
- Use `@api.depends("id")` → remove "id" from depends
- Use `@api.one` / `@api.multi` → removed in Odoo 13
- Use `category_id` on `res.groups` → removed in Odoo 19
- Use `numbercall` on `ir.cron` → deprecated
- Create circular dependencies between modules
- Import Neo4j in Odoo registry load path
- Block Odoo startup on Neo4j connection
- Hardcode database IDs → use external IDs
- Bootstrap data via CSV at runtime → use XML seed data
- Use `sudo()` without explicit justification
- Create custom partner role booleans → use native `customer_rank`/`supplier_rank`
- Commit test data to production seed files
- Attach material profiles directly to `res.partner` → use `plasticos.facility.profile`
- Call CEG/EIE directly from Odoo → route through Gate (`constellation_node_sdk`; see ADR-003-single + ADR-002)
- Treat local matcher/enrichment engines as architectural intelligence authority (ADR-003-single; mothball M1–M8 sealed — use `make no-local-intelligence` / `ci/check_no_local_intelligence.py`; M8 guards are **blocking** in CI/pre-commit)
- Apply Gate web-lead triage in Phase 1 (see GATE_AUTONOMY_ROADMAP.md) — triage stays Odoo-local until Phase 3
- Overwrite `docs/adr/ADR-003-contact-import-configuration.md` when editing the mothball ADR-003-single file (filename collision)

<!-- BEGIN L9 FORMATTER OWNERSHIP (generated — do not edit) -->

## Formatter ownership

Workspace class: `biome_default` — Default for every governed workspace: Biome owns JS/TS/JSON, VS Code JSON language features owns JSONC (the Biome extension cannot format jsonc), Ruff owns Python, Prettier owns Markdown (format-on-save off so governance docs do not churn).

Exactly one formatter owns each language. Do not reformat a file with a tool other than its owner, and do not add config for a competing formatter: the result is a diff that churns on every save.

| Languages | Owner | Note |
|---|---|---|
| `javascript`, `javascriptreact`, `typescript`, `typescriptreact`, `json` | **biome** | bound by the governed IDE profile |
| `jsonc` | **vscode-json** | bound by the governed IDE profile |
| `python` | **ruff** | bound by the governed IDE profile |
| `markdown` | **prettier** | bound by the governed IDE profile |

Generated from `environment/ide/policy.json` in the governance clone by `ops/scripts/adapters/agentdocs.sh`. Edit the policy, not this block.

<!-- END L9 FORMATTER OWNERSHIP -->

> **2026-10-06 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the `make import-legacy-erp` line in the Commands block above is superseded. The canonical ERP import
> command is **`make import-erp`** (`plasticos_partner_import/scripts/import_erp_shell.py`, driven by
> `plasticos_partner_import/models/erp_import_service.py`). ERP data enters through SQL (ADR-021): set
> `ERP_SQL_SERVER` / `ERP_SQL_DATABASE` (plus `ERP_SQL_USER` / `ERP_SQL_PASSWORD`, or `ERP_SQL_DRIVER=pyodbc`)
> for a direct read of the restored source database; the frozen grid extract under
> `plasticos_partner_import/erp_extracted_data/bulk/` is a regression fixture, not runtime authority.
> `PARTNERS_ONLY=1` runs Concern 1 (counterparties → addresses → contacts → roles → salespersons) with
> each layer validated before anything commits. Runbook: `docs/runbooks/ERP_IMPORT.md`.

> **2026-10-07 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> Publication override: `make pr` is the sole publication SSOT.
> `make push` and `make push pr=1` are retired and must not be used for publication.
> The Commands block above that names those ceremonies is historical and is superseded by this correction.
> A failed remote-feedback gate must be resolved before `make pr`.

> **2026-10-17 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> Enterprise Docker runtime tests (`make test-module`, `make test-odoo`, `scripts/test_env.sh`)
> clone only the database named in `config/test_env_fixture.conf`
> (`odoo_test_tpl_ee_c9e8a81f52f23680`). Another test database is not a substitute.
> A new template is refused unless that database is absent and `TEST_ENV_ALLOW_NEW_TEMPLATE`
> equals that name. `TEST_ENV_PARITY=community` is refused unless `TEST_ENV_SAFETY_HARNESS=1`.
> Rule: `.cursor/rules/36-plasticos-docker-test-fixture.mdc`.

> **2026-10-18 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> `make pr` remains the only publication command. `make commit` does not ask to launch it.
> A feature-branch SHA is validated by the pull_request CI event. Pushes to `Staging` and
> `Production` are validated by the push event. `workflow_dispatch` remains for the repo-index bot.

> **2026-10-18 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> The Project Structure line for `plasticos_documents_native` names it only as the Enterprise Documents bridge.
> That bridge is `installable: True`, `application: True`, and `auto_install: True`. Odoo installs it when Enterprise
> `documents`, `documents_account`, and its PlasticOS dependencies are installed.
> `plasticos_semantic_kernel` is optional (`auto_install: False`) and stays uninstalled. No module depends on it.
> Do not add `plasticos_semantic_kernel` to any `depends` list.

> **2026-10-21 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the `l9-gmp-protocol` row in the Agent Skills table above is retired. Cursor-Governance removed
> `skills/l9-gmp-protocol` (PR #744, merged 2026-10-21); the tracked projection `.claude/skills/l9-gmp-protocol`,
> its `.l9-managed-skills.json` entry and its `.claude/README.md` row were removed with it. Deterministic phased
> GMP execution is the `/gmp` slash command, which runs the governance executor against this clone:
> `"$GOV_PY" "$GOV/workflows/gmp_executor.py" --workspace "$(git rev-parse --show-toplevel)" …`
> (`commands/gmp.md` in Cursor-Governance). Do not re-add the skill symlink.

> **2026-10-21 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the Repo Index block above that names `reports/repo-index/` is superseded.
> Lookup indexes live at `docs/reports/repo-index/`. Regenerate them with
> `python3 scripts/repo_generators/export_repo_indexes.py`.
> Do not create a root `reports/` directory. The global `l9-repo-index` skill's
> default output path does not apply in this repo. The line that says no
> repo-local generator exists is also superseded: the generator is
> `scripts/repo_generators/export_repo_indexes.py`.

> **2026-10-21 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> GMP execution reports are saved in `docs/reports/gmp-reports/` and committed.
> Do not write them to a root `reports/` directory, do not scatter them, and do not
> finish a GMP without saving the report. `docs/GATE_AUTONOMY_ROADMAP.md` moved to
> `docs/roadmap/GATE_AUTONOMY_ROADMAP.md`.

> **2026-10-21 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the `make roadmap` and `make roadmap-list` commands above, and the generated Gate
> autonomy document they named, are retired. Do not restore that generator.
> `docs/roadmap/` is hand-authored strategic planning; no script may write it.
> Phase criteria are ADR-002 §3, ADR-016, and ADR-018. Web-lead triage stays in
> Odoo until an ADR amendment.

> **2026-10-21 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> `docs/runbooks/ERP_IMPORT.md` does not exist. The ERP import contract is
> ADR-021 and `plasticos_partner_import` (`erp/mapping.py`, `erp/mapping_status.py`,
> `erp/reader.py`). The unadopted `docs/runbooks/erp_sync_mapping_matrix/` proposal
> was removed. Do not restore it.

> **2026-10-21 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> `memory-bank/` is retired. Do not recreate it. Session resume is Graphiti
> (`https://github.com/Quantum-L9/l9-graphiti-memory`). Current operational
> state is `workflow_state.md`. Code debt stays in `docs/campaigns/odoo_tech_debt`.

> **2026-10-21 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the sentence above that says `docs/GATE_AUTONOMY_ROADMAP.md` moved to
> `docs/roadmap/GATE_AUTONOMY_ROADMAP.md` is superseded. That generated file
> was deleted. `docs/roadmap/` was emptied on purpose, including `README.md`.
> `docs/erp_extract_research.md` is removed with the retired `data/erp_sm_export/`
> probe. SQL authority is `plasticos_partner_import/erp_extracted_data/` and
> `erp/reader.py`. `docs/runbooks/` is removed. The CI contract note lives at
> `docs/reports/CI_CONTRACT_ASSURANCE.md`.

> **2026-10-22 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the GATE-01 Baseline Ratchet is retired. `.github/workflows/baseline-ratchet.yml` and its two
> ledgers under `.l9/baselines/` were removed. Every sentence above that names `baseline-ratchet.yml`,
> "Baseline Ratchet", or `Ratchet Verdict` as a CI gate is superseded. On each PR push, **CI Gate** and
> **L9 Analysis** start together; `CI Gate Result` is the merge aggregator. The `audit-baseline` job in
> `ci.yml` (`ci/baselines/*.json`) is separate and unchanged. Do not re-add the ratchet caller.

> **2026-10-22 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> `make pr-check` (and therefore `make pr`) runs only what the branch changed can reach. `scripts/pr_check_scope.py`
> compares the branch with `origin/Staging` (committed range, working tree, untracked files) and decides once:
> `audit` + `audit-baseline` run when any non-documentation path changed; pytest runs only the test modules
> touched by, or reading, the changed paths (`make test-scoped`; the whole suite when `tests/conftest.py`,
> `tests/common.py`, `pyproject.toml` or requirements changed); the Docker install-smoke (and its post-gate
> `--recheck`) runs only when an addon load input or an installer input changed. A documentation-only branch
> publishes with no collector and no Docker. Every doubt (no base, no change, a scope failure) keeps the whole
> gate, as does `PR_CHECK_SCOPE=full`. Receipt: `.cache/pr-check/scope.json`. `make test` and GitHub `ci.yml`
> still run the whole suite; `ci.yml` stays the merge verdict. `make pr-nosmoke` is unchanged.

> **2026-10-23 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> these Agent Skills rows are retired. Cursor-Governance archived the packs out of live `skills/` discovery: `l9-governance-wiring`, `l9-harvest-pipeline`, `l9-inspect`, `l9-plan`, `l9-pr-analysis`, `l9-update-command`, and `l9-wire-skill-into-repo`. The tracked projections `.claude/skills/<name>`, their `.l9-managed-skills.json` entries, and their `.claude/README.md` rows were removed, as with the 2026-10-21 `l9-gmp-protocol` removal. Replacements: `l9-governance-wiring` → `l9-wire-into-repo` and `l9-governance-symlinks`; `l9-harvest-pipeline` → `/harvest` and `/use-harvest`; `l9-inspect` → `/inspect`; `l9-plan` → `l9-plan-simple` for ordinary plans (program-execution planning has no live owner); `l9-pr-analysis` → `l9-pr-remediation`; `l9-update-command` → `l9-dag-authoring`; `l9-wire-skill-into-repo` → `l9-wire-into-repo`. Do not re-add the skill symlinks.

> **2026-11-03 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the 2026-10-21 sentence "Code debt stays in `docs/campaigns/odoo_tech_debt`" is superseded. PR #355 retired
> that tracker (`00_README.md`, `OPEN_REGISTER.json`, `OPEN_REGISTER.md`, `_build_register.py`), and no
> repository debt tracker replaces it. `workflow_state.md` remains the operational state of open campaigns.
> `docs/erp_import_mapping.md` stays: it is the ERP import mapping authority cited by
> `plasticos_partner_import/erp/mapping_status.py`, ADR-022 and the source-layer tests.

> **2026-10-30 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the Never line "Attach material profiles directly to `res.partner` → use `plasticos.facility.profile`" is superseded
> by operator decision 2026-10-30. A material profile belongs to a partner. No facility profile is required.
> The VanillaSoft import puts an approved contact's materials on its resolved facility partner. When that site
> cannot be resolved, they go on the matched ERP contact person. A facility profile is used only when exactly one
> already exists for that partner.

> **2026-11-03 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the "36 hooks" counts above (Commands block and the Pre-commit Hooks table heading) are superseded:
> `.pre-commit-config.yaml` declares **39** hooks and `default_stages: [pre-commit]`. The pre-push stage is
> 10 hooks: `check-xml`, `check-yaml`, `end-of-file-fixer`, `trailing-whitespace`, `check-added-large-files`,
> `check-merge-conflict`, `phantom-enum-values`, `manifest-contract`, `gitleaks-push`, and `pr-validate`.
> The 23 whole-tree Odoo scanners in the table are commit-stage hooks only. All 23 still run inside `make pr-check`
> (`make audit`, including `scripts/run_audit_integrity.sh`), but no longer a second time at push. 20 of them also
> run in `ci.yml` (`cron-invariants` through `tests/test_cron_invariants.py`); `constraint-patterns`,
> `disabled-actions`, and `automation-field-refs` do not, so `ci.yml` does not re-check those three.
> `make pr` (`scripts/git_push_with_pr.sh`)
> owns an unconditional gate on every attempt (gitleaks, smoke resolve, `make pr-check`, smoke recheck), then a
> second L4 check immediately before `git push`. Its push alone carries a binding that `scripts/pre_push_validate.sh`
> honours only for that exact SHA, clean `HEAD`, `origin`, and target branch, and only when `L9_PUBLISH_PID` names a
> live ancestor whose argv[0] or argv[1] is `scripts/git_push_with_pr.sh` (unreadable ancestry fails closed), so
> each attempt validates once. Every other push, including a direct `git push` that sets the binding variables
> itself, runs the full gate in the hook. A direct `git push` is validated but is not publication
> (no L4, no PR). Supported push forms and the threat model are in `docs/reports/make-pr-validation-consolidation.md`.

> **2026-11-04 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> `make pr base=<branch>` stacks onto an open feature branch whose pull request targets `Staging`.
> Production stays refused. Merge the parent pull request into `Staging` first.

> **2026-11-04 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> `make install-smoke`, and the smoke wave inside `make pr` / `make pr-check`, clone the database named in
> `config/test_env_fixture.conf` and upgrade the PlasticOS roster on that clone. They do not drop
> `odoo_install_smoke` or install from an empty database. The from-empty install remains
> `scripts/test_env.sh template`, which runs on first admission and on `make test-env-rebuild`.
> `make test-env-rebuild` is the operator recovery when the image, Postgres major, module roster,
> configuration, or Enterprise checkout no longer matches the admitted template. It refuses when that
> template is already admitted for the current inputs. Do not set `TEST_ENV_ALLOW_NEW_TEMPLATE` by hand.
> Smoke runs when `scripts/pr_check_scope.py` says an addon load input or an installer input changed.
> A documentation-only scope, `PR_CHECK_SKIP_SMOKE=1`, and `make pr-nosmoke reason=...` still skip it.
> `INSTALL_SMOKE_GATE` is no longer required. `l9-pr-integration-testing` in this repo uses the same
> fixture: `scripts/test_env.sh clone` and `scripts/test_env.sh run` on the host compose stack.
> Another database and the toolchain-image quick path are not an Odoo runtime result here.
> An unproven fixture stops at `make test-env-rebuild`.

> **2026-11-05 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the 2026-10-22 sentence that local pytest runs every test module touched by, or reading, the changed
> paths is superseded for the local gate. `scripts/pr_check_scope.py` selects a changed `tests/test_*.py`
> module and a test module whose source contains the changed repo-relative path, that path with its suffix
> removed, or, for Python, the dotted module. A bare filename stem, an addon directory name, a quoted
> top-level directory, and a `plasticos_*` tree walk do not select a test. Harness files, `PR_CHECK_SCOPE=full`,
> an empty diff, an unknown base, and a scope-script failure still select the whole local suite.
> `.github/workflows/ci.yml` still runs `pytest tests/` and stays the merge verdict.

> **2026-11-05 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the commercial pursuit owner is the native `crm.lead` Opportunity (`type = opportunity`), and Facility is optional.
> HOT web leads, manual Partner + Material Profile entry, and VanillaSoft contacts converge on one matching command,
> `crm.lead.action_match_opportunity`, which mints an immutable `plasticos.opportunity.approval` lot (frozen material
> snapshot, verified Partner, optional Facility, optional source Intake) and runs the one Gate orchestrator
> (`plasticos.match.orchestrator.run_match_for_lot`). No synthetic Intake or Facility is created on that route;
> absent facility evidence is omitted from the Gate request, never fabricated. Lineage is owned by
> `plasticos_crm_bridge` (`plasticos.match.run.opportunity_id` / `approval_id`, `plasticos.offer.match_result_id`),
> which now depends on `plasticos_matching` and `plasticos_offer`; Matching does not depend on CRM Bridge.
> `plasticos.match.run.intake_id`, `plasticos.match.result.intake_id` and `plasticos.offer.intake_id` are optional
> with `ondelete="restrict"`; historical rows keep null lineage and are not backfilled. Partial unique indexes:
> one Opportunity per source Intake, one result per buyer per Gate operation, one offer per reviewed result.
> Reviewed (accepted) results create idempotent unsent draft offers (`action_create_offers_from_results`); a Gate
> match carries no price authority, offer terms freeze once sent, and exactly one offer per Opportunity may be
> accepted. Acceptance creates or reuses one draft `sale.order` bound by native `sale.order.opportunity_id`
> (`sale_crm`; the hand-off stops when the field is missing) and leaves confirmation to the existing transaction
> compiler (`sale.order.action_confirm`). `plasticos.intake.action_send_offers` and the typical-price autofill are
> retired as offer-creation authority. Partner and Material Profile "Create Intake" actions open a native
> Opportunity when CRM Bridge is installed.

> **2026-11-06 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> Odoo runtime tests (`make test-module` / `make test-odoo`) have two owners and no third. (1) The Docker smoke
> stage of `make pr-check` (`scripts/pr_check_run.sh`) runs `make runtime-test` after install-smoke for the
> `runtime=` modules `scripts/pr_check_scope.py` names: declared roster modules the branch touched that ship a
> `tests/` package, or `all` when the whole gate is kept. `make pr-nosmoke reason=...` and `PR_CHECK_SKIP_SMOKE=1`
> skip it with install-smoke; a documentation-, script- or harness-only branch reaches no module; a scope of
> `smoke=0` does not skip it, so a change to an addon's own tests still runs them. (2) `l9-pr-integration-testing`,
> only when the operator invokes it, runs `make runtime-test m=<modules>` on the host compose stack.
> `make runtime-test` dispatches to the unchanged `test-module` / `test-odoo` recipes. Agents do not run
> `make test-module` or `make test-odoo` ad hoc; the lines above that list them as commands are superseded.
> `tests/test_runtime_test_ownership.py` enforces this.

> **2026-11-05 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the Audit Baselines table above is superseded on both rows. `ci/baselines/odoo_audit_baseline.json` has no
> entries: `scripts/audit/odoo_audit.py` resolves `@api.depends` fields from its AST model index (a class belongs
> to its `_name` or single `_inherit`; fields come from every class of that model in the module's depends closure),
> so the `document_ids` false positive no longer exists. `ci/baselines/extended_audit_baseline.json` has one
> entry, a reviewed `REAL_ACCEPT` on `plasticos_enrichment/models/enrichment_run.py` (per-identity profile create
> inside `action_inject`); the other 47 `N_PLUS_ONE_QUERY` rows accepted on 2026-10-10 were repaired or, for the
> `plasticos_documents_native` keyset pagination, recognised by `scripts/audit/performance_audit.py` as one query
> per page. Every baseline entry carries a `review:` reason. `make audit-baseline` still proves new 0; prune a
> fixed line's entry in the same change, since its fingerprint includes the flagged source line.

> **2026-11-06 enrichment baseline correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the 2026-11-05 sentence that `ci/baselines/extended_audit_baseline.json` has one `REAL_ACCEPT` entry on
> `plasticos_enrichment/models/enrichment_run.py` is superseded. `action_inject` creates new material profiles
> once after the raw-material walk, and fingerprint `13881d09c66d6989` is pruned. The extended baseline
> `entries` array is empty.

> **2026-11-08 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the local pytest wave inside `make pr` / `make pr-check` / the pre-push gate is retired.
> `scripts/pr_check_run.sh` full mode does not run `make test` or `make test-scoped`.
> `ci.yml` `pure-python-tests` still runs `pytest tests/` and stays the merge verdict.
> `make test` remains the manual suite. The two pre-push contract hooks
> (`phantom-enum-values`, `manifest-contract`) are unchanged.

> **2026-11-10 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> `make import-vanillasoft` writes only the Odoo.sh production database (operator decision 2026-11-10, PR #424).
> It pipes `plasticos_crm_sync/scripts/import_vanillasoft_shell.py` into `odoo-bin shell` over SSH
> (`ODOO_SH_PRODUCTION_SSH` or `.env.local`), runs under bash, and refuses inside a test-env clone
> (`TEST_ENV_VERIFIED_CLONE`). It has no Docker or local-runner path. The repository cohort
> (`VANILLASOFT_CONTACT_EXPORT` + `VANILLASOFT_PRODUCTION_CONFIRM=1`) is its third mode. The
> `plasticos-branch-promotion-rehearsal` row above is superseded for VanillaSoft: the rehearsal covers
> `import-erp` only, and `import-vanillasoft` is not rehearsed on a clone.

> **2026-11-10 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> `make pr` composes every pull request with the SSOT injector, the Cursor-Governance composer
> (`ops/scripts/compose_pr_body.py`) that SSOT `make pr` runs for every L9 repository. `scripts/git_open_pr.sh`
> calls it directly (`ssot_compose`) with the flags `open_pr_after_gate.sh` passes. The only difference is the template
> owner: `Quantum-L9` instead of the repo owner, because `cryptoxdog` has no `.github` template (`PR_TEMPLATE_OWNER`
> overrides). The body lists every touched file first (`## Files touched`). `.github/pull_request_template.md` is a
> byte copy of the `Quantum-L9/.github` template for PRs opened in the GitHub web page; the composer never reads it.
> The local body builder `scripts/build_pr_body.py` and its test are removed. `make_push_pipeline.sh` proves the org
> template is readable before any push. On an open PR, `make pr` refreshes only the composer's machine-owned regions.
> `.l9/pr/pr-intent.json` (`l9.pr_intent.v1`) supplies title and prose when its `head` names HEAD; `.l9/pr/` is
> gitignored. Install-smoke: a Claude Code cloud session (`CLAUDE_CODE_REMOTE=true`) skips it by default and says so
> on the PR; Cursor and a local terminal run it; `PR_SMOKE=1` forces it; `make pr-nosmoke reason=...` still wins.

> **2026-11-10 session-friction correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> `make runtime-bootstrap` (`scripts/runtime_bootstrap.sh`) prepares a machine with Docker, a cloud agent
> session included, for the Odoo Enterprise runtime gate. It binds an Enterprise checkout (`ODOO_ENTERPRISE_PATH`,
> `./odoo-enterprise`, a sibling `../odoo-enterprise`, or a shallow clone of `ODOO_ENTERPRISE_REPO` at
> `ODOO_ENTERPRISE_REF`, default its default branch such as `main`; the Odoo series is checked as 19.0) and admits the pinned fixture through `scripts/test_env.sh rebuild` only
> when that database is absent. A fixture that exists but is not admitted stays an operator decision
> (`make test-env-rebuild`). It runs no Odoo tests, and the two runtime-test owners are unchanged. Once it
> succeeds, `PR_SMOKE=1 make pr` in that session runs the install-smoke and the runtime tests (a cloud session
> skips them by default, per the correction above). Operator one-time setup (a private copy of the Enterprise 19.0
> source): `docs/LOCAL_DEV_SETUP.md`, "Cloud agent sessions".
> `.pre-commit-config.yaml` now declares 40 hooks; the pre-push set is unchanged. The commit-stage hook
> `readme-module-version` (`scripts/sync_readme_module_version.py`) rewrites a module README's `module_version`
> front matter when that module's `__manifest__.py` version is staged: stage the README it names and commit
> again. `check-merge-conflict` runs with `--assume-in-merge`, so a stray conflict marker fails outside a merge
> too; the leftover marker in this file was removed on 2026-11-10.

> **2026-11-10 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> `plasticos_screen_views` (`19.0.1.0.0`, `auto_install`) turns the installed view engines on for Contacts and Web
> Leads. It depends on `contacts`, `mail`, `web_hierarchy`, `web_map`, and `plasticos_web_leads`. Contacts gain map
> and hierarchy. Web Leads open on the list and gain calendar, pivot, graph, map, and activity. CRM views stay in
> `crm_enterprise`. The module is in `config/odoo_module_order.yaml` immediately after `plasticos_web_leads`.

> **2026-11-10 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> `plasticos_screen_views` also depends on `contacts_enterprise`. That module already pins the Contacts map
> (`res_partner="id"`), so this module does not add a second map binding. It adds the hierarchy view and lists
> `map` on the contacts action. `web_hierarchy`, `web_map`, and `contacts_enterprise` are known Odoo addons in
> `tests/test_repo_dependency_integrity.py`.

> **2026-11-10 pull-request integration correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> Combined open-PR integration in this repository is `plasticos-pr-integration` (`skills/plasticos-pr-integration/`).
> It merges the fetched heads onto current `Staging` in a disposable worktree and runs `make install-smoke`
> on the pinned Enterprise fixture. It does not edit the governance `l9-pr-integration-testing` pack.
> The two runtime-test owners recorded on 2026-11-06 are unchanged: the `make pr-check` smoke stage, and
> `make runtime-test m=<modules>` when an integration skill is invoked. Do not run `make test-module` or
> `make test-odoo` ad hoc.

> **2026-11-11 PlasticOS Export task read path (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> before changing a load's company or parent, container journeys (J1 `plasticos.iso.journey`, J2
> `plasticos.iso.journey.source`), the physical-release guard, actual pickup/delivery clocks or the manual freight
> context, read `docs/adr/ADR-130-export-physical-evidence-and-owner-contracts.md`, the 2026-11-11 section of
> `plasticos_logistics/business_rules/SUPERSESSION.md`, and the Export campaign pack
> `docs/campaigns/future-add-ons/PlasticOS_Export/` (`STRATEGIC_EXECUTION_PLAN_v2.8.md`, BRS-EXP-01..14). The
> `plasticos_export` addon and its README do not exist yet (slice S5); until then the campaign pack is the Export
> source. `plasticos.load.company_id` is an explicit source company (never `env.company`); one transaction owns many
> loads through `plasticos.load.transaction_id`. Addon census at Staging `08504e12`: **31** `plasticos_*` addons,
> **29** installable and 2 not installable (`plasticos_dev_tools`, `plasticos_website`); this supersedes the 30/28
> count in Project Overview.

> **2026-11-13 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> `make import-erp-material-profiles` (`DRY=1` rolls back) puts `plasticos.material.profile` records on the exact ERP
> site partner named by two private operator files (`ERP_PROFILE_SUPPLIERS`, `ERP_PROFILE_CUSTOMERS`; defaults are the
> gitignored `plasticos_material_profile/data/ERP-Material-Profiles-Suppliers.csv` and `-Customers.csv`). Both files are
> one list; supplier versus customer carries no meaning. The only product map is
> `plasticos_material_profile/data/ERP-Products.csv`, read by `material_normalizer.normalize_erp_product`; the phrase
> sheet `material_mapping.csv` stays the VanillaSoft/CRM map and is unchanged. The loader is
> `plasticos.erp.material.profile.loader` in `plasticos_transaction`, driven by
> `plasticos_transaction/scripts/load_erp_material_profiles_shell.py`. The partner is the ERP site child
> (`legacy_erp_address_<AddressID>`) whose `erp_address_label` equals the ship value, or the company
> (`legacy_erp_cp_<CpID>`) when it has no ERP site children. Every other case is rejected with a reason and writes
> nothing. Run it after the ERP partner import. It adds no field and no stored model, and it refuses a production database.
> Summary: `.l9/pr/import-erp-material-profiles-summary.json`
> (`records_seen == created + updated + unchanged + rejected`). Never commit the two operator files.

> **2026-11-13 loader review correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> two sentences of the `make import-erp-material-profiles` correction above are made precise. (1) The database check
> also runs on a dry run (`DRY=1`): a production database is refused for dry and applied runs alike. (2) One load runs
> at a time on a database; a second run started meanwhile is refused and does not wait. The phrase sheet
> `material_mapping.csv` is unchanged by the loader, and the ERP order-line import
> (`plasticos_transaction/models/native_document_import.py`) still classifies order lines through that sheet.

> **2026-11-17 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the 2026-10-30 sentence "When that site cannot be resolved, they go on the matched ERP contact person." is
> superseded by `docs/adr/ADR-132-material-profile-belongs-to-the-site.md`. A material profile never lands on a person.
> It goes on the lead's site; else the person's one linked site; else, among several linked sites, the one whose
> address matches the source record (zip, else city and street). If none matches, nothing is stored and the record is
> reported. A person whose company has no sites puts it on that company. VanillaSoft Material Type sets `source_type_id`
> and Material Form sets `form_id`. One value applies to every profile of the record, and several values are ignored and
> reported. Only an empty field is filled. Bales (any packaging type) sets `packaging_type_id`, never `form_id`.
> Which VanillaSoft records become partners is `docs/adr/ADR-133-vanillasoft-records-become-partners-selectively.md`.

> **2026-11-17 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the 2026-11-13 sentence "Both files are one list; supplier versus customer carries no meaning." is superseded.
> `make import-erp-material-profiles` writes `direction` from the file: the supplier list is `out` and the customer
> list is `in`. The same product at one site from both lists is two profiles. A replay of the same files changes
> nothing. VanillaSoft writes `out` for Supplier and `in` for Buyer. A record that is both is set per material when
> the site decides (a pickup address is out); otherwise the direction stays blank and the record is listed under
> NEEDS REVIEW. A material-profile write on the AI broker path (`plasticos_ai_broker`) with no direction is refused
> and reported. Enrichment writes no material profiles.

> **2026-11-19 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> every sentence above that says GitHub `ci.yml` `pure-python-tests` runs `pytest tests/` on a pull request or
> push is superseded. That job is the PR-fast lane: `PLASTICOS_CI_TIER=pr_fast` runs every `adversarial_contract`
> test and, when the committed diff proves them, structurally selected non-marker modules. Unknown scope fails
> the job. Unfiltered `pytest tests/` runs only from `.github/workflows/nightly-full-python.yml` (cron
> `17 7 * * *` UTC and manual dispatch, `refs/heads/Staging` only). The nightly job name is `Nightly Full Python
> Suite`. It is the Odoo-free suite, not the Odoo ORM/`TransactionCase` runtime. Required check names stay
> `Ruff Lint & Format`, `Static Analysis`, `Pure Python Tests`, and `CI Gate Result`. `make test` remains the
> local full Odoo-free suite. `gate-sdk-tests` and `audit-baseline` stay on every pull request.

> **2026-11-20 correction (additive; this file is append-only under `ops/config/root-file-protection.json`):**
> the Version Lockstep table above is superseded. Tool versions follow Core's toolchain lock
> (`Quantum-L9/l9-ci-core` `.github/actions/install-consumer-ci/toolchain-lock.json`, operator decision
> 2026-11-20). `ci/core-toolchain-lock.json` is a byte copy of that file, with its Core commit in
> `ci/core-toolchain-lock.provenance.json`; it is this repository's single source for tool versions. Live pins:
> ruff `0.16.1`, mypy `2.3.0`, pytest `9.1.1`, semgrep `1.171.0`, pre-commit `4.4.0`, pip `26.2.1`,
> gitleaks `8.24.3` (`GITLEAKS_VERSION` on `gitleaks/gitleaks-action` in `ci.yml`), Python `3.12`. They are
> repeated at each install site (`ci.yml`, `nightly-full-python.yml`, `l9-analysis.yml`, `requirements-dev.txt`,
> `requirements-ci.txt`, `make venv`, `make lock-deps`, the `ruff-pre-commit` and `mirrors-mypy` revs, and
> `pyproject.toml` `required-version`), because this addon suite has no `[project]` table and no `uv.lock`.
> `tests/test_core_toolchain_pins.py` fails on any site that differs from the copy or installs a lock-owned tool
> unpinned. Bump a tool by refreshing the copy from Core, recording the commit, and following the test.
> The repository has no `dependabot.yml`, so nothing here bumps a lock-owned tool.
