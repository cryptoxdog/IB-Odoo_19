---
component_id: "plasticos_transaction"
component_name: "Plasticos Transaction"
module_version: "19.0.2.0.0"
layer: "core"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Core transaction spine - orchestrates deals from intake to delivery"
summary: "Transaction lifecycle management with commission tracking"
---

# Plasticos Transaction

## Purpose
Core transaction spine - orchestrates deals from intake to delivery

## Summary
Transaction lifecycle management with commission tracking

## Structure
```
GUIDE.md
PlasticOS_Transaction_History_2025.csv
README.rst
__init__.py
__manifest__.py
cieTrade.WksDetail.csv
data/
migrations/
models/
scripts/
security/
tests/
views/
wizards/
```

## Dependencies
base, mail, product, account, sale_management, purchase, plasticos_logistics, plasticos_material_profile, plasticos_facility_profile, plasticos_intake, plasticos_product

## Models
plasticos.audit.cron, plasticos.transaction, plasticos.transaction.line, plasticos.transaction.import.service, plasticos.commission.rule, plasticos.commission.service

## Tier
core
