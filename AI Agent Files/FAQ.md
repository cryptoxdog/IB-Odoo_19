# FAQ.md — Frequently Asked Questions

**Last Updated**: 2026-02-24

---

## General Questions

### What is PlasticOS?

PlasticOS is an **end-to-end supply chain management platform** for the plastics recycling industry, built on Odoo 19. It automates the workflow from supplier intake to buyer fulfillment with AI-powered matching and compliance tracking.

### Who is PlasticOS for?

- **Plastics brokers** managing supplier-buyer relationships
- **Recycling companies** coordinating material flows
- **Manufacturing facilities** sourcing recycled materials
- **Logistics coordinators** managing shipments

### What does PlasticOS cost?

PlasticOS is **proprietary software** (not open source). Contact ib718@icloud.com for licensing information.

### What's the difference between PlasticOS and other ERP systems?

PlasticOS is **purpose-built for plastics recycling**, with domain-specific features:
- Material taxonomy (polymers, forms, colors, grades)
- Graph-based buyer matching (Neo4j)
- Compliance document validation
- AI-powered lead triage and normalization
- Logistics coordination for bulk materials

Generic ERPs (SAP, NetSuite, etc.) lack this vertical specialization.

---

## Technical Questions

### What version of Odoo does PlasticOS use?

**Odoo 19.0** (Community Edition as base, with custom modules).

### Can PlasticOS run on Odoo 18 or earlier?

**No**. PlasticOS uses Odoo 19-specific features:
- `@api.model_create_multi` decorator
- Updated search view syntax
- New privilege model (`plasticos_privilege_*` groups)

Backporting to Odoo 18 would require significant refactoring.

### Does PlasticOS require Neo4j?

**No, but highly recommended**. Neo4j enables advanced buyer matching with:
- 14 hard gates (must-haves)
- 9 soft signals (preferences)
- Transaction history bonus
- Geographic proximity scoring

Without Neo4j, PlasticOS falls back to **Python-only matching** with 10 gates (less sophisticated).

### Can I use PlasticOS without OpenAI API?

**Yes**. OpenAI (GPT-4o) is optional for:
- Web lead triage (HOT/WARM/COLD classification)
- Material normalization (text → structured data)

Without OpenAI, leads are marked **COLD** for manual review.

### What databases are supported?

- **PostgreSQL 15+** (required for Odoo)
- **Neo4j 5.15+** (optional for graph matching)

SQLite, MySQL, and other databases are **not supported**.

### Can PlasticOS run on Windows?

**Yes**, but **Docker on Linux/macOS is recommended** for production.

Windows compatibility:
- ✅ Odoo runs on Windows
- ❌ Some shell scripts require WSL (Windows Subsystem for Linux)
- ❌ Performance may be slower than Linux

---

## Installation & Setup

### How long does installation take?

- **Docker (recommended)**: 5 minutes
- **Manual Python setup**: 15 minutes
- **Production deployment (Odoo.sh)**: 30 minutes

### Do I need to install modules in a specific order?

**No**. Module dependencies are declared in `__manifest__.py` and enforced automatically by Odoo.

However, **recommended installation order** for manual installs:
1. `plasticos_security_base`
2. `plasticos_base`
3. `plasticos_material_profile`
4. `plasticos_facility_profile`
5. `plasticos_intake`
6. `plasticos_transaction`

### Can I install only some modules?

**Yes**. Modules are modular and optional. However, **core dependencies** must be installed:
- `plasticos_base` (required by all modules)
- `plasticos_security_base` (required for RBAC)

### How do I update modules after code changes?

```bash
# Docker
docker compose exec odoo odoo-bin -d odoo -u plasticos_transaction --stop-after-init

# Local
odoo-bin -d odoo -u plasticos_transaction --stop-after-init

# Or use convenience script
./scripts/rebuild-odoo-modules.sh
```

---

## Usage Questions

### How do I create my first intake?

1. Navigate to **Intake > Create**
2. Fill required fields:
   - **Supplier** (res.partner with `supplier_rank > 0`)
   - **Polymer** (e.g., HDPE)
   - **Quantity** (lbs)
3. Optional: Fill form, color, source type
4. Click **Save**
5. Click **Match to Buyers** to find compatible buyers

### How does buyer matching work?

**Two-stage process** (v2.0):

**Stage 1: Capability Matcher (Python)**
- Filters buyers using deterministic hard gates
- Checks polymer, form, source type (exact match)
- Applies quality gates (contamination, moisture)
- Applies volume gates (min/max lot size)
- Applies geographic filtering (per-buyer radius)
- **Output**: 10-50 candidate facilities

**Stage 2: Graph Service (Neo4j Cypher)**
- Ranks candidates using soft signals
- Applies range-based gates (MFI, density)
- Checks equipment capabilities (washline, extruder)
- Scores color match, packaging match
- Adds transaction history bonus
- **Output**: Ranked buyers with composite scores (0-1000)

See [CYPHER_BUYER_MATCH_LOGIC.md](plasticos_buyer_match_engine/doc/CYPHER_BUYER_MATCH_LOGIC.md) for details.

### Why are my match results empty?

