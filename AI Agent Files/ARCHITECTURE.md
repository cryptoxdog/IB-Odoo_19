# ARCHITECTURE.md — PlasticOS System Architecture

**Repository**: cryptoxdog/IB-Odoo_19
**Version**: 19.0.2.0.0
**Architecture**: Layered, deterministic, graph-augmented

## System Overview

PlasticOS implements a 5-layer architecture for plastics recycling brokerage operations. Each layer has strict boundaries, defined responsibilities, and explicit dependencies.

### Core Principles

1. **Deterministic Seed Doctrine**: All reference data versioned in XML
2. **Layer Isolation**: Higher layers depend on lower, never reverse
3. **Graph Augmentation**: Neo4j for scoring, Odoo for transactions
4. **Partner Hierarchy**: Native Odoo fields + capability profiles
5. **Intake-First Flow**: Supplier intake drives buyer matching

## Layer Architecture

```
┌─────────────────────────────────────────────────┐
│  Layer 5: TRANSACTION                          │
│  plasticos_transaction, plasticos_logistics     │
│  plasticos_documents, plasticos_claims          │
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
│  plasticos_buyer_match_engine (+ Neo4j)         │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│  Layer 1: MATERIAL                             │
│  plasticos_material_profile                     │
│  plasticos_intake, plasticos_product            │
└─────────────────────────────────────────────────┘
```

## Module Index (25 Odoo Modules)

| # | Module | Layer | Summary |
|---|--------|-------|---------|
| 1 | `plasticos_base` | 1 | Core seed data: partner tags, sales reps, material taxonomy |
| 2 | `plasticos_security_base` | 1 | RBAC roles, record rules, private-partner flag |
| 3 | `plasticos_material_profile` | 1 | Canonical material master: polymer, form, color, source, process |
| 4 | `plasticos_product` | 1 | Scrap plastic product catalog with polymer-synced products |
| 5 | `plasticos_facility_profile` | 2 | Facility capability profiles: equipment, tolerances, BCP |
| 6 | `plasticos_intake` | 2 | Material intake with contact intelligence |
| 7 | `plasticos_intake_normalizer` | 2 | Schema-driven intake normalization for L9 packets |
| 8 | `plasticos_matching` | 2 | Match result storage for intake-to-buyer matching |
| 9 | `plasticos_buyer_match_engine` | 2 | 10-gate filtering + Neo4j graph scoring |
| 10 | `plasticos_geolocalize` | 2 | Auto-geocode partners + nightly backfill cron |
| 11 | `plasticos_accounting` | 3 | Chart of accounts, payment terms, incoterms seed |
| 12 | `plasticos_offer` | 3 | Offer lifecycle: match → negotiation → deal |
| 13 | `plasticos_order_lines` | 3 | Extend PO/SO lines with full material specifications |
| 14 | `plasticos_automation` | 3 | Workflow automation: approvals, reminders, SLA monitoring |
| 15 | `plasticos_transaction` | 5 | Transaction spine + commission engine |
| 16 | `plasticos_logistics` | 5 | Load management, BOL generation, dispatch |
| 17 | `plasticos_documents` | 4 | Document validation matrices, compliance tracking |
| 18 | `plasticos_documents_native` | 4 | Bridge to Odoo Enterprise Documents with AI auto-sort |
| 19 | `plasticos_claims` | 5 | QC cases, claims, chargebacks, compliance workflows |
| 20 | `plasticos_web_leads` | 2 | AI-powered web lead triage: Cognito → LLM → HOT/COLD |
| 21 | `plasticos_enrichment` | 2 | AI-powered web intelligence extraction for buyer profiles |
| 22 | `plasticos_enrichment_bridge` | 2 | Bridge to external Enrichment API for CRM leads |
| 23 | `plasticos_inference_engine` | 2 | Deterministic polymer inference from YAML knowledge base |
| 24 | `plasticos_partner_import` | 3 | Partner import wizard with validation |
| 25 | `plasticos_dev_tools` | — | Dev-only: audit scripts, integrity checks, validators |

