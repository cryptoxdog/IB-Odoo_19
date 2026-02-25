# DEPLOYMENT.md — PlasticOS Deployment Guide

**Repository**: cryptoxdog/IB-Odoo_19
**Odoo Version**: 19.0
**Target Platforms**: Docker, Odoo.sh

## Overview

PlasticOS supports two primary deployment strategies:

1. **Docker-based deployment** (local development, self-hosted production)
2. **Odoo.sh deployment** (managed cloud hosting)

Both require PostgreSQL and optionally Neo4j for graph-based buyer matching.

---

## Docker Deployment

### Prerequisites

- Docker 24.0+
- Docker Compose 2.0+
- 4GB RAM minimum (8GB recommended)
- 20GB disk space

### Configuration Files

**Dockerfile**:
```dockerfile
# PlasticOS Odoo 19 with custom Python dependencies
FROM odoo:19

USER root

# Install Python dependencies from requirements.txt
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed \
    -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

USER odoo
```

**requirements.txt**:
```
neo4j>=5.0.0
openai>=1.0.0
requests>=2.28.0
```

**docker-compose.prod.yml** (Expected, not found in repo):
```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-odoo}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB:-odoo}
    volumes:
      - odoo-db-data:/var/lib/postgresql/data
    restart: unless-stopped

  odoo:
    build: .
    depends_on:
      - db
      - neo4j
    ports:
      - "8069:8069"
    environment:
      - HOST=db
      - USER=${POSTGRES_USER:-odoo}
      - PASSWORD=${POSTGRES_PASSWORD}
      - DATABASE=${POSTGRES_DB:-odoo}
      - NEO4J_URI=${NEO4J_URI:-bolt://neo4j:7687}
      - NEO4J_USER=${NEO4J_USER:-neo4j}
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./plasticos_*:/mnt/extra-addons
      - odoo-web-data:/var/lib/odoo
      - odoo-config:/etc/odoo
    restart: unless-stopped

  neo4j:
    image: neo4j:5.15-community
    ports:
      - "7474:7474"  # Browser UI
      - "7687:7687"  # Bolt protocol
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
    volumes:
      - neo4j-data:/data
      - neo4j-logs:/logs
    restart: unless-stopped

volumes:
  odoo-db-data:
  odoo-web-data:
  odoo-config:
  neo4j-data:
  neo4j-logs:
```

### Environment Setup

**Create `.env` file**:
```bash
# PostgreSQL
POSTGRES_USER=odoo
POSTGRES_PASSWORD=<strong_password>
POSTGRES_DB=odoo

# Neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=<strong_password_min_8_chars>
NEO4J_URI=bolt://neo4j:7687

# OpenAI (optional, for web lead triage)
OPENAI_API_KEY=sk-...

# Odoo
ODOO_DB_HOST=db
ODOO_DB_PORT=5432
```

**⚠️ Security**: Never commit `.env` to version control.

### Deployment Steps

#### 1. Build Custom Image
```bash
docker build -t plasticos-odoo:19 .
```

#### 2. Start Infrastructure
```bash
docker compose -p plasticos_prod -f docker-compose.prod.yml up -d
```

#### 3. Initialize Neo4j
```bash
./scripts/setup_neo4j.sh
```

**Script performs**:
- Starts Neo4j container
- Waits for readiness (30-60 seconds)
- Verifies connection
- Displays browser UI URL: http://localhost:7474

#### 4. Initialize Odoo Database
```bash
docker compose -p plasticos_prod exec odoo odoo-bin \
  -d odoo \
  --init=plasticos_base,plasticos_material_profile,plasticos_facility_profile,plasticos_intake,plasticos_transaction \
  --stop-after-init
```

#### 5. Start Odoo
```bash
docker compose -p plasticos_prod -f docker-compose.prod.yml up -d odoo
```

#### 6. Sync Graph Schema
```bash
./scripts/setup_neo4j.sh --init-schema
```

**Script performs**:
- Initializes Neo4j schema (indexes, constraints)
- Syncs facility nodes from `plasticos.facility.profile`
- Syncs material nodes from `plasticos.material.profile`

#### 7. Verify Deployment
```bash
# Check all services
docker compose -p plasticos_prod ps

# Check Odoo logs
docker compose -p plasticos_prod logs odoo -f

# Test Neo4j connection
./scripts/setup_neo4j.sh --test
```

### Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| Odoo | http://localhost:8069 | admin / admin (change immediately) |
| Neo4j Browser | http://localhost:7474 | neo4j / (from .env) |
| PostgreSQL | localhost:5432 | (from .env) |

