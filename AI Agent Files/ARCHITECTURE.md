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

---

**Architecture Version**: 2.0.0
**Last Updated**: 2026-02-24
**Verified Against**: cryptoxdog/IB-Odoo_19 @ staging branch
```
