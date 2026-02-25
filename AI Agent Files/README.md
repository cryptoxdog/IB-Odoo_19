# PlasticOS — Odoo 19 Industrial Brokerage Suite

**Repository**: cryptoxdog/IB-Odoo_19
**Branch**: staging
**Odoo Version**: 19.0
**Python**: 3.12+
**Database**: PostgreSQL
**Graph Database**: Neo4j 5.0+

## Overview

PlasticOS is a deterministic, layered transaction management system for the plastics recycling brokerage industry. Built on Odoo 19, it implements a strict 5-layer architecture with Neo4j graph integration for intelligent buyer-facility matching.

## Architecture Layers

1. **Material Layer**: Canonical polymer, form, color, source, process registries
2. **Capability Layer**: Facility profiles with equipment, tolerances, BCP fields
3. **Commercial Layer**: Pricing, commissions, payment terms, partner taxonomy
4. **Compliance Layer**: Document validation matrices, regulatory tracking
5. **Transaction Layer**: Intake → Matching → Offer → Load → Settlement spine

## Active Modules (33)

### Core Foundation
- `plasticos_base` — Partner tags, sales reps, material taxonomy seed
- `plasticos_security_base` — RBAC, record rules, group hierarchy
- `plasticos_accounting` — Chart of accounts, payment terms, incoterms

### Material & Capability
- `plasticos_material_profile` — Polymer, form, color, source, process registries
- `plasticos_facility_profile` — Equipment types, tolerances, BCP capabilities
- `plasticos_product` — Product variants with material linkage

### Transaction Spine
- `plasticos_intake` — Material intake with contact intelligence
- `plasticos_intake_normalizer` — UX normalization layer
- `plasticos_matching` — Match result storage
- `plasticos_buyer_match_engine` — v2.0 facility-based matching + Neo4j
- `plasticos_offer` — Offer generation and tracking
- `plasticos_transaction` — Core transaction lifecycle + commission engine
- `plasticos_logistics` — Load management, BOL generation, dispatch
- `plasticos_order_lines` — Order line extensions

### Intelligence & Automation
- `plasticos_enrichment` — Knowledge base, YAML-driven enrichment
- `plasticos_inference_engine` — Graph-based capability inference
- `plasticos_web_leads` — AI-powered lead triage (OpenAI GPT-4o + Vision)
- `plasticos_automation` — Workflow automation, SLA monitoring, crons
- `plasticos_geolocalize` — Partner geolocation services

### Compliance & Quality
- `plasticos_documents` — Document validation matrices, compliance tracking
- `plasticos_documents_native` — Native Odoo document integration
- `plasticos_claims` — Quality claims management

### Data Management
- `plasticos_partner_import` — CSV partner import with graph sync
- `plasticos_dev_tools` — Development utilities

## Key Features

### Neo4j Graph Integration
- **Driver**: neo4j>=5.0.0
- **Use Cases**: Buyer-facility matching with geographic proximity scoring
- **Isolation**: Graph failures do not crash Odoo registry
- **Environment Variables**:
  - `NEO4J_URI`
  - `NEO4J_USER`
  - `NEO4J_PASSWORD`

### AI/ML Integration
- **OpenAI Integration**: GPT-4o for lead triage, vision analysis
- **Use Cases**: Web lead classification (HOT/COLD), material spec extraction
- **Module**: `plasticos_web_leads`

### Deterministic Seed Doctrine
- All seed data in XML with `noupdate="1"`
- No runtime CSV bootstrap
- External IDs for all reference data
- Reproducible across environments

## Installation

```bash
# Clone repository
git clone https://github.com/cryptoxdog/IB-Odoo_19.git
cd IB-Odoo_19

# Copy environment template
cp .env.example .env

# Edit .env with actual credentials
# POSTGRES_USER, POSTGRES_PASSWORD, NEO4J_URI, etc.

# Build Docker image
docker build -t plasticos-odoo:19 .

# Run Odoo
docker run -d \
  --name odoo19 \
  -p 8069:8069 \
  -v ./config:/etc/odoo \
  -v ./plasticos_*:/mnt/extra-addons \
  --env-file .env \
  plasticos-odoo:19
```

## Development Workflow

### Pre-Commit Hooks
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

### Run Tests
```bash
./scripts/run-odoo-tests.sh plasticos_transaction
./scripts/run-odoo-tests.sh plasticos_buyer_match_engine
```

### Check Module Wiring
```bash
python3 scripts/check_module_wiring.py
```

### Rebuild Database
```bash
./scripts/rebuild-odoo-db.sh odoo_dev
```

## Module Dependency Graph

```
plasticos_base
├── plasticos_material_profile
│   ├── plasticos_facility_profile
│   │   ├── plasticos_matching
│   │   │   └── plasticos_buyer_match_engine (Neo4j)
│   │   └── plasticos_intake
│   │       ├── plasticos_intake_normalizer
│   │       ├── plasticos_offer
│   │       └── plasticos_web_leads (OpenAI)
│   └── plasticos_product
├── plasticos_logistics
│   └── plasticos_transaction
│       ├── plasticos_documents
│       └── plasticos_claims
└── plasticos_automation
```

## Configuration

### Required Environment Variables
- `POSTGRES_USER`: Database user
- `POSTGRES_PASSWORD`: Database password
- `ODOO_DB_HOST`: Database host (default: db)
- `NEO4J_URI`: Neo4j connection string
- `NEO4J_USER`: Neo4j username
- `NEO4J_PASSWORD`: Neo4j password
- `OPENAI_API_KEY`: OpenAI API key (for web_leads)

### Optional Configuration
- `ODOO_REBUILD_MODULES`: Comma-separated module list for rebuild script
- `ODOO_TEST_MODULES`: Comma-separated module list for test script

## Production Deployment

See [`DEPLOYMENT.md`](./DEPLOYMENT.md) for:
- Odoo.sh deployment instructions
- Environment-specific configurations
- Database migration procedures
- Neo4j cluster setup

## Testing

- **Test Count**: 52 tests passing
- **Coverage**: Transaction (47), Buyer Match Engine (5)
- **Test Database**: `odoo_test`
- **Disabled for CI**: Modules requiring seed data (enrichment, dev_tools)

## Security

- **RBAC**: Role-based access control via `plasticos_security_base`
- **Record Rules**: Multi-company isolation, user-level restrictions
- **ACL Files**: `security/ir.model.access.csv` in all modules
- **Credentials**: Never hardcoded, always env vars

## Compliance

### Odoo 19 Patterns Enforced
- ✅ No `_sql_constraints` (use `models.Constraint`)
- ✅ No `@api.depends("id")`
- ✅ No `@api.one` / `@api.multi`
- ✅ No `category_id` on `res.groups`
- ✅ No `numbercall` on `ir.cron`

### Pre-Commit Checks
- Ruff (linting + formatting)
- Odoo pattern validation
- Module wiring checks
- XML/YAML validation

## Known Issues & Constraints


2. **Partner Import**: Requires facility role field verification
3. **Neo4j Integration**: Must not block Odoo registry load
4. **Graph Sync**: Outbox pattern not yet implemented (planned)

## Roadmap

See [`ROADMAP.md`](./ROADMAP.md)

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md)

## License

LGPL-3

## Contact

PlasticOS Development Team
