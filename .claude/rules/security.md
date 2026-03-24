---
paths:
  - "plasticos_*/security/**"
  - "plasticos_security_base/**"
---
# PlasticOS Security Model

## Group Hierarchy (plasticos_security_base)

```
plasticos_privilege_manager (Full Access)
  ├── implied → base.group_system, base.group_erp_manager
  └── CRUD on all models

plasticos_privilege_user (Standard User)
  ├── implied → base.group_user
  └── Read all, write own records

plasticos_privilege_readonly (Reports Only)
  └── Read-only all models

plasticos_group_sales → implied → privilege_user
plasticos_group_logistics → implied → privilege_user
plasticos_group_compliance → implied → privilege_user
plasticos_group_accounting → implied → account.group_account_invoice
```

## ACL Requirements
- Every new model MUST have `security/ir.model.access.csv`
- Format: `id,name,model_id/id,group_id/id,perm_read,perm_write,perm_create,perm_unlink`
- At minimum: manager=CRUD, user=CRU, readonly=R

## Record Rules
- Multi-company isolation on all business models
- Sales rep data scoping (own records only for sales group)
- Use `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]` pattern

## Forbidden
- ❌ `sudo()` without explicit justification in code comment
- ❌ Sensitive fields without ACL protection
- ❌ Exposing financial data to non-accounting groups
