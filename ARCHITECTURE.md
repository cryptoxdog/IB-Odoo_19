# ARCHITECTURE.md — PlasticOS System Architecture

**Repository**: cryptoxdog/IB-Odoo_19
**Version**: 19.0.2.0.0
**Architecture**: Layered, deterministic, graph-augmented

## System Overview

PlasticOS implements a 5-layer architecture for plastics recycling brokerage operations. Each layer has strict boundaries, defined responsibilities, and explicit dependencies.

### Core Principles

1. **Deterministic Seed Doctrine**: All reference data versioned in XML
2. **Layer Isolation**: Higher layers depend on lower, never reverse
3. **External intelligence via Gate**: Matching and enrichment authority is Gate → CEG/EIE; Odoo persists results only
4. **Partner Hierarchy**: Native Odoo fields + capability profiles
5. **Intake-First Flow**: Supplier intake drives buyer matching

## Layer Architecture

```
┌─────────────────────────────────────────────────┐
│  Layer 5: TRANSACTION                          │
│  plasticos_transaction, plasticos_logistics     │
│  plasticos_claims                               │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│  Layer 4: COMPLIANCE                           │
│  plasticos_documents, validation matrices       │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│  Layer 3: COMMERCIAL                           │
│  plasticos_accounting, plasticos_offer          │
│  plasticos_automation                           │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│  Layer 2: CAPABILITY                           │
│  plasticos_facility_profile                     │
│  plasticos_matching + plasticos_gate            │
│  plasticos_enrichment (Gate-mediated)           │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│  Layer 1: MATERIAL                             │
│  plasticos_material_profile                     │
│  plasticos_intake, plasticos_product            │
└─────────────────────────────────────────────────┘
```

## Module Index (28 Odoo Modules)

| # | Module | Layer | Maturity | Summary |
|---|--------|-------|----------|---------|
| 1 | `plasticos_base` | 1 | Production | Core seed data: partner tags, sales reps, material taxonomy |
| 2 | `plasticos_security_base` | 1 | Production | RBAC roles, record rules, private-partner flag |
| 3 | `plasticos_material_profile` | 1 | Production | Canonical material master: polymer, form, color, source, process |
| 4 | `plasticos_product` | 1 | Production | Scrap plastic product catalog with polymer-synced products |
| 5 | `plasticos_facility_profile` | 2 | Production | Facility capability profiles: equipment, tolerances, BCP |
| 6 | `plasticos_intake` | 2 | Production | Material intake with contact intelligence |
| 7 | `plasticos_intake_normalizer` | 2 | Beta | Schema-driven intake normalization for L9 packets |
| 8 | `plasticos_matching` | 2 | Production | Match result storage for intake-to-buyer matching |
| 9 | `plasticos_geolocalize` | 2 | Production | Auto-geocode partners + nightly backfill cron |
| 10 | `plasticos_gate` | 2 | New | Constellation Gate TransportPacket client seam (ADR-002) |
| 11 | `plasticos_enrichment` | 2 | Beta | Gate-mediated partner enrichment (local inference retired M7) |
| 12 | `plasticos_web_leads` | 2 | Production | AI lead triage (Cognito → LLM → HOT/COLD) |
| 13 | `plasticos_accounting` | 3 | Production | Chart of accounts, payment terms, incoterms seed |
| 14 | `plasticos_offer` | 3 | Production | Offer lifecycle: match → negotiation → deal |
| 15 | `plasticos_order_lines` | 3 | Production | Extend PO/SO lines with full material specifications |
| 16 | `plasticos_automation` | 3 | Production | Workflow automation: approvals, reminders, SLA monitoring |
| 17 | `plasticos_partner_import` | 3 | Production | Partner import wizard with validation |
| 18 | `plasticos_crm_bridge` | 3 | Production | CRM integration bridge |
| 19 | `plasticos_commission` | 3 | Production | Commission calculation engine |
| 20 | `plasticos_admin_dashboard` | 3 | Production | RevOps KPI dashboard (admin) |
| 21 | `plasticos_documents` | 4 | Production | Document validation matrices, compliance tracking |
| 22 | `plasticos_documents_native` | 4 | Beta | Bridge to Odoo Enterprise Documents with AI auto-sort |
| 23 | `plasticos_transaction` | 5 | Production | Transaction spine + commission engine |
| 24 | `plasticos_logistics` | 5 | Production | Load management, BOL generation, dispatch |
| 25 | `plasticos_claims` | 5 | Production | QC cases, claims, chargebacks, compliance workflows |
| 26 | `plasticos_website` | UI | Disabled | Website extensions (`installable: False`) |
| 27 | `plasticos_odoo_standard_apps` | Meta | Production | Auto-install bundle of standard Odoo CE apps |
| 28 | `plasticos_dev_tools` | — | Dev-only | Audit scripts, integrity checks (`installable: False`) |

