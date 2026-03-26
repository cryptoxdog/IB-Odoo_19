---
paths:
  - "plasticos_*/**/*.py"
  - "plasticos_*/**/*.xml"
---
# PlasticOS Invariants

**Meta-Rule**: If code violates an invariant, code is wrong — not the invariant.

## 1. Odoo 19 Compliance
- ❌ `_sql_constraints` → Use `models.Constraint` / `UniqueConstraint`
- ❌ `@api.depends("id")` → Remove "id" from depends
- ❌ `@api.one` / `@api.multi` → Removed in Odoo 13
- ❌ `category_id` on `res.groups` → Removed in Odoo 19
- ❌ `numbercall` on `ir.cron` → Deprecated
- Run: `scripts/check_odoo_patterns.sh`

## 2. Dependency Graph Acyclicity
- Module dependencies must form a DAG (no cycles)
- Every import requires matching `depends` in `__manifest__.py`
- Run: `python3 ci/check_circular_deps.py`

## 3. Namespace Consistency
- Module names: `plasticos_*`
- Model names: `plasticos.*`
- External IDs: `plasticos_module.external_id`
- ❌ `plastos_` / `plast_` / mixed conventions

## 4. Deterministic Seed Doctrine
- All reference data in XML with `noupdate="1"`
- All records have external IDs: `plasticos_module.record_name`
- ❌ CSV runtime bootstrap
- ❌ Hardcoded database IDs

## 5. Neo4j Integration Boundaries
- Graph logic in service classes only
- Graph failures wrapped in safe boundaries
- ❌ Neo4j imports in Odoo registry load path
- ❌ Blocking Odoo startup on Neo4j

## 6. Partner Model Constraints
- Use native: `company_type`, `customer_rank`, `supplier_rank`
- Facility capabilities via `plasticos.facility.profile`
- ❌ Custom partner role booleans
- ❌ Material profiles directly on `res.partner`

## 7. Security
- Every model: `security/ir.model.access.csv`
- Record rules for multi-company isolation
- ❌ `sudo()` without justification
- ❌ Sensitive fields without ACL

## 8. Test Safety
- Tests must not mutate seed data
- ❌ Test data in production seed files
- Tag tests requiring seed data for CI exclusion

## CI Audit Scripts (ci/)
| Script | What it checks |
|--------|---------------|
| check_circular_deps.py | Circular module dependencies |
| check_orphan_model_refs.py | Model references without dependency |
| check_odoo19_xml.py | XML view Odoo 19 compatibility |
| check_field_integrity.py | Field reference validity |
| check_state_guard_bypass.py | State machine bypass safety |
| check_constraint_patterns.py | Deprecated constraint usage |
| check_orm_integrity.py | ORM pattern correctness |
| check_automation_field_refs.py | Automation field references |
| check_xpath_stability.py | XPath expression stability |
| check_odoo_antipatterns.py | General Odoo antipatterns |
