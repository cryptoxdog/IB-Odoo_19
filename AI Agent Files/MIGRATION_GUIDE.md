# MIGRATION_GUIDE.md — PlasticOS Migration Guide

**Repository**: cryptoxdog/IB-Odoo_19
**Current Version**: 19.0
**Last Updated**: 2026-02-24

## Overview

This guide covers migration scenarios for PlasticOS:
1. Legacy data migration from CSV
2. Module version upgrades
3. Schema changes and data transformations
4. Zero-downtime deployment strategies

---

## 1. Legacy Data Migration

### Partner Import from CSV

**Module**: `plasticos_partner_import`

**Supported Formats**:
- Corporate-only records
- Facility-only records
- Full hierarchy (Corporate + Facilities)

**Import Wizard**:
```python
# Navigate to: Contacts > Import Partners
wizard = env['plasticos.partner.import.wizard'].create({
    'corporate_csv_path': '/path/to/corporate.csv',
    'facility_csv_path': '/path/to/facilities.csv',
    'create_profiles': True,
})
wizard.action_run_import()
```

**CSV Format (Corporate)**:
```csv
external_id,name,company_type,street,city,state,zip,phone,email,payment_term_code
corp_abc,ABC Plastics Inc,company,123 Main St,Charlotte,NC,28202,555-0001,info@abc.com,net30
```

**CSV Format (Facility)**:
```csv
external_id,name,parent_external_id,type,street,city,state,zip,polymer_codes,equipment_codes,volume_min
fac_abc_001,ABC Plant 1,corp_abc,delivery,456 Plant Rd,Charlotte,NC,28203,"HDPE,PP","washline,grinder",5000
```

**Validation**:
```bash
# Audit import integrity
wizard.action_audit_import()

# Repair data issues
wizard.action_repair_import()
```

### Transaction Import from cieTrade CSV

**Module**: `plasticos_transaction`

**Wizard**: `plasticos.transaction.import.wizard`

**CSV Format** (cieTrade.WksDetail.csv):
```csv
BuySellNo,Company,Supplier,Material,Quantity,PricePerLb,TransactionDate
TX001,Buyer Corp,Supplier Inc,HDPE Regrind,10000,0.45,2024-01-15
TX001,Buyer Corp,Supplier Inc,HDPE Regrind,10000,0.55,2024-01-15
```

**Import Strategy**:
- Group by `BuySellNo` (transaction ID)
- First row → Transaction header
- All rows → Transaction lines
- Dry run mode available
- Skip existing transactions

**Usage**:
```python
wizard = env['plasticos.transaction.import.wizard'].create({
    'csv_file': base64.b64encode(csv_data),
    'filename': 'cieTrade.WksDetail.csv',
    'dry_run': True,
})
wizard.action_import()
```

---

## 2. Module Version Upgrades

### Version Numbering

**Format**: `<odoo_version>.<major>.<minor>.<patch>`

**Example**: `19.0.2.1.5`
- `19.0` = Odoo version
- `2` = Major (breaking changes)
- `1` = Minor (new features)
- `5` = Patch (bug fixes)

### Migration Script Structure

**Location**: `<module>/migrations/<version>/`

**Example**: `plasticos_transaction/migrations/19.0.2.0.0/`

**Files**:
- `pre-migrate.py` — Runs before module upgrade
- `post-migrate.py` — Runs after module upgrade
- `end-migrate.py` — Runs after all modules upgraded

### Pre-Migration Script Template

```python
# plasticos_transaction/migrations/19.0.2.0.0/pre-migrate.py
import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """
    Pre-migration: Prepare data before schema changes.
    """
    _logger.info("Running pre-migration for plasticos_transaction 19.0.2.0.0")

    # Example: Rename old field
    if column_exists(cr, 'plasticos_transaction', 'old_field'):
        cr.execute("""
            ALTER TABLE plasticos_transaction
            RENAME COLUMN old_field TO new_field
        """)
        _logger.info("Renamed old_field to new_field")

def column_exists(cr, table, column):
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name=%s AND column_name=%s
    """, (table, column))
    return bool(cr.fetchone())
```

### Post-Migration Script Template

```python
# plasticos_transaction/migrations/19.0.2.0.0/post-migrate.py
import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """
    Post-migration: Transform data after schema updated.
    """
    _logger.info("Running post-migration for plasticos_transaction 19.0.2.0.0")

    # Example: Populate new field from computed logic
    cr.execute("""
        UPDATE plasticos_transaction
        SET commission_amount = (total_buyer_revenue - total_supplier_cost) * 0.10
        WHERE commission_amount IS NULL
    """)
    _logger.info("Computed commission_amount for existing transactions")
```

