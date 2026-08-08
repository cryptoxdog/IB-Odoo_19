# AGENTS.md — PlasticOS (Odoo 19)

Cross-tool agent instructions for the IB-Odoo_19 repository. Read by Claude Code, Codex, Cursor, Copilot, Jules, Aider, CodeRabbit, and all AGENTS.md-compatible tools.

## Project Overview

- **Name**: PlasticOS — Plastics Recycling Brokerage ERP
- **Type**: Odoo 19 custom module suite (**30** `plasticos_*` addons — **28** installable, 2 dev/non-installable; **~33K** lines Python in addons, **~174** XML files in addons).
- **Stage**: Production (`Staging` branch → `Production`)
- **Stack**: Python 3.12, Odoo 19, PostgreSQL 16, Neo4j (graph scoring), Docker

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
#   Skip remote: PR_CHECK_SKIP_REMOTE=1 make push

# Push (safe: pr-check first, then push feature branch; use pr=1 to open PR into Staging)
make push                                 # pr-check then push current branch
make push pr=1                            # push, then open PR into Staging

# Docker
docker-compose up -d                      # Start Odoo + PostgreSQL + Redis
docker-compose exec web odoo -u plasticos_base --stop-after-init  # Update module

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
| `plasticos-static-audit-kernel` | Broad static audit / evidence report | `audit`, `audit-quick` |
| `plasticos-pr-review-kernel` | `PR_REVIEW_MODE`, `REVIEW PR #N` | `pr-check`, `audit` |
| `plasticos-repo-review-kernel` | Repo-wide readiness / pack review | `audit`, `wiring` |
| `plasticos-final-touches` | `FINAL_TOUCHES_MODE` | `audit` + `pr-check` |
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
- **`make commit` / `make push` omit `.cursor-commands`** — local symlink to Dropbox governance SSOT; that tree is pushed from a separate repo, never from IB-Odoo_19
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
14. Seed data must be wrapped in `<odoo noupdate="1">`

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
make test-odoo              # docker compose --test-enable on ODOO_TEST_DB
make test-module m=<module>
```

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
| `manifest-contract` | Odoo | Yes (pre-push) | `tests/test_repo_dependency_integrity.py` (version, depends order) |
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
| Ruff | `v0.15.5` | `0.15.5` | `make venv` pins `ruff==0.15.5` explicitly | `required-version = "==0.15.5"` (hard-fails on any drift — this is the enforcement mechanism, not a lockfile) |
| mypy | `v1.14.0` | `1.14.0` | `requirements-dev.txt` pins `mypy==1.14.0` | `[tool.mypy]` config (no version field — mypy has no `required-version` equivalent) |
| Semgrep | n/a (not a hook) | `1.164.0` | `make venv` pins `semgrep==1.164.0` explicitly | n/a |
| pytest | n/a (not a hook) | `8.3.5` / `pytest-timeout==2.4.0` / `pytest-cov==5.0.0` | `requirements-dev.txt` — same three pins | `[tool.pytest.ini_options]` |
| gitleaks | pre-commit hook (`gitleaks-commit`/`gitleaks-push`, unpinned local binary) | SHA-pinned action (`gitleaks/gitleaks-action@ff98106e...`, tag `v2`) | local `gitleaks` binary version, unpinned | n/a |
| shellcheck | not yet a pre-commit hook | unpinned (`apt-get install -y shellcheck` = whatever Ubuntu ships) | unpinned (`brew install shellcheck`) | n/a |

Ruff is the only tool with a **hard version gate** (`required-version` in `pyproject.toml` — this is
what caught the drift on 2026-07: a global `ruff==0.14.11` on PATH refused to run against a repo
pinned to `0.15.5`, exactly as designed). This repo intentionally has **no `uv.lock`** — see
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
- Seed data in XML with `noupdate="1"` and external IDs
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

Workspace class: `biome_default` — Default for every governed workspace: Biome owns JS/TS/JSON, Ruff owns Python.

Exactly one formatter owns each language. Do not reformat a file with a tool other than its owner, and do not add config for a competing formatter: the result is a diff that churns on every save.

| Languages | Owner | Note |
|---|---|---|
| `javascript`, `javascriptreact`, `typescript`, `typescriptreact`, `json`, `jsonc` | **biome** | bound by the governed IDE profile |
| `python` | **ruff** | bound by the governed IDE profile |

Generated from `environment/ide/policy.json` in the governance clone by `ops/scripts/adapters/agentdocs.sh`. Edit the policy, not this block.

<!-- END L9 FORMATTER OWNERSHIP -->