**Maturity guide**: Production = stable CI; Beta = higher churn, some CI waivers; New = active development; Disabled = `installable: False`, not currently installed; Dev-only = not for production install.

**Note:** 4 additional directories (`plasticos_graph_*`) exist but are non-Odoo Python packages (no `__manifest__.py`). These are excluded from all pre-commit hooks and CI workflows.

## Module Dependency Graph (Extracted from Manifests)

### Layer 1: Material Foundation

**plasticos_base**
- **Depends**: `base`, `contacts`, `sale_management`
- **Provides**: Partner tags, sales reps, material taxonomy seed
- **Models**: None (seed data only)

**plasticos_material_profile**
- **Depends**: `base`, `contacts`, `mail`, `purchase`, `sale_management`, `product`
- **Provides**: Polymer, form, color, source, process registries
- **Models**:
  - `plasticos.polymer`
  - `plasticos.material.form`
  - `plasticos.material.color`
  - `plasticos.source.type`
  - `plasticos.process.type`
  - `plasticos.material.profile`

**plasticos_intake**
- **Depends**: `base`, `contacts`, `mail`, `plasticos_material_profile`, `plasticos_facility_profile`
- **Provides**: Material intake with contact intelligence
- **Models**:
  - `plasticos.intake`
  - `plasticos.intake.match`

### Layer 2: Capability Profiles

**plasticos_facility_profile**
- **Depends**: `base`, `contacts`, `mail`, `sale_management`, `plasticos_material_profile`
- **Provides**: Equipment types, tolerances, BCP fields
- **Models**:
  - `plasticos.facility.profile`
  - `plasticos.equipment.type`
  - `plasticos.partner.type`
- **Partner Extension**: Adds `facility_profile_id` to `res.partner`

**plasticos_matching**
- **Depends**: `base`, `mail`, `plasticos_intake`, `plasticos_facility_profile`, `plasticos_gate`
- **Provides**: Match result storage (Gate-mediated matching authority)
- **Models**:
  - `plasticos.match.result`

