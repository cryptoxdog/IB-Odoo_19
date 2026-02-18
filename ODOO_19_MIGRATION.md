# Odoo 19 Migration Reference

**Generated:** 2026-02-17  
**Source:** Official Odoo 19 docs + Cybrosys technical guide

---

## Breaking Changes Matrix

| Category | Deprecated | Odoo 19 Replacement | Severity |
|----------|------------|---------------------|----------|
| SQL Constraints | `_sql_constraints = [(...)]` | `_check_name = models.Constraint(...)` | CRITICAL |
| Context | `self._context` | `self.env.context` | HIGH |
| Expression OR | `from odoo.osv.expression import OR` | `Domain.OR` | HIGH |
| API decorator | `@api.returns` | **Removed** | HIGH |
| Port config | `xmlrpc_port` | `http_port` | MEDIUM |
| Template escape | `t-esc` | `t-out` | MEDIUM |
| Kanban template | `<t t-name="kanban-box">` | `<t t-name="card">` | MEDIUM |
| Security groups | `category_id` | `privilege_id` | MEDIUM |
| Users field | `groups_id` | `group_ids` | MEDIUM |
| Portal access | `check_access_rights` | `check_access` | MEDIUM |
| Product UoM | `product_uom` | `product_uom_id` | MEDIUM |
| Taxes field | `taxes_id` | `tax_ids` | MEDIUM |
| Website cart | `sale_get_order()` | `request.cart` | MEDIUM |
| Cart create | `_create_cart()` | replaces `sale_get_order()` | MEDIUM |
| POS method | `this.pos.get_order()` | `this.pos.getOrder()` | LOW |
| JS controller | `type="json"` | `type="jsonrpc"` | LOW |

---

## Python Requirements

```yaml
minimum: "3.10"
recommended: "3.12"
note: "Older versions NOT supported"
```

---

## SQL Constraint Syntax (Odoo 19)

```python
# ❌ OLD (deprecated)
_sql_constraints = [
    ("unique_name", "unique(field)", "Error message")
]

# ✅ NEW (Odoo 19)
_check_unique_name = models.Constraint(
    "unique(field)",
    "Error message",
)
```

**Key rules:**
- Named class attribute (prefix `_check_` or similar)
- Use `models.Constraint` not standalone `Constraint`
- NOT a list, individual attributes per constraint

---

## Cursor Execute Pattern

```python
# ❌ OLD (returns None in Odoo 19)
result = self.env.cr.execute("SELECT ...")

# ✅ NEW
self.env.cr.execute("SELECT ...")
result = self.env.cr.fetchall()
```

---

## Fixes Applied to PlasticOS Modules

### Module: `plasticos_intake`

| File | Issue | Fix |
|------|-------|-----|
| `__manifest__.py` | Missing deps `plasticos_material`, `plasticos_processing` | Removed |
| `__manifest__.py` | Missing `author`, `license` | Added `PlasticOS`, `LGPL-3` |
| `models/intake.py` | `processing_profile_id` refs non-existent model | Commented out |
| `models/intake.py` | `l9.adapter.service` refs non-existent model | Stubbed with UserError |
| `models/intake.py` | `_sql_constraints` deprecated | → `models.Constraint` class attr |
| `views/intake_views.xml` | `processing_profile_id` field in form | Removed |

### Module: `plasticos_logistics`

| File | Issue | Fix |
|------|-------|-----|
| `__manifest__.py` | Dep on `l9_trace` (non-existent) | Removed |
| `__manifest__.py` | Missing `author`, `license`, `summary` | Added |
| `models/load.py` | `l9_trace` imports | Replaced with `uuid` + `logging` |
| `models/dispatch.py` | `l9_trace` imports | Replaced with `uuid` + `logging` |

### Module: `plasticos_documents`

| File | Issue | Fix |
|------|-------|-----|
| `__manifest__.py` | Missing `author`, `license`, `summary` | Added |
| `data/cron.xml` | Refs abstract model `plasticos.compliance.service` | → `plasticos.document` |
| `data/cron.xml` | Cron active by default | Set `active=False` |

### Module: `plasticos_commission`

| File | Issue | Fix |
|------|-------|-----|
| `__manifest__.py` | Missing `author`, `license`, `summary` | Added |

### Module: `plasticos_transaction`

| File | Issue | Fix |
|------|-------|-----|
| `__manifest__.py` | Missing `author`, `license`, `summary` | Added |
| `tests/__init__.py` | Only 7/15 tests imported | All 15 now imported |
| `tests/test_migration_safety.py` | `cr.execute()` return value | Added `fetchall()` |

---

## Deleted Files (Duplicates)

```
plasticos_logistics/manifest.py      # shadowed __manifest__.py
plasticos_logistics/init.py          # shadowed __init__.py
plasticos_logistics/models/init.py   # shadowed models/__init__.py
plasticos_documents/manifest.py      # shadowed __manifest__.py
plasticos_documents/init.py          # shadowed __init__.py
plasticos_documents/models/init.py   # shadowed models/__init__.py
```

---

## L9 Integration Status

```yaml
l9_trace:
  status: DISABLED
  reason: Module not available in this deployment
  files_affected:
    - plasticos_logistics/models/load.py
    - plasticos_logistics/models/dispatch.py
  replacement: uuid + logging stubs

l9.adapter.service:
  status: DISABLED
  reason: Model not available
  files_affected:
    - plasticos_intake/models/intake.py
  replacement: UserError stubs
```

---

## Manifest Template (Odoo 19 Compliant)

```python
{
    "name": "Module Name",
    "version": "1.0.0",
    "summary": "Brief description",
    "author": "PlasticOS",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/main_views.xml",
    ],
    "installable": True,
    "application": False,
}
```

---

## Test Pattern (Odoo 19)

```python
from odoo.tests.common import TransactionCase

class TestExample(TransactionCase):

    def setUp(self):
        super().setUp()
        # Setup code

    def test_something(self):
        # Use ORM methods
        record = self.env["model.name"].create({})
        
        # Raw SQL (if needed)
        self.env.cr.execute("SELECT ...")
        rows = self.env.cr.fetchall()
        
        self.assertFalse(rows, "Error message")
```

---

## References

- [Odoo 19 Constraints Tutorial](https://www.odoo.com/documentation/19.0/developer/tutorials/server_framework_101/10_constraints.html)
- [Odoo 19 Technical Changes](https://www.cybrosys.com/blog/overview-of-what-developers-need-to-know-in-odoo-19-technical-changes)
- [Odoo 19 Release Notes](https://www.odoo.com/odoo-19-release-notes)
