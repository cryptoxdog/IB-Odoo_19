
### File 4: INVARIANTS.md

```markdown
# INVARIANTS.md — PlasticOS System Invariants

**Purpose**: Unchangeable rules that govern the PlasticOS codebase.
**Status**: Constitutional
**Enforcement**: Machine + Human

## Meta-Rule

**If code violates an invariant, code is wrong — not invariant.**

## Core Invariants

### 1. Odoo 19 Compliance

**Rule**: No deprecated Odoo patterns.

**Forbidden Patterns**:
- ❌ `_sql_constraints` → Use `models.Constraint`
- ❌ `@api.depends("id")` → Remove `"id"` from depends
- ❌ `@api.one` / `@api.multi` → Removed in Odoo 13
- ❌ `category_id` on `res.groups` → Removed in Odoo 19
- ❌ `numbercall` on `ir.cron` → Deprecated

**Detection**:
```bash
scripts/check_odoo_patterns.sh
```

**Enforcement**: Pre-commit hook, CI/CD pipeline

---

### 2. Dependency Graph Acyclicity

**Rule**: Module dependency graph must be a DAG (Directed Acyclic Graph).

**Prohibited**:
- ❌ Circular dependencies: A → B → A
- ❌ Transitive cycles: A → B → C → A

**Detection**:
```bash
python3 scripts/check_module_wiring.py
```

**Enforcement**: Pre-commit hook

---

### 3. Namespace Consistency

**Rule**: Use `plasticos_` prefix universally.

**Required**:
- ✅ Module names: `plasticos_<module>`
- ✅ Model names: `plasticos.<model>`
- ✅ External IDs: `plasticos_<module>.<external_id>`

**Forbidden**:
- ❌ `plastos_` (namespace drift)
- ❌ `plast_` (abbreviation)
- ❌ Mixed conventions

**Detection**: Grep + manual audit

---

### 4. Deterministic Seed Doctrine

**Rule**: All reference data versioned in XML with `noupdate="1"`.

**Required**:
- ✅ Partner tags in XML
- ✅ Material taxonomy in XML
- ✅ Payment terms in XML
- ✅ Chart of accounts in XML
- ✅ Partner types in XML

**Forbidden**:
- ❌ Runtime CSV bootstrap
- ❌ Python seed generation (except migrations)
- ❌ Hardcoded database IDs

**Enforcement**: Code review, architectural audit

---

### 5. Graph Isolation Boundary

**Rule**: Neo4j integration must not break Odoo registry.

**Required**:
- ✅ Neo4j imports wrapped in try/except
- ✅ Graph failures return empty results
- ✅ No Neo4j imports in `__init__.py` registry load
- ✅ Connection timeout defined

**Forbidden**:
- ❌ Graph failures raise unhandled exceptions
- ❌ Neo4j driver imported at module load
- ❌ Blocking Odoo startup on Neo4j availability

**Enforcement**: Code review, integration tests

---

### 6. Partner Architecture Integrity

**Rule**: Use native Odoo partner fields + isolated capability profiles.

**Required**:
- ✅ `company_type` for entity type
- ✅ `customer_rank` / `supplier_rank` for business role
- ✅ `category_id` for partner tags
- ✅ `plasticos.facility.profile` for capabilities (One2many)

**Forbidden**:
- ❌ Custom partner role booleans (`is_buyer`, `is_supplier`)
- ❌ Material profiles attached directly to `res.partner`
- ❌ Capability fields on `res.partner` model

**Enforcement**: Architectural review, module wiring check

---

### 7. Layer Dependency Direction

**Rule**: Higher layers depend on lower layers, never reverse.

**Dependency Flow**:
```
Transaction Layer (5)
    ↓ depends on
Compliance Layer (4)
    ↓ depends on
Commercial Layer (3)
    ↓ depends on
Capability Layer (2)
    ↓ depends on
