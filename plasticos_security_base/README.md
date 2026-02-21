---
component_id: "PLASTICOS-SECURITY-001"
component_name: "PlasticOS Security Base"
module_version: "19.0.1.0.0"
layer: "foundation"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Security groups and access control foundation"
summary: "Role-based access control across all modules"
---

# PlasticOS Security Base

## Purpose
Foundation security module defining groups and access control for all PlasticOS modules.

## Summary
- Security group definitions
- Role-based access control
- Cross-module security inheritance

## Structure
```
├── __init__.py
├── __manifest__.py
├── security/
│   ├── ir.model.access.csv
│   └── security_groups.xml
└── views/
    └── res_partner_views.xml
```

## Dependencies
- base, sale, purchase, account, stock
- All plasticos_* modules

## Security Groups
| Group | Description |
|-------|-------------|
| `group_sales_rep` | Sales Representative |
| `group_logistics` | Logistics Team |
| `group_accounting` | Accounting Team |
| `group_logistics_ops` | Logistics Operations (trucker communications) |
| `group_qc_manager` | Quality Control Manager |
| `group_accounting_ops` | Accounting Operations |
| `group_operations_manager` | Operations Manager |
| `group_system_admin` | System Administrator |

## Tier
foundation
