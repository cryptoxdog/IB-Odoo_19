# AGENTS.md — PlasticOS (Odoo 19)

Cross-tool agent instructions for the IB-Odoo_19 repository. Read by Claude Code, Codex, Cursor, Copilot, Jules, Aider, CodeRabbit, and all AGENTS.md-compatible tools.

## Project Overview

- **Name**: PlasticOS — Plastics Recycling Brokerage ERP
- **Type**: Odoo 19 custom module suite (**29** installable `plasticos_*` addons, **~32K** lines Python in addons, **~174** XML files in addons).
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
make roadmap                              # Validate docs/roadmap/registry.yaml alignment
make roadmap-sync                         # Regenerate roadmap markdown from registry
make roadmap-add domain=gate-autonomy phase=1 kind=backlog title="..."

# Docker
docker-compose up -d                      # Start Odoo + PostgreSQL + Redis
docker-compose exec web odoo -u plasticos_base --stop-after-init  # Update module

# Tests (requires running Odoo instance)
python -m pytest tests/ -v                # All tests
python -m pytest tests/contracts/ -v      # Contract tests
python -m pytest tests/integration/ -v    # Integration tests
```

## Testing

- Contract tests: `tests/contracts/` — 8 contract test files
- Integration tests: `tests/integration/` — 10 integration test files
- Unit tests: `tests/test_*.py` — **28** standalone test modules at `tests/` root (plus deeper `tests/` tree; run `pytest tests/ --collect-only` for full count)
- Every new model/field needs at least one test
- Tests must not mutate seed data
- Run `pre-commit run --all-files` before opening a PR

## Agent Skills & Subagents

Skills live in `.claude/skills/`; subagents in `.claude/agents/`. Full registry: `.claude/README.md`.

| Skill | When to load |
|-------|--------------|
| `structured-reasoning` | Planning, plan review, architecture decisions, debugging |
| `new-odoo-module` | Scaffolding a new `plasticos_*` module |
| `new-model-field` | Adding fields or models to existing modules |
| `xml-view` | Creating or modifying Odoo XML views |
| `odoo-sh-deploy` | Odoo.sh production errors — SSH diagnose before fix |
| `update-agent-docs` | Refresh AGENTS.md / ARCHITECTURE.md / INVARIANTS.md / CLAUDE.md |
| `skill-compiler` | Compile kernels/SOPs into zero-stub skill packs |

| Subagent | Preloaded skills | Delegate for |
|----------|------------------|--------------|
| `plasticos-code-reviewer` | `structured-reasoning` | PR review, invariant compliance |
| `module-auditor` | `structured-reasoning`, `new-odoo-module`, `new-model-field` | Module structure/wiring audit |

## Project Structure

```
plasticos_base/              # Layer 1: Core seed data, feature gates, partner tags
plasticos_security_base/     # Layer 1: RBAC roles, record rules, ACL
plasticos_material_profile/  # Layer 1: Material master (polymer, form, color, source)
plasticos_product/           # Layer 1: Scrap plastic product catalog
plasticos_facility_profile/  # Layer 2: Facility capabilities, equipment, tolerances
plasticos_intake/            # Layer 2: Material intake with contact intelligence
plasticos_intake_normalizer/ # Layer 2: L9 packet normalization
plasticos_matching/          # Layer 2: Match result storage
plasticos_buyer_match_engine/# Layer 2: 10-gate filtering + Neo4j graph scoring
plasticos_geolocalize/       # Layer 2: Auto-geocode + nightly backfill
plasticos_enrichment/        # Layer 2: AI web intelligence extraction
plasticos_web_leads/         # Layer 2: AI lead triage (Cognito → LLM → HOT/COLD)
plasticos_inference_engine/  # Layer 2: Deterministic polymer inference (YAML KB)
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
plasticos_website/           # UI: Website extensions
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
pre-commit run --all-files                # Run ALL 31 hooks at once
```

### CI Architecture — `ci.yml` is the Single Gate (11 Workflow Files)

`ci.yml` is the **only workflow that runs automatically on PRs and pushes**. All other legacy check workflows (`pr-gate.yml`, `odoo-audit.yml`, `module-check.yml`, `test-quality.yml`) are disabled (`workflow_dispatch` manual-only) to eliminate duplicate runs.

**Active workflows and their triggers:**

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| **`ci.yml`** | push + PR (all branches) | Single CI gate — Tier 1 lint → Tier 2 static → Tier 3 pytest |
| `security.yml` | push + PR → staging/main + weekly | pip-audit, Trivy, Gitleaks |
| `changelog.yml` | push → Production + manual | Auto-update CHANGELOG.md |
| `auto-merge.yml` | PR events → staging/main | Auto-merge approved non-draft PRs |
| `auto-review-request.yml` | PR opened/sync → staging/main | Auto-request reviewers |
| `release.yml` | tag `v*.*.*` + manual | GitHub Release creation |
| `pr-autopilot.yml` | manual only | Scan open PRs for CI/SonarCloud signals |
| `test-quality.yml` | manual only | Full Odoo runtime tests (Odoo.sh) |
| `odoo-audit.yml` | manual only | Legacy — superseded by ci.yml |
| `pr-gate.yml` | manual only | Legacy — superseded by ci.yml |
| `module-check.yml` | manual only | Legacy — superseded by ci.yml |

**`ci.yml` blocking jobs** (must pass for merge):

| CI Job | Tier | What it checks | Common failure |
|--------|------|---------------|----------------|
| `lint` | 1 | `ruff check` + `ruff format --check` | Unsorted imports (I001), unformatted code |
| `static-checks` | 2 (needs lint) | XML syntax, manifest syntax, bash syntax, Odoo 19 patterns, circular deps, module wiring, orphan refs, XPath stability, ORM integrity, model inheritance, dev-tools fence, pipeline-v2 guard | Missing `__init__.py` import, broken XPath, phantom dep |
| `pure-python-tests` | 3 (needs static) | pytest suite (no Odoo runtime): dependency integrity, compat, cron invariants, XML patterns, enum alignment | Test assertion failure, missing fixture |

**Non-blocking (advisory):**

| CI Job | Workflow | Notes |
|--------|----------|-------|
| `secret-scan` | `ci.yml` | `continue-on-error: true` — Gitleaks |
| `dependency-scan` | `security.yml` | `pip-audit \|\| true` |
| `trivy-scan` | `security.yml` | `exit-code: 0` |

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
| Ruff lint | `plasticos_inference_engine`, `plasticos_buyer_match_engine`, `plasticos_matching` | Excluded in `ci.yml` ruff step |
| mypy | `plasticos_web_leads`, `plasticos_enrichment`, `plasticos_buyer_match_engine`, `plasticos_inference_engine` | Complex patterns, gradual typing |
| ACL completeness | all modules | Non-blocking hook (warn-only) |
| Odoo patterns script | CI workflows | `|| true` — tracked separately |
| YAML syntax | `plasticos_enrichment/knowledge_base/*.yaml`, `buyer_matching_rag.yaml` | Complex YAML not standard Odoo |
| All pre-commit hooks | `odoo-enterprise/**`, `plasticos_graph_*/**` | External/experimental code |
| All pre-commit hooks | `docs/**` | Documentation files |

### Pre-commit Hooks (31 total)

| Hook | Type | Blocking? | What it catches |
|------|------|-----------|-----------------|
| `ruff` | Lint | Yes | Python lint violations (E/W/F/I/B/UP/C90) |
| `ruff-format` | Format | Yes | Unformatted Python code |
| `check-xml` | Syntax | Yes | Malformed XML |
| `check-yaml` | Syntax | Yes | Malformed YAML |
| `end-of-file-fixer` | Format | Yes | Missing newline at EOF |
| `trailing-whitespace` | Format | Yes | Trailing whitespace |
| `check-added-large-files` | Guard | Yes | Files over 1000 KB |
| `check-merge-conflict` | Guard | Yes | Leftover merge conflict markers |
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
| `pipeline-v2-guard` | Odoo | Yes | Import fence for pipeline v2 |
| `dev-tools-fence` | Odoo | Yes | Dev tools not imported from production |
| `critical-manifest` | Odoo | Yes | Critical manifest rules |
| `enhanced-audit` | Odoo | Yes | Enhanced code audit |
| `mypy` | Type | **No** | Type checking (excludes many modules) |

### Ruff Configuration (from `pyproject.toml`)

| Setting | Value |
|---------|-------|
| Line length | **120** (not 100) |
| Target Python | 3.12 |
| Rules selected | E, W, F, I, B, UP, C90 |
| McCabe max-complexity | 25 |
| Ignored | E501 (formatter), E731 (lambdas), B008 (Odoo field defaults), B905 (zip strict) |
| `__init__.py` exempt from | F401 (unused imports), I001 (import order) |
| `__manifest__.py` exempt from | B018 (bare dict) |
| `test_*.py` exempt from | F841, B011, F821, B017 |

### Audit Baselines (enforced by `ci.yml` static-checks tier)

CI fails if HIGH severity findings exceed these baselines:

| Audit | Baseline | Notes |
|-------|----------|-------|
| `odoo_audit.py` HIGH | 0 | Any new HIGH finding blocks merge |
| Extended audit HIGH | 4 | Pre-existing N+1 in `plasticos_logistics/load.py` and `plasticos_transaction/transaction.py` |
| XPath CRITICAL | 0 | No new CRITICAL XPath issues allowed |
| XPath HIGH | 0 | No new HIGH XPath issues allowed |

### Version Drift Warning

| Tool | Pre-commit | CI (`ci.yml`) |
|------|-----------|--------------|
| Ruff | `v0.15.5` | `0.14.11` |

Pre-commit and CI may use different ruff versions. Always run `pre-commit run --all-files` locally before pushing.

## Boundaries

### ✅ Always
- Use `plasticos_` prefix for all module/model/external ID names
- Add `security/ir.model.access.csv` for every new model
- Use `sanitize_label()` patterns — no f-string SQL/Cypher
- Declare dependencies in `__manifest__.py` before importing
- Seed data in XML with `noupdate="1"` and external IDs
- Run `python3 scripts/check_module_wiring.py` before commit

### ⚠️ Ask First
- Adding new modules (affects dependency graph and install order)
- Modifying `plasticos_base` (affects all downstream modules)
- Changing security groups or record rules
- Adding new `ir.cron` scheduled actions
- Neo4j integration changes (graph boundary rules apply)
- Gate / CEG integration (follow `docs/adr/ADR-002` and `docs/GATE_AUTONOMY_ROADMAP.md`)
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
- Call CEG/EIE directly from Odoo → route through Gate (`constellation_node_sdk`; see ADR-002)
- Apply Gate web-lead triage or remove local matcher fallback in Phase 1 (see GATE_AUTONOMY_ROADMAP.md)
