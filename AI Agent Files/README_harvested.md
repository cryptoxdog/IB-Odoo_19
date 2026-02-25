# PlasticOS — Plastics Recycling Supply Chain Platform

**Odoo 19.0 Enterprise Application**
**Repository**: [cryptoxdog/IB-Odoo_19](https://github.com/cryptoxdog/IB-Odoo_19)

[![Odoo Version](https://img.shields.io/badge/Odoo-19.0-714B67)](https://www.odoo.com)
[![Python Version](https://img.shields.io/badge/Python-3.12-3776AB)](https://www.python.org)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.15-008CC1)](https://neo4j.com)
[![License](https://img.shields.io/badge/License-Proprietary-red)](LICENSE)

---

## 🚀 Quick Start

### Docker Deployment (Recommended)

```bash
# 1. Clone repository
git clone https://github.com/cryptoxdog/IB-Odoo_19.git
cd IB-Odoo_19

# 2. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 3. Build and start services
docker build -t plasticos-odoo:19 .
docker compose -p plasticos_prod -f docker-compose.prod.yml up -d

# 4. Initialize Neo4j
./scripts/setup_neo4j.sh

# 5. Access Odoo
# Navigate to: http://localhost:8069
# Default credentials: admin / admin (change immediately!)
```

**⚠️ Production Deployment**: See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for SSL, backups, and security hardening.

---

## 📚 What is PlasticOS?

PlasticOS is an **end-to-end supply chain management platform** for the plastics recycling industry, built on Odoo 19. It automates the entire workflow from supplier intake to buyer fulfillment, with AI-powered matching and compliance tracking.

### Key Features

✅ **Material Intake Management** — Normalize supplier leads with AI
✅ **Graph-Based Buyer Matching** — Neo4j-powered compatibility engine (14 hard gates, 9 soft signals)
✅ **Transaction Management** — Commission tracking, cieTrade import
✅ **Logistics Coordination** — Load management, BOL generation, carrier dispatch
✅ **Compliance Automation** — Document validation, expiry tracking
✅ **Web Lead Triage** — GPT-4o classification (HOT/WARM/COLD)

---

## 🏗️ Architecture

PlasticOS is organized into **5 architectural layers** with **23 core modules**:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 5: TRANSACTION (Revenue Recognition)                  │
│  plasticos_transaction, plasticos_logistics                 │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: COMPLIANCE (Risk Management)                       │
│  plasticos_documents, plasticos_claims                      │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: COMMERCIAL (Deal Lifecycle)                        │
│  plasticos_offer, plasticos_buyer_match_engine              │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: CAPABILITY (Facility Profiles)                     │
│  plasticos_facility_profile, plasticos_matching             │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: MATERIAL (Master Data)                             │
│  plasticos_material_profile, plasticos_intake               │
└─────────────────────────────────────────────────────────────┘
```

**Full module map**: See [ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 🔥 Core Workflows

### 1. Supplier Intake → Buyer Match → Transaction

```
Web Lead (GPT-4o Triage)
    ↓
Intake (Normalize with AI)
    ↓
Match to Buyers (Neo4j Graph)
    ↓
Create Offer (Price Negotiation)
    ↓
Accept Offer → Transaction
    ↓
Generate Load (Logistics)
    ↓
Invoicing & Settlement
```

### 2. Two-Stage Buyer Matching (v2.0)

```
Stage 1: Capability Matcher (Python)
  -  Deterministic hard gates (polymer/form/source exact match)
  -  Quality gates (contamination, moisture)
  -  Volume gates (min/max lot size)
  -  Geographic filtering (per-buyer radius)
  → Output: Candidate facilities (10-50 buyers)

Stage 2: Graph Service (Neo4j Cypher)
  -  Range-based gates (MFI, density)
  -  Equipment capability gates (washline, extruder)
  -  Soft signals (color match, packaging match)
  -  Transaction history bonus
  → Output: Ranked buyers with composite scores
```

**Matching Logic**: See [CYPHER_BUYER_MATCH_LOGIC.md](plasticos_buyer_match_engine/doc/CYPHER_BUYER_MATCH_LOGIC.md)

---

## 🛠️ Technology Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Framework** | Odoo | 19.0 | ERP backend |
| **Language** | Python | 3.12 | Business logic |
| **Database** | PostgreSQL | 15+ | Relational data |
| **Graph DB** | Neo4j | 5.15+ | Buyer matching |
| **AI** | OpenAI GPT-4o | Latest | Web lead triage |
| **Containerization** | Docker | 24.0+ | Deployment |

---

## 📦 Installation

### Prerequisites

- Docker 24.0+ and Docker Compose 2.0+
- 4GB RAM minimum (8GB recommended)
- 20GB disk space
- PostgreSQL 15+ (or use Docker)
- Neo4j 5.15+ (optional, Python fallback available)

### Local Development Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure Odoo
cp config/odoo.conf.example config/odoo.conf
# Edit config/odoo.conf with database credentials

# 3. Initialize database
odoo-bin -c config/odoo.conf -d odoo --init=plasticos_base --stop-after-init

# 4. Start Odoo
odoo-bin -c config/odoo.conf -d odoo

# 5. Install modules via UI
# Navigate to Apps > Search "plasticos" > Install
```

### Module Installation Order

**Automatic**: Dependencies enforced via `__manifest__.py`

**Manual** (if needed):
```bash
./scripts/get_odoo_module_order.py
# Or reference: config/odoo_module_order.yaml
```

**Critical Modules** (install first):
1. `plasticos_security_base` — RBAC groups
2. `plasticos_base` — Taxonomy and master data
3. `plasticos_material_profile` — Polymer/form/color
4. `plasticos_facility_profile` — Equipment types
5. `plasticos_intake` — Intake management
6. `plasticos_transaction` — Transaction tracking

---

## 🧪 Testing

### Run All Tests

```bash
./scripts/run-odoo-tests.sh
```

### Run Specific Module Tests

```bash
odoo-bin -d odoo_test --test-enable --test-tags /plasticos_transaction/tests --stop-after-init
```

### Test Coverage

- **Total Tests**: 52 passing
- **Modules Tested**: `plasticos_transaction` (47), `plasticos_buyer_match_engine` (5)
- **Coverage Target**: 80% for core modules

**Test Strategy**: See [TEST_STRATEGY.md](docs/TEST_STRATEGY.md)

---

## 📖 Documentation

### Core Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, layer model, module map |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker, Odoo.sh, SSL, monitoring |
| [API_REFERENCE.md](docs/API_REFERENCE.md) | Public APIs, Python SDK, webhooks |
| [DATA_MODEL.md](docs/DATA_MODEL.md) | Database schema, ERD, relationships |
| [SECURITY_MODEL.md](docs/SECURITY_MODEL.md) | RBAC, ACL, record rules, multi-company |
| [MIGRATION_GUIDE.md](docs/MIGRATION_GUIDE.md) | Version upgrades, schema changes |
| [TEST_STRATEGY.md](docs/TEST_STRATEGY.md) | Testing approach, coverage targets |

### Module-Specific Guides

| Module | Guide |
|--------|-------|
| `plasticos_transaction` | [GUIDE.md](plasticos_transaction/GUIDE.md) |
| `plasticos_buyer_match_engine` | [CYPHER_BUYER_MATCH_LOGIC.md](plasticos_buyer_match_engine/doc/CYPHER_BUYER_MATCH_LOGIC.md) |
| `plasticos_intake` | [Intake README](plasticos_intake/README.rst) |
| `plasticos_web_leads` | [Web Leads README](plasticos_web_leads/README.rst) |

### Quick Reference

- **Module List**: [reports/READMEODOOINDEX.md](reports/READMEODOOINDEX.md)
- **Bug Fixes**: [reports/BUGFIXESSUMMARY.md](reports/BUGFIXESSUMMARY.md)
- **Gap Analysis**: [reports/GAPANALYSISANDCONSOLIDATION.md](reports/GAPANALYSISANDCONSOLIDATION.md)
- **Workflow State**: [workflow_state.md](workflow_state.md)

---

## 🔐 Security

### Production Checklist

- [ ] Change default `admin` password immediately
- [ ] Enable SSL/TLS (use reverse proxy like Nginx)
- [ ] Restrict database access (firewall rules)
- [ ] Rotate API keys every 90 days
- [ ] Enable Odoo audit log
- [ ] Configure backup retention policy
- [ ] Set up monitoring alerts
- [ ] Review ACL permissions for each module
- [ ] Disable unnecessary modules
- [ ] Enable MFA for admin accounts

**Security Model**: See [SECURITY_MODEL.md](docs/SECURITY_MODEL.md)

---

## 🐛 Troubleshooting

### Common Issues

**Odoo won't start**:
```bash
# Check logs
docker compose -p plasticos_prod logs odoo

# Common causes:
# - Database connection failed (check POSTGRES_PASSWORD in .env)
# - Port 8069 already in use
# - Module dependency error
```

**Neo4j connection failed**:
```bash
# Verify Neo4j running
./scripts/setup_neo4j.sh --check

# Test from Odoo
./scripts/setup_neo4j.sh --test
```

**Module load error**:
```bash
# Check module wiring
./scripts/check_module_wiring.py

# Common causes:
# - Missing dependency in __manifest__.py
# - Circular dependency
# - Field referenced before defined
```

**Full Troubleshooting**: See [DEPLOYMENT.md#Troubleshooting](docs/DEPLOYMENT.md#troubleshooting)

---

## 🤝 Contributing

### Development Workflow

1. **Create feature branch**:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make changes** and test locally:
   ```bash
   ./scripts/run-odoo-tests.sh
   ./scripts/check_odoo_patterns.sh
   ```

3. **Commit with conventional commits**:
   ```bash
   git commit -m "feat(intake): add lazy partner creation"
   ```

4. **Push and create PR**:
   ```bash
   git push origin feature/my-new-feature
   # Create PR in GitHub
   ```

### Code Standards

- **Python**: Follows PEP 8, enforced by Ruff
- **Odoo**: Follows OCA guidelines
- **Commit Messages**: Conventional Commits format
- **Pre-commit**: Runs linters, pattern checks

**Linting**:
```bash
ruff check .
ruff format .
```

---

## 📊 Project Status

### Current State (2026-02-24)

- ✅ **93 modules** installed successfully
- ✅ **52 tests** passing (transaction, matching)
- ✅ **Two-stage matching** implemented (Capability Matcher + Graph Service)
- ✅ **CI/CD** configured for Odoo.sh
- ✅ **Documentation** complete (10+ guides)
- 🚧 **Production deployment** (Docker ready, awaiting SSL configuration)
- 🚧 **Additional tests** (enrichment, logistics, documents)

### Roadmap

**Q1 2026**:
- [ ] Complete test coverage (80% target)
- [ ] Production deployment to Odoo.sh
- [ ] Mobile app for logistics dispatch
- [ ] Real-time load tracking dashboard

**Q2 2026**:
- [ ] Filler science integration (talc/CaCO3/GF routing)
- [ ] Application class taxonomy (pallet/food/automotive)
- [ ] Property degradation tracking (recycle cycles)
- [ ] Advanced analytics (Power BI/Looker)

---

## 📄 License

**Proprietary** — All rights reserved.

This software is proprietary and confidential. Unauthorized copying, distribution, or modification is strictly prohibited.

---

## 🙏 Acknowledgments

- **Odoo Community**: For the incredible ERP framework
- **Neo4j**: For graph database technology
- **OpenAI**: For GPT-4o AI capabilities
- **Contributors**: Igor Beylin, Cursor AI

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/cryptoxdog/IB-Odoo_19/issues)
- **Email**: ib718@icloud.com
- **Documentation**: [docs/](docs/)

---

**PlasticOS** — Transforming plastics recycling through intelligent automation.

*Last Updated: 2026-02-24*