**Common causes**:
1. **No buyers configured**: Add facility profiles via **Facility Profile > Create**
2. **Too restrictive gates**: Check contamination tolerance, lot size constraints
3. **Geographic filter**: Increase radius or add buyer lat/lon
4. **PVC contamination**: PVC is zero-tolerance for most buyers
5. **Neo4j not running**: Check with `./scripts/setup_neo4j.sh --check`

**Debug**:
```python
# Odoo shell
env['plasticos.graph.service'].match_buyers_for_intake(intake)
# Check logs for gate failures
```

### How do I import partners from CSV?

1. Navigate to **Contacts > Import Partners**
2. Upload CSV files:
   - `corporate.csv` (companies)
   - `facilities.csv` (physical locations)
3. Click **Run Import**
4. Review **Audit Import** for errors
5. Click **Repair Import** to fix common issues

See [MIGRATION_GUIDE.md](docs/MIGRATION_GUIDE.md) for CSV format.

### How do I create a transaction from an intake?

**Manual**:
1. Navigate to intake
2. Click **Create Offer** (if buyer matched)
3. Buyer accepts offer
4. Transaction auto-created

**Direct**:
1. Navigate to **Transactions > Create**
2. Fill buyer, supplier, quantity, prices
3. Commission auto-calculated

### How do I generate a load (BOL)?

1. Navigate to transaction
2. Click **Generate Load**
3. Fill pickup/delivery details
4. Click **Confirm Dispatch**
5. Print BOL: **Actions > Print BOL (Pickup)**

---

## Troubleshooting

### Odoo won't start — "Port 8069 already in use"

**Solution 1**: Stop other Odoo instance
```bash
sudo lsof -i :8069  # Find process
sudo kill -9 <PID>  # Kill process
```

**Solution 2**: Change port
```bash
# In docker-compose.yml
ports:
  - "8070:8069"  # Change 8069 → 8070
```

### Module install error — "Field X does not exist"

**Cause**: Field referenced before model loaded (dependency order issue).

**Solution**:
1. Check `__manifest__.py` dependencies
2. Install dependencies first:
   ```bash
   odoo-bin -d odoo -i plasticos_base,plasticos_material_profile --stop-after-init
   ```
3. Then install your module

### Neo4j connection failed

**Check Neo4j status**:
```bash
./scripts/setup_neo4j.sh --check
```

**If not running**:
```bash
docker compose restart neo4j
sleep 60  # Wait for startup
```

**Verify credentials**:
```bash
# Check .env
cat .env | grep NEO4J

# Test connection
./scripts/setup_neo4j.sh --test
```

### "Graph sync skipped" warnings in logs

**Cause**: Neo4j unavailable (this is **non-blocking**).

**Impact**: Buyer matching falls back to Python-only (10 gates instead of 14+9 signals).

**Solution**:
1. Start Neo4j: `docker compose up -d neo4j`
2. Initialize schema: `./scripts/setup_neo4j.sh --init-schema`
3. Retry intake matching

### Tests failing — "plasticos.polymer not found"

**Cause**: Test database missing seed data.

**Solution**:
```bash
# Recreate test database with seed data
dropdb odoo_test
createdb odoo_test
odoo-bin -d odoo_test --init=plasticos_material_profile --stop-after-init

# Run tests
./scripts/run-odoo-tests.sh
```

---

## Performance Questions

### How fast is buyer matching?

**Current performance** (Q1 2026):
- **Stage 1 (Capability Matcher)**: < 500ms for 1000 buyers
- **Stage 2 (Graph Service)**: < 2s for 50 candidates
- **Total**: < 2.5s end-to-end

**Target performance** (Q2 2026):
- **Total**: < 1s (p99)

### How many transactions can PlasticOS handle?

**Current capacity**:
- **Transactions**: 10,000+ per month
- **Intakes**: 50,000+ per month
- **Partners**: 100,000+

**Scalability**:
- Horizontal scaling (multiple Odoo workers)
- PostgreSQL read replicas for reporting
- Neo4j Enterprise clustering (requires license)

### How do I optimize database performance?

**PostgreSQL tuning**:
```sql
-- Add indexes for slow queries
CREATE INDEX idx_transaction_state ON plasticos_transaction(state);
CREATE INDEX idx_intake_polymer ON plasticos_intake(polymer_id);
```

**Neo4j tuning**:
```cypher
// Add indexes for graph queries
CREATE INDEX facility_partner_id IF NOT EXISTS FOR (f:Facility) ON (f.partner_id);
CREATE INDEX material_polymer IF NOT EXISTS FOR (m:Material) ON (m.polymer);
```