### Migration Testing

**Test Database**:
```bash
# Backup production
pg_dump -U odoo odoo > backup_pre_migration.sql

# Restore to test database
createdb odoo_migration_test
psql -U odoo odoo_migration_test < backup_pre_migration.sql

# Run upgrade
odoo-bin -d odoo_migration_test -u plasticos_transaction --stop-after-init

# Verify data integrity
psql -U odoo odoo_migration_test -c "SELECT COUNT(*) FROM plasticos_transaction WHERE commission_amount IS NULL"
```

---

## 3. Schema Changes

### Adding New Field (Non-Breaking)

**Example**: Add `deal_type` to `plasticos.intake`

**Steps**:
1. Add field to model:
```python
deal_type = fields.Selection([
    ('spot', 'Spot Purchase'),
    ('contract', 'Contract'),
    ('recurring', 'Recurring Order'),
], string='Deal Type', default='spot')
```

2. Update views (optional):
```xml
<field name="deal_type"/>
```

3. No migration script needed (Odoo auto-creates column)

4. Increment version: `19.0.5.0.0` → `19.0.5.1.0`

### Renaming Field (Breaking Change)

**Example**: Rename `broker_id` → `trucker_id` in `plasticos.load`

**Steps**:
1. Create pre-migration script:
```python
def migrate(cr, version):
    cr.execute("""
        ALTER TABLE plasticos_load
        RENAME COLUMN broker_id TO trucker_id
    """)
```

2. Update model definition:
```python
# OLD: broker_id = fields.Many2one('res.partner')
trucker_id = fields.Many2one('res.partner', string='Carrier')
```

3. Update all references (views, compute methods, etc.)

4. Increment major version: `19.0.1.0.0` → `19.0.2.0.0`

### Changing Field Type (Breaking Change)

**Example**: Convert `polymer` (Char) → `polymer_id` (Many2one)

**Steps**:
1. Create new field without removing old:
```python
polymer = fields.Char(string='Polymer (DEPRECATED)', deprecated=True)
polymer_id = fields.Many2one('plasticos.polymer', string='Polymer')
```

2. Create post-migration to populate new field:
```python
def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    intakes = env['plasticos.intake'].search([('polymer_id', '=', False)])
    for intake in intakes:
        if intake.polymer:
            polymer = env['plasticos.polymer'].search([('code', '=', intake.polymer.upper())], limit=1)
            if polymer:
                intake.polymer_id = polymer.id
```

3. Remove deprecated field in next major version

---

## 4. Neo4j Graph Migration

### Initial Schema Setup

```bash
./scripts/setup_neo4j.sh --init-schema
```

**Creates**:
- Node labels: `Facility`, `Material`, `Intake`, `Transaction`
- Indexes on `partner_id`, `material_id`, `intake_id`
- Constraints for uniqueness

### Sync Existing Data to Graph

```python
# Via Odoo shell
graph_service = env['plasticos.graph.service']

# Sync all facilities
graph_service.sync_facility_nodes(trigger='migration')

# Sync all materials
graph_service.sync_material_nodes(trigger='migration')

# Sync transactions (last 90 days for recency weighting)
graph_service.sync_transaction_edges(trigger='migration')

env.cr.commit()
```

### Graph Schema Updates

**Adding New Node Property**:
```cypher
// Add property to existing nodes
MATCH (f:Facility)
SET f.new_property = null
```

**Creating New Relationship**:
```cypher
// Create new relationship type
MATCH (i:Intake), (f:Facility)
WHERE i.matched_buyer_id = f.partner_id
MERGE (i)-[:MATCHED_TO]->(f)
```

**Reindex**:
```cypher
CREATE INDEX facility_new_property IF NOT EXISTS FOR (f:Facility) ON (f.new_property)
```

---

## 5. Zero-Downtime Deployment

### Blue-Green Deployment Strategy

**Step 1: Deploy Green Environment**
```bash
# Start green stack
docker compose -p plasticos_green -f docker-compose.green.yml up -d

# Run migrations
docker compose -p plasticos_green exec odoo odoo-bin -d odoo --update=all --stop-after-init

# Smoke test
curl http://localhost:8070/web/health
```