### Module Installation Order

**Enforced by dependencies** (`config/odoo_module_order.yaml`):

```yaml
install_order:
  - plasticos_security_base
  - plasticos_geolocalize
  - plasticos_base
  - plasticos_accounting
  - plasticos_material_profile
  - plasticos_facility_profile
  - plasticos_product
  - plasticos_enrichment
  - plasticos_inference_engine
  - plasticos_partner_import
  - plasticos_intake
  - plasticos_intake_normalizer
  - plasticos_matching
  - plasticos_logistics
  - plasticos_order_lines
  - plasticos_transaction
  - plasticos_buyer_match_engine
  - plasticos_offer
  - plasticos_web_leads
  - plasticos_documents
  - plasticos_documents_native
  - plasticos_claims
  - plasticos_automation
  - plasticos_dev_tools
```

### Post-Deployment Configuration

#### 1. Create Company
- Navigate to **Settings > Companies**
- Create company with legal details
- Set fiscal year, currency, timezone

#### 2. Configure Sales Reps
- Navigate to **Sales > Sales Teams**
- Assign users to teams
- Set quotas and targets

#### 3. Import Partners
- Navigate to **Contacts > Import**
- Use `plasticos_partner_import` wizard
- Verify facility profiles created

#### 4. Enable Crons
- Navigate to **Settings > Technical > Automation > Scheduled Actions**
- Enable required crons (all disabled by default):
  - Buyer matching sync
  - Document expiry check
  - Load SLA monitoring
  - Invoice reminders

#### 5. Test Matching Engine
- Create test intake
- Click "Match To Buyers"
- Verify Neo4j results in `plasticos.match.result`

---

## Odoo.sh Deployment

### Prerequisites

- Odoo.sh subscription (Starter or higher)
- GitHub repository access
- SSH key configured

### Repository Setup

**Branch Strategy**:
- `main` → Production
- `staging` → Staging/UAT
- `development` → Development

**requirements.txt** (root of repo):
```
neo4j>=5.0.0
openai>=1.0.0
requests>=2.28.0
```

### Odoo.sh Configuration

#### 1. Connect Repository
- Log in to Odoo.sh
- Click "New Project"
- Connect GitHub repository: `cryptoxdog/IB-Odoo_19`
- Select branch: `staging` (default)

#### 2. Configure Environment Variables
Navigate to **Settings > Environment Variables**:

```
NEO4J_URI=bolt://<neo4j_host>:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<secure_password>
OPENAI_API_KEY=sk-...
```

**⚠️ Neo4j External Hosting Required**: Odoo.sh does not support custom Docker containers. Use:
- Neo4j Aura (managed Neo4j cloud)
- External Neo4j server
- Or disable graph matching (Python-only fallback)

#### 3. Deploy
- Push to `staging` branch
- Odoo.sh automatically:
  - Installs dependencies from `requirements.txt`
  - Creates database
  - Installs modules (via `--init` flag or UI)
  - Runs CI tests

#### 4. Install Modules
- Via UI: **Apps > Search "plasticos" > Install**
- Via command line (Odoo.sh shell):
```bash
odoo-bin -d <db_name> --init=plasticos_base,plasticos_material_profile --stop-after-init
```

#### 5. Sync Graph (if Neo4j external)
- Access Odoo.sh shell
- Run Python script:
```python
graph_service = env['plasticos.graph.service']
graph_service.initialize_schema()
graph_service.sync_facility_nodes(trigger='odoo_sh_deploy')
graph_service.sync_material_nodes(trigger='odoo_sh_deploy')
env.cr.commit()
```

### CI/CD on Odoo.sh

**Automatic Test Execution**:
- Runs on every push to tracked branch
- Uses test database
- 52 tests currently passing

**Disabled for CI** (require production seed data):
- `plasticos_enrichment` tests
- `plasticos_dev_tools` tests

**Test Command**:
```bash
odoo-bin -d test_db --test-enable --stop-after-init
```

### Staging → Production Promotion

1. Verify staging environment stable
2. Merge `staging` → `main` via GitHub PR
3. Odoo.sh auto-deploys to production
4. Monitor logs for errors
5. Test critical paths:
   - Create intake
   - Match to buyers
   - Create transaction
   - Generate load

---

## Rollback Procedures

### Docker Rollback

**Database Backup** (before deployment):
```bash
docker compose -p plasticos_prod exec db pg_dump -U odoo odoo > backup_$(date +%Y%m%d_%H%M%S).sql
```

**Restore**:
```bash
docker compose -p plasticos_prod exec -T db psql -U odoo odoo < backup_20260224_120000.sql
```