**Note:** 4 additional directories (`plasticos_graph_*`) exist but are non-Odoo Python packages (no `__manifest__.py`).

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
- **Depends**: `base`, `mail`, `plasticos_intake`, `plasticos_facility_profile`
- **Provides**: Match result storage
- **Models**:
  - `plasticos.match.result`

**plasticos_buyer_match_engine**
- **Depends**: `plasticos_intake`, `plasticos_material_profile`, `plasticos_matching`, `plasticos_facility_profile`, `plasticos_transaction`
- **Provides**: v2.0 facility-based matching with Neo4j scoring
- **External**: `neo4j>=5.0.0`
- **Models**:
  - `plasticos.match.exclusion`
- **Services**:
  - `graph_service.py` (Neo4j driver wrapper)
  - `matcher.py` (10-gate filtering + Cypher scoring)

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

## Neo4j Integration Architecture

### Connection Strategy
- **Driver**: `neo4j>=5.0.0` Python driver
- **Module**: `plasticos_buyer_match_engine`
- **Service**: `services/graph_service.py`

### Environment Configuration
```python
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
```

### Graph Isolation Boundaries

**Safe Boundaries Enforced**:
1. Neo4j imports wrapped in try/except
2. Graph failures return empty results, do not crash
3. No Neo4j imports in Odoo registry load path
4. Connection pooling with timeout

**Graph Service Pattern**:
```python
class GraphService:
    def __init__(self):
        self.driver = None
        self._connect()

    def _connect(self):
        try:
            self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        except Exception as e:
            _logger.error(f"Neo4j connection failed: {e}")
            self.driver = None

    def execute_query(self, cypher, params):
        if not self.driver:
            return []
        try:
            with self.driver.session() as session:
                result = session.run(cypher, params)
                return [record.data() for record in result]
        except Exception as e:
            _logger.error(f"Neo4j query failed: {e}")
            return []
```

### Matching Engine Flow

**Stage 1: Python 10-Gate Filtering**
```
Intake Material → Facility Profiles
├── Gate 1: Polymer Match
├── Gate 2: Form Match
├── Gate 3: Color Match
├── Gate 4: Filler Match
├── Gate 5: Source Type Match
├── Gate 6: MFI Range
├── Gate 7: Density Range
├── Gate 8: Moisture Tolerance
├── Gate 9: Contamination Tolerance
└── Gate 10: Volume Minimum
```

**Gate Modes**:
- **Strict Mode**: All 10 gates enforced
- **Relaxed Mode**: Only polymer gate enforced, others penalized

**Stage 2: Neo4j Cypher Scoring**
```cypher
MATCH (intake:Intake {intake_id: $intake_id})
MATCH (facility:Facility)
WHERE facility.accepted_polymers CONTAINS intake.polymer
RETURN facility.partner_id AS buyer_id,
       gds.similarity.cosine(intake.specs, facility.specs) AS score
ORDER BY score DESC
LIMIT 20
```

### Ontology Mapping

From `ONTOLOGY_NEO4J_FIELD_CROSSWALK.md`:

**Node Labels**:
- `Material` → `plasticos.material.profile`
- `Facility` → `plasticos.facility.profile`
- `Intake` → `plasticos.intake`
- `Transaction` → `plasticos.transaction`

**Relationships**:
- `(:Facility)-[:ACCEPTS]->(:Material)`
- `(:Facility)-[:LOCATED_IN]->(:Region)`
- `(:Intake)-[:MATCHED_TO]->(:Facility)`
- `(:Transaction)-[:FULFILLED_BY]->(:Facility)`

## AI/ML Integration Architecture

### OpenAI Integration

**Module**: `plasticos_web_leads`

**Use Case**: Web lead triage and material spec extraction

