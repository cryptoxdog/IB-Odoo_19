# AGENTS.md — PlasticOS (Odoo 19)

Cross-tool agent instructions for the IB-Odoo_19 repository. Read by Claude Code, Codex, Cursor, Copilot, Jules, Aider, CodeRabbit, and all AGENTS.md-compatible tools.

## Project Overview

- **Name**: PlasticOS — Plastics Recycling Brokerage ERP
- **Type**: Odoo 19 custom module suite (**30** installable `plasticos_*` addons, **~32K** lines Python in addons, **~174** XML files in addons). Four additional `plasticos_graph_*` trees exist for experiments/research and **do not** ship as Odoo addons (no root `__manifest__.py`).
- **Stage**: Production (staging branch → main)
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
plasticos_enrichment_bridge/ # Layer 2: Enrichment → CRM / lead bridge
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

- Branch from `staging`, PR to `staging`
- Merge `staging` → `main` for production
- Commit messages: conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`)
- PRs require passing CI: ruff + XML validation + Odoo pattern checks + secret scan

## CI Compliance Checklist (MANDATORY before commit/PR)

Every code change MUST pass these checks. CI will reject PRs that fail.

### When you create a NEW Python file

1. Add `from . import <filename>` to the parent `models/__init__.py` (or `controllers/__init__.py`)
2. If the file defines a new Odoo model (`_name = "plasticos.something"`):
   - Add ACL entry in `security/ir.model.access.csv`
   - Add the CSV to `__manifest__.py` `data` list if not already there

### When you create a NEW model

1. `_name` MUST be a string literal (`_name = "plasticos.foo"`) — never a variable/constant
2. Add `security/ir.model.access.csv` entry with read/write/create/unlink permissions
3. Every `fields.Many2one` MUST have `ondelete=` parameter (`"restrict"`, `"set null"`, or `"cascade"`)
4. Every `@api.constrains(...)` field name must exist on the model

### When you modify `__manifest__.py`

1. Every module you `from <module> import ...` MUST be in the `depends` list
2. Every XML/CSV file in `data/` or `security/` MUST be in the `data` list
3. No circular dependencies: if A depends on B, B cannot depend on A

### Before committing

Run these checks (all must pass):

```bash
ruff check --fix .                        # Fix lint issues
ruff format .                             # Format code
python3 scripts/check_module_wiring.py    # Dependency + __init__.py wiring
python3 ci/check_circular_deps.py         # No circular deps
python3 ci/check_odoo19_xml.py            # XML pattern compliance
```

### CI gates that block merge

| CI Job | What it checks | Common failure |
|--------|---------------|----------------|
| `static-checks` (test-quality.yml) | Circular deps, XML patterns, module wiring, ORM integrity, XPath stability, model inheritance | Missing `__init__.py` import, broken XPath anchor, phantom dependency in manifest |
| `static-checks` (odoo-audit.yml) | Bash syntax, `_name` must be string literal | `_name = CONSTANT` instead of `_name = "model.name"` |
| `Python Lint & Format` | `ruff check` + `ruff format --check` | Unsorted imports (I001), unused imports (F401), unformatted code |
| `audit` | ACL completeness, constraint field validity, audit regressions | New model without `ir.model.access.csv`, `@api.constrains` on non-existent field |
| `Check Module Dependencies` | `scripts/check_module_wiring.py` | New file not in `__init__.py`, import from module not in `depends` |
| `Secret Detection` | GitGuardian + custom scan | API keys, passwords, tokens in committed code |

### Odoo 19 patterns that CI rejects

- `<tree>` in views → use `<list>`
- `string="..."` attribute on `<search>` → remove it
- `<group>` inside `<search>` → use flat `<filter>` elements
- `attrs="{...}"` on fields → use `invisible="..."` / `readonly="..."` / `required="..."` directly
- `states={"done": [("readonly", True)]}` → use `readonly="state == 'done'"`
- `category_id` on `res.groups` → removed in Odoo 19
- `numbercall` on `ir.cron` → deprecated

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