**Code Rollback**:
```bash
git checkout <previous_commit>
docker compose -p plasticos_prod down
docker compose -p plasticos_prod up -d --build
```

### Odoo.sh Rollback

1. Navigate to **Builds** in Odoo.sh dashboard
2. Find previous stable build
3. Click "Restore"
4. Confirm database restore point

---

## Monitoring

### Docker Health Checks

**Check Service Status**:
```bash
docker compose -p plasticos_prod ps
```

**View Logs**:
```bash
# All services
docker compose -p plasticos_prod logs -f

# Odoo only
docker compose -p plasticos_prod logs odoo -f --tail=100

# Neo4j only
docker compose -p plasticos_prod logs neo4j -f --tail=100
```

**Check Neo4j Health**:
```bash
./scripts/setup_neo4j.sh --check
```

### Odoo.sh Monitoring

- Built-in metrics dashboard
- Email alerts on errors
- Automatic daily backups

### Application Monitoring

**Key Metrics**:
- Transaction creation rate
- Match success rate (intake → offer conversion)
- Load fulfillment time
- Document compliance rate
- Neo4j query latency

**Log Levels**:
- `INFO`: Normal operations
- `WARNING`: Non-critical issues (API fallback, etc.)
- `ERROR`: Critical failures requiring attention

---

## Scaling Considerations

### Vertical Scaling
- **Database**: Increase PostgreSQL memory (`shared_buffers`, `work_mem`)
- **Odoo**: Increase workers (`--workers=4`)
- **Neo4j**: Increase heap size (`NEO4J_dbms_memory_heap_max__size=4G`)

### Horizontal Scaling
- **Odoo**: Multiple Odoo containers behind load balancer
- **Neo4j**: Neo4j Enterprise cluster (requires license)
- **PostgreSQL**: Read replicas for reporting

### Performance Tuning

**PostgreSQL**:
```sql
-- Add indexes
CREATE INDEX idx_transaction_state ON plasticos_transaction(state);
CREATE INDEX idx_intake_polymer ON plasticos_intake(polymer_id);
```

**Neo4j**:
```cypher
// Create indexes
CREATE INDEX facility_partner_id IF NOT EXISTS FOR (f:Facility) ON (f.partner_id);
CREATE INDEX material_polymer IF NOT EXISTS FOR (m:Material) ON (m.polymer);
```

---

## Security Hardening

### Production Checklist

- [ ] Change default `admin` password
- [ ] Disable demo/test accounts
- [ ] Enable SSL/TLS (use reverse proxy)
- [ ] Restrict database access (firewall rules)
- [ ] Rotate API keys regularly
- [ ] Enable Odoo audit log
- [ ] Configure backup retention policy
- [ ] Set up monitoring alerts
- [ ] Review ACL permissions
- [ ] Disable unnecessary modules

### SSL/TLS Configuration

**Nginx Reverse Proxy** (recommended):
```nginx
server {
    listen 443 ssl http2;
    server_name plasticos.example.com;

    ssl_certificate /etc/ssl/certs/plasticos.crt;
    ssl_certificate_key /etc/ssl/private/plasticos.key;

    location / {
        proxy_pass http://localhost:8069;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Troubleshooting

### Common Issues

#### Odoo Won't Start
```bash
# Check logs
docker compose -p plasticos_prod logs odoo

# Common causes:
# - Database connection failed (check POSTGRES_PASSWORD)
# - Module dependency error (check __manifest__.py)
# - Port conflict (check if 8069 already in use)
```

#### Neo4j Connection Failed
```bash
# Verify Neo4j running
./scripts/setup_neo4j.sh --check

# Test from Odoo
./scripts/setup_neo4j.sh --test

# Common causes:
# - NEO4J_URI incorrect (use bolt://neo4j:7687 from Docker network)
# - Password mismatch (check .env)
# - Neo4j not fully started (wait 60 seconds)
```

#### Module Load Error
```bash
# Check module wiring
./scripts/check_module_wiring.py

# Common causes:
# - Missing dependency in __manifest__.py
# - Typo in model name or external ID
# - Circular dependency
```

#### Graph Sync Failing
```bash
# Check Neo4j schema
docker compose exec neo4j cypher-shell -u neo4j -p <password> "SHOW INDEXES"

# Reinitialize schema
./scripts/setup_neo4j.sh --init-schema
```

---

**Deployment Guide Version**: 1.0.0
**Last Updated**: 2026-02-24
**Verified On**: Docker 24.0, Odoo.sh (2026-02 release)