**Models Used**:
- `gpt-4o` for text normalization
- `gpt-4o-vision-preview` for image analysis

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
HOT → Auto-create Intake
COLD → Manual Review Queue
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
│  MATCHING PHASE                                             │
│  plasticos_buyer_match_engine                               │
│  - 10-gate Python filtering                                 │
│  - Neo4j graph scoring                                      │
│  - Geographic proximity                                     │
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
(Optional) Neo4j Sync via Outbox
    ↓
Graph Update
```

## Deployment Architecture

### Docker Deployment
```yaml
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}

  odoo:
    build: .
    depends_on:
      - db
      - neo4j
    environment:
      - DB_HOST=db
      - NEO4J_URI=bolt://neo4j:7687
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./plasticos_*:/mnt/extra-addons

  neo4j:
    image: neo4j:5.15-community
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
```

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
6. `plasticos_buyer_match_engine`
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
- **plasticos_buyer_match_engine**: 5 tests
- **Total**: 52 tests passing

### CI/CD Integration
- Pre-commit hooks: ruff, module wiring, XML validation
- GitHub Actions (if configured): test suite on PR
- Odoo.sh CI: automatic test run on push

## Performance Considerations

### Database Indexing
- Automatically created by Odoo for:
  - Foreign keys (Many2one)
  - `res.partner.customer_rank`, `supplier_rank`
  - Transaction state fields
- Custom indexes via migration scripts (if needed)

### Neo4j Query Optimization
- Cypher queries use `LIMIT` (default 20 results)
- Graph indexes on `partner_id`, `material_id`
- Connection pooling with max sessions = 50

### Caching Strategy
- Odoo native cache for computed fields
- Redis (optional) for session management
- No custom cache layers (rely on Odoo ORM)

## Monitoring & Observability

### Logging
- Python `logging` module with structured logs
- Log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`
- Neo4j connection failures logged at `ERROR`
- OpenAI API failures logged at `WARNING`

### Health Checks
- Odoo HTTP endpoint: `/web/health`
- Neo4j: `CALL dbms.ping()`
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

### B. Tests — plasticos_buyer_match_engine

**Files**: `plasticos_buyer_match_engine/tests/test_matcher.py`

**Fixes applied**:

1. **Get-or-create for master data** (avoids `UniqueViolation` on module load):
   - Polymer (hdpe, pp), material form (bales), material color (natural), source type (pcr, pir) are searched first; `create()` is called only if no record exists. Prevents duplicate key errors when demo data or other modules already created these records.

2. **Required `form_id` on material profile creates** (avoids `NotNullViolation`):
   - `plasticos.material.profile` has `form_id` required in DB. All test methods that create a material profile now include `form_id: self.form_bales.id`.
   - Affected tests:
     - `test_action_match_to_buyers_with_material_profile`
     - `test_action_match_to_buyers_uses_match_mode_strict`
     - `test_action_match_to_buyers_uses_match_mode_relaxed`
     - `test_action_match_to_buyers_returns_action_window`

**Pattern for new tests**: When creating `plasticos.material.profile`, always set `form_id` (and optionally `color_id`, `source_type_id`) from setUp’s get-or-create master data.

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
| `plasticos_buyer_match_engine/models/graph_service.py` | `from odoo.addons.plasticos_material_profile.form_codes import EQUIPMENT_GATED_FORMS, PASSTHROUGH_FORMS` | `_get_form_codes()` lazy loader |
| `plasticos_enrichment/models/enrichment_service.py` | `from odoo.addons.plasticos_inference_engine import InferenceEngine, InferenceRequest` | `_get_inference_classes()` lazy loader |
| `plasticos_inference_engine/pipeline_v2.py` | `from plasticos_inference_engine import ...` | `from . import ...` (relative import) |

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
- `plasticos_buyer_match_engine/views/match_exclusion_views.xml`
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

**Architecture Version**: 2.3.0
**Last Updated**: 2026-03-04
**Verified Against**: cryptoxdog/IB-Odoo_19 @ staging branch