**plasticos_gate**
- **Depends**: `base`, `plasticos_base`
- **Provides**: Constellation Gate TransportPacket client seam — Odoo intelligence routing (see [External Intelligence Boundary (Gate)](#external-intelligence-boundary-gate))
- **External**: `constellation_node_sdk`
- **Models**: None (seed data: ICP allowlist)
- **Services**:
  - `gate_client.py` (TransportPacket send/receive)
  - `gate_builders.py`, `gate_mappers.py`, `gate_contracts.py` (packet construction/mapping)
  - `gate_config.py`, `gate_allowlists.py` (config + ICP allowlist)

### Layer 3: Commercial Operations

**plasticos_accounting**
- **Depends**: `account`
- **Provides**: Chart of accounts, payment terms, incoterms
- **Models**: None (seed data only)

**plasticos_offer**
- **Depends**: `base`, `mail`, `plasticos_intake`, `plasticos_transaction`
- **Provides**: Offer generation and tracking
- **Models**:
  - `plasticos.offer`

**plasticos_automation**
- **Depends**: `base`, `base_automation`, `mail`, `product`, `sale_management`, `account`, `stock`, `purchase`, `plasticos_logistics`, `plasticos_transaction`, `plasticos_claims`
- **Provides**: Workflow automation, SLA monitoring, crons
- **Models**:
  - `plasticos.automation.config`
  - `plasticos.automation.log`

### Layer 4: Compliance

**plasticos_documents**
- **Depends**: `base`, `mail`, `plasticos_transaction`
- **Provides**: Document validation matrices, compliance tracking
- **Models**:
  - `plasticos.document`
  - `plasticos.document.tag`
  - `plasticos.document.rule`
  - `plasticos.document.extension`
  - `plasticos.validation.matrix`
  - `plasticos.transaction.docs`

### Layer 5: Transaction Spine

**plasticos_logistics**
- **Depends**: `sale_management`, `stock`, `mail`
- **Provides**: Load management, BOL generation, dispatch
- **Models**:
  - `plasticos.load`
- **Reports**:
  - BOL Pickup
  - BOL Delivery
  - Delivery Order

**plasticos_transaction**
- **Depends**: `base`, `mail`, `product`, `account`, `sale_management`, `purchase`, `plasticos_logistics`, `plasticos_material_profile`, `plasticos_facility_profile`, `plasticos_intake`, `plasticos_product`
- **Provides**: Transaction lifecycle + commission engine
- **Models**:
  - `plasticos.transaction`
  - `plasticos.commission`
  - `plasticos.transaction.bulk.update.wizard`
  - `plasticos.transaction.bulk.assign.wizard`
  - `plasticos.transaction.import.wizard`

**plasticos_claims**
- **Depends**: `base`, `mail`, `plasticos_transaction`
- **Provides**: Quality claims management
- **Models**:
  - `plasticos.claim`

## Partner Architecture

### Native Odoo Fields (Used)
- `company_type`: "company" | "person"
- `customer_rank`: Integer (0 = not customer)
- `supplier_rank`: Integer (0 = not supplier)
- `category_id`: Many2many to `res.partner.category` (tags)
- `parent_id`: Hierarchical parent
- `property_payment_term_id`: Payment terms
- `type`: "contact" | "invoice" | "delivery" | "other"

### Custom Extensions

**Facility Profile** (`plasticos.facility.profile`)
- **Purpose**: Equipment, tolerances, BCP fields
- **Relationship**: One2many from `res.partner` (facility-level)
- **Fields**:
  - Equipment types (washline, grinder, extruder, etc.)
  - Material tolerances (MFI, color, filler, moisture, etc.)
  - Geographic constraints
  - Company type (`broker`, `mrf`, `recycler`, `enduser`, etc.)

 mode (`strict` vs `relaxed`)

**Material Profile** (`plasticos.material.profile`)
- **Purpose**: Material specifications (not attached to partner directly)
- **Relationship**: Referenced by intake, facility profiles
- **Fields**:
  - Polymer, form, color, source, process
  - MFI, density, moisture content
  - Packaging, contamination levels

### Partner Type Taxonomy (`res.partner.category`)

Extracted from `plasticos_base/data/partner_tags.xml`:
- `Buyer`
- `Supplier`
- `Carrier`
- `Processor`
- `Broker`
- `MRF` (Material Recovery Facility)
- `Recycler`
- `End User`
- `Grinder`
- `Toll Processor`
- `Converter`

## External Intelligence Boundary (Gate)

**Authority:** [docs/adr/ADR-003-single-external-intelligence-authority.md](docs/adr/ADR-003-single-external-intelligence-authority.md) (mothball successor; supersedes ADR-002 §2 fallback-as-authority)  
**Topology / phased human gates:** [docs/adr/ADR-002-gate-hub-phased-autonomy.md](docs/adr/ADR-002-gate-hub-phased-autonomy.md)  
**Phases:** [docs/GATE_AUTONOMY_ROADMAP.md](docs/GATE_AUTONOMY_ROADMAP.md)

PlasticOS routes matching and enrichment intelligence through the **Constellation Gate** — not direct HTTP from Odoo to [Cognitive.Engine.Graphs](https://github.com/cryptoxdog/Cognitive.Engine.Graphs) (CEG) or [Enrichment.Inference.Engine](https://github.com/cryptoxdog/Enrichment.Inference.Engine) (EIE). Odoo is a Gate **consumer** only; CEG/EIE own intelligence semantics.

```
Odoo  ──TransportPacket (constellation_node_sdk)──►  Gate  ──►  CEG / EIE
Odoo  ◄──────────────────────────────────────────  Gate  ◄──
```

| Rule | Detail |
|------|--------|
| Gate is mandatory hub | No Odoo → CEG/EIE direct calls |
| Intelligence authority | Gate → CEG for matching; Gate → EIE `converge` for enrichment |
| Local engines | **Non-authority — physically retired (M7)** — `plasticos_buyer_match_engine` and `plasticos_inference_engine` removed; Gate-only authority |
| Web lead triage (Phase 1) | **Odoo local only** — LLM/vision/HOT-COLD; Gate triage deferred to Phase 3 |
| Human gates (Phase 1) | HOT lead review, match line selection, explicit Send Offer |

**Phase 1 seam:** `plasticos.matching` orchestrator → Gate `action=match` → persist match results in Odoo.

**Implementation module:** `plasticos_gate` (Layer 2) — `services/gate_client.py` sends/receives `TransportPacket` via `constellation_node_sdk`; `gate_builders.py`/`gate_mappers.py`/`gate_contracts.py` construct and map packets; `gate_config.py`/`gate_allowlists.py` hold connection config and the ICP allowlist seed (`data/gate_icp_seed.xml`).

## Retired Local Intelligence (M7)

> **ADR-003 (single external intelligence authority):** Matching and enrichment architectural authority is Gate → CEG/EIE only. M7 physically deleted `plasticos_buyer_match_engine` (local matcher + Neo4j) and `plasticos_inference_engine` (YAML KB inference). Odoo retains result storage (`plasticos_matching`, `plasticos_enrichment`) and Gate client wiring only.

**Retirement evidence:** module directories absent from repo (M7 / TASK-051); `neo4j` driver removed from `requirements.txt`; Neo4j env vars removed from `.env.example`; superseded fallback runtime tests deleted. M8 (TASK-052) activates blocking drift guards in Makefile, pre-commit, CI, and `scripts/check_odoo_patterns.sh`.

**Observation criteria:** `ci/check_no_local_intelligence.py` must block reintroduction of local matcher/inference modules or consumer-path authority; contract tests under `tests/contracts/test_no_local_intelligence.py` assert wiring and absence guards.

## AI/ML Integration Architecture

### OpenAI Integration

**Module**: `plasticos_web_leads`

**Use Case**: Web lead triage and material spec extraction

**Models Used**:
- `gpt-4o` for text normalization and image analysis (multimodal; recommended replacement for `gpt-4-vision-preview`)

**API Configuration**:
```python
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = openai.Client(api_key=OPENAI_API_KEY)
```

**Lead Classification Flow**:
```
Cognito Form Submission
    ↓
LLM Text Normalization (GPT-4o)
    ↓
Vision Analysis (if images attached)
    ↓
Material Spec Extraction
    ↓
Classification: HOT | COLD
    ↓
HOT → Human review → Intake (Phase 1; see GATE_AUTONOMY_ROADMAP.md)
COLD → Skipped / manual review queue
```

**Safety Constraints**:
1. OpenAI failures return "COLD" (manual review)
2. API key missing logs warning, no crash
3. Rate limiting handled with exponential backoff
4. No PII sent to OpenAI (sanitized)

## Transaction Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│  INTAKE PHASE                                               │
│  plasticos.intake                                           │
│  - Supplier contact intelligence                            │
│  - Material spec capture                                    │
│  - Quantity, location, availability                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  MATCHING PHASE (human selects buyers)                      │
│  plasticos_matching + plasticos_gate                        │
│  - Odoo → Gate → CEG → Odoo (ADR-002 / ADR-003)           │
│  - Explicit degraded mode when Gate unavailable (no local)  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  OFFER PHASE                                                │
│  plasticos.offer                                            │
│  - Offer generation to matched buyers                       │
│  - Pricing, terms negotiation                               │
│  - Acceptance tracking                                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  TRANSACTION PHASE                                          │
│  plasticos.transaction                                      │
│  - Transaction record creation                              │
│  - Commission calculation                                   │
│  - Supplier/buyer linkage                                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  LOGISTICS PHASE                                            │
│  plasticos.load                                             │
│  - Load assignment                                          │
│  - Carrier dispatch                                         │
│  - BOL generation (pickup + delivery)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  COMPLIANCE PHASE                                           │
│  plasticos.document, plasticos.validation.matrix            │
│  - Document validation                                      │
│  - Regulatory compliance check                              │
│  - Audit trail                                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  SETTLEMENT PHASE                                           │
│  account.move (Odoo native)                                 │
│  - Invoice generation                                       │
│  - Payment tracking                                         │
│  - Commission payout                                        │
└─────────────────────────────────────────────────────────────┘
```

## Security Architecture

### RBAC Model

**Base Module**: `plasticos_security_base`

**Group Hierarchy**:
```
plasticos_manager (full access)
    ├── plasticos_sales_rep (own transactions)
    ├── plasticos_logistics_coordinator (loads only)
    ├── plasticos_compliance_officer (documents)
    └── plasticos_readonly (reports)
```

### Record Rules

**Multi-Company Isolation**:
- All models inherit `company_id` field
- Record rules enforce `company_id = user.company_id`

**User-Level Restrictions**:
- Sales reps see only own transactions
- Buyers see only own offers
- Suppliers see only own intakes

### ACL Files

Every module includes `security/ir.model.access.csv`:
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_plasticos_intake_user,plasticos.intake user,model_plasticos_intake,plasticos_security_base.group_plasticos_user,1,1,1,0
access_plasticos_intake_manager,plasticos.intake manager,model_plasticos_intake,plasticos_security_base.group_plasticos_manager,1,1,1,1
```

## Data Flow Architecture

### Seed Data Flow
```
XML Data Files (noupdate="1")
    ↓
Odoo Registry Load
    ↓
External ID Assignment
    ↓
Database Insert (if not exists)
    ↓
Reference Integrity Enforced
```

**Seed Data Modules**:
- `plasticos_base`: Partner tags, sales reps, material taxonomy
- `plasticos_material_profile`: Polymers, forms, colors, sources, processes
- `plasticos_facility_profile`: Equipment types, partner types
- `plasticos_accounting`: Chart of accounts, payment terms, incoterms
- `plasticos_logistics`: Incoterms seed

### Runtime Data Flow
```
User Input (UI/API)
    ↓
Odoo ORM Layer
    ↓
Model Constraints Validation
    ↓
PostgreSQL Write
    ↓
Gate egress (match / converge) when intelligence action required
```

## Deployment Architecture

### Docker Deployment

Local `docker-compose.yml` provides PostgreSQL + Odoo only (no Neo4j service after M7). See repo root compose file for the authoritative service list.

### Odoo.sh Deployment

**Requirements**:
- `requirements.txt` in repo root
- Environment variables via Odoo.sh UI
- Database seed via install scripts

**Module Install Order** (enforced by dependencies):
1. `plasticos_base`
2. `plasticos_material_profile`
3. `plasticos_facility_profile`
4. `plasticos_intake`
5. `plasticos_matching`
6. `plasticos_gate`
7. `plasticos_logistics`
8. `plasticos_transaction`
9. `plasticos_documents`
10. All other modules

## Testing Architecture

### Test Database Strategy
- Dedicated test database: `odoo_test`
- Isolated from production seed data
- Transactional rollback after each test

### Test Coverage
- **plasticos_transaction**: 47 tests
- **tests/contracts**: M7 absence guards + external-intelligence authority contracts
- Odoo runtime tests run under `odoo --test-enable` (not pure-python CI tier)

### CI/CD Architecture

**9 GitHub Actions workflow files**. `ci.yml` is the single active CI gate for all PRs and pushes and the only one that blocks merge (alongside the GATE-01 `baseline-ratchet.yml`). The 4 legacy check workflows (`pr-gate.yml`, `odoo-audit.yml`, `module-check.yml`, `test-quality.yml`) were deleted in 2026-07 — every unique check they ran (mypy, shellcheck, `_name` string-literal enforcement, manifest field validation, ACL CSV format, test-attribute-guard, audit-baseline regression) was ported into `ci.yml`, not silently dropped. See `AGENTS.md` § "CI Architecture" for the full job table.

#### Workflow Files

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| **`ci.yml`** | push + PR (all branches) | **Single CI gate**: lint / static-checks / pure-python-tests / secret-scan / audit-baseline run in parallel (fail-slow), `ci-gate-result` aggregates last |
| **`baseline-ratchet.yml`** | push + PR → Staging | GATE-01 baseline ratchet (l9-ci-core reusable workflow, SHA-pinned) |
| `l9-analysis.yml` | push → Staging + PR + manual | Governed semgrep pipeline (l9-ci-core) — advisory-first, not yet a required check |
| `security.yml` | push + PR → staging/main + weekly cron | pip-audit, Trivy, Gitleaks |
| `changelog.yml` | push → Production branch + manual | Auto-update CHANGELOG.md from conventional commits |
| `pr-autopilot.yml` | manual only | Scan open PRs for CI/SonarCloud/CodeRabbit signals |
| `auto-merge.yml` | PR events → staging/main | Auto-merge approved non-draft PRs |
| `auto-review-request.yml` | PR opened/sync → staging/main | Auto-request reviewers on external PRs |
| `release.yml` | tag push `v*.*.*` + manual | Create GitHub Release with changelog and module version list |

#### Pre-commit Hooks (36 total)

All hooks run via `pre-commit run --all-files`. Key hooks:

| Category | Hooks |
|----------|-------|
| Format | `ruff`, `ruff-format`, `end-of-file-fixer`, `trailing-whitespace` |
| Syntax | `check-xml`, `check-yaml`, `check-merge-conflict`, `check-added-large-files` |
| Commit hygiene | `conventional-pre-commit` (commit-msg stage) |
| Odoo 19 | `odoo-patterns` (24 sub-checks), `odoo19-xml`, `odoo19-hooks` |
| Wiring | `module-wiring`, `circular-deps`, `package-init`, `orphan-model-refs` |
| Integrity | `field-integrity`, `orm-integrity`, `constraint-patterns`, `model-inheritance` |
| Safety | `cron-invariants`, `automation-field-refs`, `state-guard-bypass`, `pipeline-v2-guard` |
| Audit | `enhanced-audit`, `acl-completeness` (warn-only), `critical-manifest`, `dev-tools-fence` |
| Pre-push only | `phantom-enum-values`, `manifest-contract`, `gitleaks-push` |
| Secrets | `gitleaks-commit` (staged-file scan), `gitleaks-push` (full repo scan) |
| Type | `mypy` (advisory — many modules excluded) |

#### Global Exclusions

These paths are excluded from all hooks and CI:
- `odoo-enterprise/**`
- `plasticos_graph_engine/**`, `plasticos_graph_integration/**`, `plasticos_graph_intelligence/**`, `plasticos_graph_3d_embedding/**`
- `docs/**` (for ruff, ruff-format, check-xml, trailing-whitespace, end-of-file-fixer)

#### Audit Baselines

| Audit | Baseline | Blocks Merge If Exceeded |
|-------|----------|--------------------------|
| `odoo_audit.py` HIGH count | 0 | Yes |
| Extended audit HIGH count | 4 | Yes (pre-existing N+1 in logistics/transaction) |
| XPath CRITICAL | 0 | Yes |
| XPath HIGH | 0 | Yes |

See `AGENTS.md` CI Compliance Checklist for the complete reference.

## Performance Considerations

### Database Indexing
- Automatically created by Odoo for:
  - Foreign keys (Many2one)
  - `res.partner.customer_rank`, `supplier_rank`
  - Transaction state fields
- Custom indexes via migration scripts (if needed)

### Caching Strategy
- Odoo native cache for computed fields
- Redis (optional) for session management
- No custom cache layers (rely on Odoo ORM)

## Monitoring & Observability

### Logging
- Python `logging` module with structured logs
- Log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`
- Gate client failures logged at `ERROR`
- OpenAI API failures logged at `WARNING`

### Health Checks
- Odoo HTTP endpoint: `/web/health`
- PostgreSQL: `SELECT 1`

### Metrics
- Transaction volume by state
- Match success rate (intake → offer conversion)
- Load fulfillment time
- Document compliance rate

## Odoo 19 Stabilization Fixes (2026-02-25)

Applied as part of the PlasticOS Odoo 19 Fix & Hardening GMP. These changes ensure clean install/upgrade, passing buyer-match tests, and ACL-safe cron execution.

### A. plasticos_base — Service User & Security XML

**Status**: Already compliant; no code changes.

- **service_user.xml**: Defines `user_system_cron` with only valid Odoo 19 `res.users` fields: `name`, `login`, `password`, `active`, `share`, `company_id`, `company_ids`. No `groups_id` or privilege assignment in XML.
- **sales_reps.xml**: Defines sales rep users with same valid fields; no `groups_id` or `users` on `res.groups`. Group assignment is done via Settings > Users > Access Rights or via the post_init_hook (see C).

**Invariants**: No deprecated `groups_id` on `res.users`; no `users` on `res.groups` in XML.

### B. Tests — retired local matcher (M7)

**Status:** `plasticos_buyer_match_engine` physically deleted in M7 / TASK-051. Historical matcher runtime tests lived under the removed module; matching authority is Gate-only via `plasticos_matching` + `plasticos_gate`.

### C. Crons — ACL-Safe Execution

**Problem**: Crons run as `user_system_cron`, which had no group memberships. Access to `plasticos.enrichment.source`, `plasticos.document.rule`, and `plasticos.claim` requires Enrichment/Documents/Claims groups, causing ACL errors when crons executed.

**Solution**: Keep all `ir.cron` records referencing `plasticos_base.user_system_cron` (repo invariant CRON304). Grant the required groups to that user via a **post-install hook** instead of changing cron `user_id` to `base.user_admin`.

**Files**:

- **plasticos_base/hooks.py** (new): Defines `post_init_hook(env)`.
  - Resolves `plasticos_base.user_system_cron`.
  - Adds manager groups if the corresponding modules are installed:
    - `plasticos_enrichment.group_enrichment_manager` (enrichment crons)
    - `plasticos_documents.group_documents_manager` (document crons)
    - `plasticos_claims.group_claims_manager` (claims SLA cron)
  - Uses `(4, gid)` to append groups without removing existing ones.
- **plasticos_base/__manifest__.py**: `"post_init_hook": "post_init_hook"`, version bump to 19.0.1.0.1.
- **plasticos_base/__init__.py**: Exports `post_init_hook` for the manifest.

**Crons unchanged** (still use `user_system_cron`):

- `plasticos_enrichment/data/cron.xml` — enrichment daily, inference standalone
- `plasticos_documents/data/cron_missing_docs.xml`, `cron.xml` — missing docs, compliance audit
- `plasticos_claims/data/claim_cron.xml` — SLA check

**Security**: No ACLs relaxed; cron user is explicitly granted the same manager groups that would be needed for manual execution. Aligns with `SECURITY_MODEL.md`.

### D. Cross-Addon Import Pattern (2026-02-25)

**Problem**: Top-level imports like `from odoo.addons.plasticos_material_profile.form_codes import FORM_SELECTION` cause `ModuleNotFoundError` at module load time due to Odoo's module initialization order.

**Solution**: Defer cross-addon imports using lazy-loading functions.

**Files Fixed**:

| File | Original Import | Fix |
|------|-----------------|-----|
| `plasticos_facility_profile/models/facility_profile.py` | `from plasticos_material_profile.form_codes import FORM_SELECTION` | `_get_form_selection()` callable for Selection field |
| `plasticos_enrichment/models/enrichment_service.py` | (retired) lazy import of `plasticos_inference_engine` | Removed with M7 — Gate-only enrichment path |

**Pattern**:
```python
# WRONG — fails at module load time
from odoo.addons.plasticos_other_module.some_file import SomeClass

# CORRECT — deferred until runtime
def _get_some_class():
    """Lazy load to avoid import error at module load time."""
    from odoo.addons.plasticos_other_module.some_file import SomeClass
    return SomeClass

# Usage in method:
def some_method(self):
    SomeClass = _get_some_class()
    return SomeClass(...)
```

**Invariant**: No top-level cross-addon imports in model files. All `from odoo.addons.plasticos_*` imports must be inside functions.

### E. Dockerfile PYTHONPATH (2026-02-25)

**Problem**: Cross-module imports failed in Docker because `/mnt/extra-addons` was not in Python's module search path.

**Fix**: Added to `Dockerfile`:
```dockerfile
ENV PYTHONPATH="/mnt/extra-addons:${PYTHONPATH}"
```

This ensures all PlasticOS modules at `/mnt/extra-addons` are importable as Python packages.

### F. SQL Constraints Migration (2026-02-25)

**Problem**: Odoo 19 deprecated `_sql_constraints` tuple syntax.

**Fix**: Converted all 20 model files from:
```python
_sql_constraints = [
    ('name_uniq', 'unique(name)', 'Name must be unique'),
]
```

To:
```python
_constraints = [
    models.Constraint(
        'unique(name)',
        'Name must be unique',
    ),
]
```

**Files affected**: `plasticos_web_leads`, `plasticos_transaction`, `plasticos_offer`, `plasticos_material_profile`, `plasticos_matching`, `plasticos_facility_profile`, `plasticos_claims`, `plasticos_logistics`, `plasticos_documents`, `plasticos_automation`.

**Verification**: `grep -r "_sql_constraints" plasticos_*` returns zero matches.

### G. Geo Cron Hardening (2026-02-25)

**Problem**: Nominatim geocoding API returns HTTP 429 (rate limit), causing cron spam on fresh DBs.

**Fixes**:
1. `plasticos_geolocalize/data/cron_geo_backfill.xml`: Set `active=False` by default
2. `cron_geo_backfill()` method: Added early-abort after 3 consecutive failures, exponential backoff (5s delay), per-success commits

### H. Attachment Orphan Cleanup (2026-02-25)

**Problem**: After DB rebuild/restore, `ir.attachment` rows reference missing filestore blobs, causing `FileNotFoundError` in enrichment cron.

**Fix**: Added `plasticos_base/models/ir_attachment.py`:
- `_cron_cleanup_missing_filestore_orphans()`: Daily cron that removes orphan attachment rows
- Cron: `PlasticOS: Cleanup Missing Filestore Attachments`

### I. XML View Fixes (2026-02-25)

**Problem**: Invalid `.strftime()` calls in domain expressions.

**Fix**: Removed `.strftime('%Y-%m-%d')` from `context_today()` calls in:
- `plasticos_logistics/views/load_views.xml`
- `plasticos_offer/views/offer_views.xml`

`context_today()` already returns a date object; `.strftime()` is invalid in Odoo domain expressions.

---

## Odoo 19 Bug Patterns & CI Enforcement

Extracted from `reports/BUG_FIXES_SUMMARY.md`. These patterns are enforced by `scripts/check_odoo_patterns.sh` and pre-commit hooks.

### Odoo 19 Breaking Changes

| Pattern | Status | Enforcement |
|---------|--------|-------------|
| `_sql_constraints` deprecated | ✅ Fixed | CI check #1 |
| `@api.depends("id")` disallowed | ✅ Fixed | CI check #2 |
| `@api.one/@api.multi` removed | ✅ Clean | CI check #3 |
| `category_id` on `res.groups` removed | ✅ Fixed | CI check #4 |
| `groups_id` on `res.users` removed | ✅ Fixed | Manual audit |
| `users` field on `res.groups` removed | ✅ Fixed | Manual audit |
| `numbercall` on `ir.cron` deprecated | ✅ Clean | CI check #5 |

### Field Type & Reference Patterns

| Pattern | Example | Fix |
|---------|---------|-----|
| String writes to Many2one | `"polymer": "hdpe"` | Use `"polymer_id": record.id` |
| Wrong relational field in domain | `transaction_id.user_id` on `plasticos.load` | Use correct field path |
| Duplicate field labels | `polymer` and `polymer_id` both "Polymer" | Add "Code" suffix to computed |
| View field name mismatch | `packaging_type` vs `packaging_type_id` | Align view with model |

### XML Data File Patterns

| Pattern | Example | Fix |
|---------|---------|-----|
| Missing `<data>` wrapper | Bare records | Add `<data noupdate="1">` |
| Unescaped `&` in XML | `PC & PMMA` | Use `&amp;` |
| Nested quotes in `eval` | `eval="[ref("id")]"` | Use single quotes: `ref('id')` |
| Missing module prefix in `ref()` | `ref('attr_clean')` | Add module: `ref('plasticos_material_profile.attr_clean')` |
| Cron `model_id` missing prefix | `ref="model_plasticos_load"` | Add module: `ref="plasticos_logistics.model_plasticos_load"` |

### Code Quality Patterns

| Pattern | Example | Fix |
|---------|---------|-----|
| Empty inherit files | `class SaleOrder(models.Model): _inherit = "sale.order"` with no fields | Delete file |
| Namespace drift | `PlastosMaterialProfile` | Fix to `PlasticosMaterialProfile` |
| Empty `__init__.py` in modules | Models won't load | Add proper imports |

### CI Checks Summary (12 Total)

| # | Check | Pattern |
|---|-------|---------|
| 1 | `_sql_constraints` | Deprecated in Odoo 17+ |
| 2 | `@api.depends("id")` | Disallowed in Odoo 19 |
| 3 | `@api.one/@api.multi` | Removed in Odoo 13+ |
| 4 | `category_id` on `res.groups` | Removed in Odoo 19 |
| 5 | `numbercall` on ir.cron | Deprecated |
| 6 | Unescaped `&` in XML | Parse errors |
| 7 | Empty `__init__.py` | Models won't load |
| 8 | Namespace drift | `PlastoS` vs `PlasticoS` |
| 9 | Empty inherit files | Dead code |
| 10 | Cron `model_id` refs | Missing module prefix |
| 11 | XML `eval` quotes | Nested double quotes |
| 12 | String writes to Many2one | `"polymer": val` instead of `"polymer_id": rec.id` |

### Pre-Commit Hooks

| Hook | What it catches |
|------|-----------------|
| `ruff` | Python syntax, unused imports, undefined names |
| `ruff-format` | Python formatting |
| `check-xml` | XML syntax errors |
| `check-yaml` | YAML syntax errors |
| `trailing-whitespace` | Trailing whitespace |
| `end-of-file-fixer` | Missing newline at EOF |
| `check-merge-conflict` | Leftover merge markers |

### Bugs Requiring Runtime Validation

These cannot be caught by static analysis — require `odoo -i module --test-enable`:

| Bug Type | Why Static Tools Miss It |
|----------|--------------------------|
| Invalid field references in domains | Requires model schema knowledge |
| Field name mismatches (view ↔ model) | Views aren't type-checked against models |
| External ID references to non-existent records | Requires database state |
| Enterprise module dependencies | Requires installed module list |

---

## Bulk Action Wizards

Created 2026-02-21 to 2026-02-22 for common administrative operations.

### Available Wizards

| Module | Wizard | Purpose |
|--------|--------|---------|
| `plasticos_claims` | `claim_bulk_update_wizard` | Bulk status change, assignment, escalation |
| `plasticos_logistics` | `load_bulk_update_wizard` | Bulk status updates for loads |
| `plasticos_offer` | `offer_bulk_action_wizard` | Bulk send/accept/reject/cancel |
| `plasticos_web_leads` | `lead_bulk_action_wizard` | Bulk force-hot, retry triage, mark skipped |
| `plasticos_partner_import` | `partner_bulk_update_wizard` | Bulk update partners (salesperson, categories, privacy) |
| `plasticos_transaction` | `transaction_bulk_assign_wizard` | Bulk assign suppliers/buyers |
| `plasticos_transaction` | `transaction_import_wizard` | Import from cieTrade CSV |

### Wizard File Structure

Each wizard follows this pattern:
```
module/
├── wizards/
│   ├── __init__.py
│   └── wizard_name.py          # TransientModel
├── views/
│   └── wizard_name_views.xml   # Form view + action binding
├── security/
│   └── ir.model.access.csv     # ACL for wizard model
└── __manifest__.py             # Include view in data list
```

---

**Architecture Version**: 3.2.0
**Last Updated**: 2026-07-22
**Verified Against**: cryptoxdog/IB-Odoo_19 @ Staging branch