See [DEPLOYMENT.md#Performance Tuning](docs/DEPLOYMENT.md#performance-tuning) for more.

---

## Security Questions

### How do I reset the admin password?

**Docker**:
```bash
docker compose exec odoo odoo-bin -d odoo --db-filter=^odoo$ shell

# In Python shell
env['res.users'].browse(2).write({'password': 'new_password'})
env.cr.commit()
```

**Local**:
```bash
odoo-bin -d odoo shell

# Same Python commands as above
```

### What's the difference between groups and record rules?

| Feature | Groups (ACL) | Record Rules |
|---------|--------------|--------------|
| **Level** | Model-level | Row-level |
| **Controls** | CRUD operations (can create/read/write/delete) | Which records user can access |
| **Example** | "Sales reps can create transactions" | "Sales reps can only see their own transactions" |
| **File** | `ir.model.access.csv` | `security.xml` |

See [SECURITY_MODEL.md](docs/SECURITY_MODEL.md) for details.

### How do I add a new user?

1. Navigate to **Settings > Users & Companies > Users**
2. Click **Create**
3. Fill: Name, Email, Login
4. **Access Rights** tab:
   - Check groups (e.g., `plasticos_group_sales`)
5. Click **Save**
6. Send user their login credentials

### Can I use SSO (Single Sign-On)?

**Yes**, Odoo supports SAML 2.0 and OAuth 2.0 (requires Odoo Enterprise license or custom module).

For open-source SSO, use:
- **auth_oauth** module (Google, Facebook, GitHub)
- **auth_saml** (community module)

---

## Data Questions

### Where is data stored?

- **Relational data**: PostgreSQL (`odoo` database)
- **Graph data**: Neo4j (Facility, Material nodes)
- **Files**: Odoo filestore (`/var/lib/odoo/filestore/`)

### How do I backup data?

**PostgreSQL**:
```bash
pg_dump -U odoo odoo > backup_$(date +%Y%m%d).sql
```

**Neo4j**:
```bash
docker compose exec neo4j neo4j-admin dump --database=neo4j --to=/backups/neo4j.dump
```

**Filestore**:
```bash
tar -czf filestore_backup.tar.gz /var/lib/odoo/filestore/
```

See [DEPLOYMENT.md#Backup](docs/DEPLOYMENT.md) for automated backups.

### Can I export data to Excel?

**Yes**, built-in Odoo feature:
1. Navigate to any list view (e.g., Transactions)
2. Select records (or **Select All**)
3. Click **Action > Export**
4. Choose fields to export
5. Download as CSV or XLS

### How do I migrate data from another system?

1. **Export data** from old system to CSV
2. **Map fields** to PlasticOS schema
3. **Use import wizards**:
   - Partners: `plasticos_partner_import`
   - Transactions: `plasticos_transaction_import` (cieTrade format)
4. **Verify import**: Check audit logs, run integrity checks

See [MIGRATION_GUIDE.md](docs/MIGRATION_GUIDE.md) for detailed steps.

---

## Integration Questions

### Does PlasticOS have an API?

**Yes**, Odoo XML-RPC / JSON-RPC API:
- **External API**: `https://your-odoo.com/xmlrpc/2/`
- **JSON API**: `https://your-odoo.com/web/dataset/call_kw`

See [API_REFERENCE.md](docs/API_REFERENCE.md) for examples.

### Can I integrate with QuickBooks?

**Yes**, via:
- **Odoo QuickBooks Online Connector** (paid module)
- **Custom integration** using QuickBooks API + Odoo API

### Can I integrate with Salesforce?

**Yes**, via:
- **Zapier** (no-code integration)
- **Custom API integration** (Salesforce REST API + Odoo API)
- **ETL tools** (Talend, Apache Airflow)

### Does PlasticOS support webhooks?

**Not natively**, but can be implemented via:
- Custom module with `@http.route` endpoints
- Odoo **Automation Actions** (trigger external HTTP requests)

Example:
```python
# models/intake.py
def action_match_to_buyers(self):
    result = super().action_match_to_buyers()
    # Trigger webhook
    requests.post('https://your-webhook.com/intake-matched', json={
        'intake_id': self.id,
        'match_count': len(self.intake_match_ids),
    })
    return result
```

---

## Support

### How do I get help?

1. **Search this FAQ**
2. **Check documentation**: [docs/](docs/)
3. **Search GitHub Issues**: [Issues](https://github.com/cryptoxdog/IB-Odoo_19/issues)
4. **Ask in Discussions**: [Discussions](https://github.com/cryptoxdog/IB-Odoo_19/discussions)
5. **Email support**: ib718@icloud.com

### How do I report a bug?

1. **Verify it's a bug** (not configuration issue)
2. **Check if already reported**: [GitHub Issues](https://github.com/cryptoxdog/IB-Odoo_19/issues)
3. **Open new issue** with:
   - Steps to reproduce
   - Expected vs actual behavior
   - Error logs
   - Odoo version, module version
   - Environment (Docker, Odoo.sh, local)

### How do I request a feature?

1. **Check roadmap**: [ROADMAP.md](docs/ROADMAP.md)
2. **Search discussions**: [Feature Requests](https://github.com/cryptoxdog/IB-Odoo_19/discussions/categories/feature-requests)
3. **Open new discussion** with:
   - Use case and business value
   - Proposed solution
   - Willingness to contribute

### Is commercial support available?

**Yes**. Contact ib718@icloud.com for:
- Priority support
- Custom development
- Consulting and training
- Managed hosting

---

**Still have questions?** Open a [GitHub Discussion](https://github.com/cryptoxdog/IB-Odoo_19/discussions)!

*Last Updated: 2026-02-24*