Material Layer (1)
```

**Forbidden**:
- ❌ Material layer depending on transaction layer
- ❌ Intake depending on documents
- ❌ Capability depending on commercial

**Enforcement**: Dependency graph analysis

---

### 8. Security Model Completeness

**Rule**: Every model requires ACL and record rules.

**Required**:
- ✅ `security/ir.model.access.csv` in every module
- ✅ Record rules for multi-company isolation
- ✅ Group-based access control

**Forbidden**:
- ❌ Models without ACL file
- ❌ `sudo()` without explicit justification comment
- ❌ World-readable sensitive fields

**Enforcement**: Module wiring check, security audit

---

### 9. External ID Referential Integrity

**Rule**: All `ref="..."` must point to existing external IDs.

**Required**:
- ✅ External IDs defined before use
- ✅ No duplicate external IDs across modules
- ✅ Seed data loading order enforced by dependencies

**Forbidden**:
- ❌ `ref="module.nonexistent_id"`
- ❌ Duplicate external IDs
- ❌ Orphaned XML records

**Detection**:
```bash
grep -r 'ref="' --include="*.xml" | check_external_ids.py
```

---

### 10. Test Isolation

**Rule**: Tests must not mutate seed data or production database.

**Required**:
- ✅ Use dedicated test database (`odoo_test`)
- ✅ Transactional rollback after tests
- ✅ No test data committed to seed XML

**Forbidden**:
- ❌ Tests writing to production database
- ❌ Test data in `data/*.xml` files
- ❌ Tests assuming specific database state

**Enforcement**: Test suite configuration, code review

---

### 11. API Dependency Isolation

**Rule**: External API failures must not crash Odoo.

**Required**:
- ✅ OpenAI API wrapped in try/except
- ✅ API failures return safe defaults
- ✅ Rate limiting handled
- ✅ API keys in environment variables

**Forbidden**:
- ❌ Unhandled OpenAI exceptions
- ❌ Hardcoded API keys
- ❌ Blocking operations without timeout

**Enforcement**: Code review, integration tests

---

### 12. Model Name Uniqueness

**Rule**: No duplicate `_name` across all modules.

**Required**:
- ✅ Unique `_name` for each model
- ✅ Use `_inherit` for extensions
- ✅ Avoid namespace collisions

**Forbidden**:
- ❌ Two modules defining `plasticos.intake`
- ❌ Model name collision with Odoo core

**Detection**:
```bash
python3 scripts/check_module_wiring.py
```

---

### 13. Field Reference Safety

**Rule**: All field references must exist before use.

**Required**:
- ✅ Fields defined before `@api.depends`
- ✅ Related fields point to existing paths
- ✅ Computed fields reference valid fields

**Forbidden**:
- ❌ `@api.depends("nonexistent_field")`
- ❌ `related="missing.path"`
- ❌ Undefined field in compute method

**Detection**: Odoo registry load errors, unit tests

---

### 14. Migration Safety

**Rule**: Migrations must be idempotent and safe.

**Required**:
- ✅ Migrations check before modify
- ✅ No data loss on rollback
- ✅ Version numbering enforced

**Forbidden**:
- ❌ Destructive migrations without backup
- ❌ Non-idempotent operations
- ❌ Missing version tags

**Enforcement**: Code review, staging environment testing

---

### 15. Cron Job Discipline

**Rule**: Cron jobs must have safe failure modes.

**Required**:
- ✅ Cron failures logged, not raised
- ✅ Idempotent operations
- ✅ `active="False"` by default for production safety

**Forbidden**:
- ❌ Crons crashing on failure
- ❌ Non-idempotent batch operations
- ❌ Auto-enabled crons in production

**Enforcement**: Code review, manual testing

---

## Enforcement Strategy

### Automated Checks
- **Pre-commit hooks**: Ruff, module wiring, XML validation
- **CI/CD pipeline**: Full test suite, pattern detection
- **Module wiring script**: Dependency graph validation

### Manual Reviews
- **Architectural review**: Layer violations, partner model changes
- **Security audit**: ACL completeness, sensitive data exposure
- **Code review**: API isolation, error handling

### Violation Response
1. **Block merge**: If automated check fails
2. **Request remediation**: If manual review finds violation
3. **Document exception**: If invariant must be violated (rare, requires approval)

---

## Invariant Change Process

**Invariants are constitutional.**

To modify an invariant:
1. Propose change with justification
2. Architectural review and approval
3. Update INVARIANTS.md
4. Update enforcement tooling
5. Remediate existing codebase

**No silent invariant violations.**

---

**Invariants Version**: 1.0.0
**Last Updated**: 2026-02-24
**Maintained By**: PlasticOS Architecture Team
```

***