**Step 2: Switch Traffic**
```nginx
# Update load balancer
upstream odoo_backend {
    # server localhost:8069;  # Blue (old)
    server localhost:8070;    # Green (new)
}
```

**Step 3: Monitor**
- Watch error logs
- Check transaction creation rate
- Verify matching engine working

**Step 4: Rollback if Needed**
```nginx
# Revert load balancer
upstream odoo_backend {
    server localhost:8069;  # Blue (rollback)
}
```

### Database Migration with Replication

**Option 1: Dump & Restore**
```bash
# Backup
pg_dump -U odoo odoo > backup_$(date +%Y%m%d).sql

# Restore to new database
createdb odoo_new
psql -U odoo odoo_new < backup_20260224.sql

# Update Odoo config to use odoo_new
```

**Option 2: PostgreSQL Replication**
- Set up read replica
- Promote replica to primary
- Point Odoo to new primary

---

## 6. Data Integrity Validation

### Post-Migration Checks

**Partner Integrity**:
```sql
-- Check for missing facility profiles
SELECT p.id, p.name
FROM res_partner p
WHERE p.supplier_rank > 0
  AND NOT EXISTS (
    SELECT 1 FROM plasticos_facility_profile f WHERE f.partner_id = p.id
  );
```

**Transaction Integrity**:
```sql
-- Check for orphaned transactions
SELECT t.id, t.name
FROM plasticos_transaction t
LEFT JOIN res_partner buyer ON t.buyer_id = buyer.id
LEFT JOIN res_partner supplier ON t.supplier_id = supplier.id
WHERE buyer.id IS NULL OR supplier.id IS NULL;
```

**Graph Sync Validation**:
```cypher
// Check facility node count vs Odoo
MATCH (f:Facility)
RETURN COUNT(f) AS facility_count
// Compare to: SELECT COUNT(*) FROM plasticos_facility_profile
```

### Automated Validation Script

```python
# scripts/validate_migration.py
def validate_post_migration(env):
    errors = []

    # Check 1: All transactions have buyer/supplier
    orphaned_tx = env['plasticos.transaction'].search([
        '|', ('buyer_id', '=', False), ('supplier_id', '=', False)
    ])
    if orphaned_tx:
        errors.append(f"Found {len(orphaned_tx)} orphaned transactions")

    # Check 2: All facility profiles have valid partner
    invalid_profiles = env['plasticos.facility.profile'].search([
        ('partner_id', '=', False)
    ])
    if invalid_profiles:
        errors.append(f"Found {len(invalid_profiles)} profiles without partner")

    # Check 3: Neo4j connectivity
    try:
        graph_service = env['plasticos.graph.service']
        if not graph_service._get_driver():
            errors.append("Neo4j connection failed")
    except:
        errors.append("Neo4j service unavailable")

    return errors
```

---

## 7. Rollback Procedures

### Odoo Module Rollback

**Not Supported Natively** — Use database restore:
```bash
# Stop Odoo
docker compose -p plasticos_prod stop odoo

# Restore pre-migration backup
psql -U odoo odoo < backup_pre_migration.sql

# Start Odoo
docker compose -p plasticos_prod start odoo
```

### Git-Based Code Rollback

```bash
# Revert to previous commit
git checkout <previous_commit_sha>

# Rebuild Docker image
docker compose -p plasticos_prod build

# Restart
docker compose -p plasticos_prod up -d
```

### Neo4j Graph Rollback

```cypher
// Delete nodes created after migration timestamp
MATCH (n)
WHERE n.created_at > datetime('2026-02-24T00:00:00Z')
DETACH DELETE n
```

---

## 8. Migration Checklist

### Pre-Migration
- [ ] Full database backup
- [ ] Export critical data (transactions, partners)
- [ ] Test migration on staging
- [ ] Review migration scripts
- [ ] Schedule maintenance window
- [ ] Notify users

### During Migration
- [ ] Stop cron jobs
- [ ] Put Odoo in maintenance mode
- [ ] Run pre-migration scripts
- [ ] Update modules
- [ ] Run post-migration scripts
- [ ] Validate data integrity

### Post-Migration
- [ ] Smoke test critical paths
- [ ] Verify Neo4j sync
- [ ] Check error logs
- [ ] Re-enable cron jobs
- [ ] Monitor for 24 hours
- [ ] Update documentation

---

**Migration Guide Version**: 1.0.0
**Last Updated**: 2026-02-24
**Tested On**: Odoo 19.0, PostgreSQL 15, Neo4j 5.15
