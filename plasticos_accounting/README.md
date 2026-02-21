---
component_id: "PLASTICOS-ACCOUNTING-001"
component_name: "PlasticOS Accounting"
module_version: "19.0.1.0.0"
layer: "foundation"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Chart of accounts and payment terms"
summary: "Accounting configuration for PlasticOS"
---

# PlasticOS Accounting

## Purpose
Accounting configuration including chart of accounts and payment terms.

## Summary
- Custom payment terms for plastics industry
- Account configuration

## Structure
```
├── __init__.py
├── __manifest__.py
└── data/
    ├── accounts.xml
    └── payment_terms.xml
```

## Dependencies
- account

## Tier
foundation
