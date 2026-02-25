# QUICK_START.md — Get PlasticOS Running in 5 Minutes

**For**: Developers who want to try PlasticOS immediately
**Time**: 5 minutes to running system

---

## 🚀 Option 1: Docker (Recommended)

### Prerequisites Check

```bash
docker --version  # Requires 24.0+
docker compose version  # Requires 2.0+
```

### One-Command Startup

```bash
# Clone and start
git clone https://github.com/cryptoxdog/IB-Odoo_19.git
cd IB-Odoo_19
cp .env.example .env
docker build -t plasticos-odoo:19 .
docker compose -p plasticos up -d

# Wait 60 seconds for services to initialize
sleep 60

# Initialize Neo4j (optional but recommended)
./scripts/setup_neo4j.sh
```

### Access

- **Odoo**: http://localhost:8069
- **Neo4j Browser**: http://localhost:7474
- **Default Login**: admin / admin (change immediately!)

---

## 🐍 Option 2: Python Virtual Environment

### Prerequisites

```bash
python3.12 --version  # Requires 3.12+
pip install -r requirements.txt
```

### Setup

```bash
# 1. Install Odoo dependencies
pip install -r requirements.txt

# 2. Create database
createdb odoo

# 3. Initialize Odoo
odoo-bin -d odoo --init=plasticos_base,plasticos_material_profile,plasticos_transaction --stop-after-init

# 4. Start Odoo
odoo-bin -d odoo
```

### Access

- **Odoo**: http://localhost:8069
- **Default Login**: admin / admin

---

## ✅ Verify Installation

### Check Services

```bash
# Docker
docker compose ps

# Should show: db (postgres), odoo, neo4j (all Up)
```

### Test Core Functions

1. **Create Intake**:
   - Navigate to **Intake > Create**
   - Fill: Supplier, Polymer (HDPE), Quantity (10000 lbs)
   - Click **Save**

2. **Match to Buyers**:
   - Click **Match to Buyers** button
   - Verify results appear (may be empty if no buyers configured)

3. **Create Transaction**:
   - Navigate to **Transactions > Create**
   - Fill: Buyer, Supplier, Quantity, Prices
   - Click **Save**
   - Verify commission calculated

---

## 📦 Install Additional Modules

### Via UI

1. Navigate to **Apps**
2. Remove "Apps" filter
3. Search "plasticos"
4. Click **Install** on desired modules

### Via Command Line

```bash
odoo-bin -d odoo -u plasticos_logistics,plasticos_documents --stop-after-init
```

**Recommended Modules**:
- `plasticos_logistics` — Load management
- `plasticos_documents` — Compliance tracking
- `plasticos_web_leads` — AI triage (requires OPENAI_API_KEY)
- `plasticos_buyer_match_engine` — Graph matching (requires Neo4j)

---

## 🐛 Troubleshooting

### Odoo Won't Start

```bash
# Check logs
docker compose logs odoo --tail=100

# Common issues:
# - Port 8069 in use: Change in docker-compose.yml
# - Database connection: Check POSTGRES_PASSWORD in .env
```

### Neo4j Connection Failed

```bash
# Check Neo4j status
./scripts/setup_neo4j.sh --check

# If not running:
docker compose restart neo4j
sleep 60
```

### Module Install Error

```bash
# Check module dependencies
./scripts/check_module_wiring.py

# Common fix: Install dependencies first
odoo-bin -d odoo -u plasticos_base,plasticos_material_profile --stop-after-init
```

---

## 📚 Next Steps

1. **Configure Master Data**:
   - Import partners: **Contacts > Import**
   - Set up polymers: **Material Profile > Polymers**
   - Configure equipment types: **Facility Profile > Equipment Types**

2. **Read Documentation**:
   - [ARCHITECTURE.md](docs/ARCHITECTURE.md) — System overview
   - [WORKFLOW_GUIDE.md](docs/WORKFLOW_GUIDE.md) — User workflows
   - [API_REFERENCE.md](docs/API_REFERENCE.md) — Developer API

3. **Run Tests**:
   ```bash
   ./scripts/run-odoo-tests.sh
   ```

4. **Join Community**:
   - [GitHub Discussions](https://github.com/cryptoxdog/IB-Odoo_19/discussions)

---

**Got Issues?** Open a [GitHub Issue](https://github.com/cryptoxdog/IB-Odoo_19/issues) with logs attached.

*Last Updated: 2026-02-24*
