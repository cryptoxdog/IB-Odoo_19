---
component_id: "PLASTICOS-IMPORT-001"
component_name: "PlasticOS Partner Import"
module_version: "19.0.1.0.0"
layer: "integration"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Partner and facility CSV import service"
summary: "Bulk partner data import"
---

# PlasticOS Partner Import

## Purpose
Bulk import service for partners and facilities from CSV files.

## Summary
- CSV import processing
- Partner validation
- Facility profile creation
- Import logging

## Structure
```
├── __init__.py
├── __manifest__.py
├── models/
│   ├── partner_import_service.py
│   └── validation.py
├── scripts/
│   └── run_import.py
├── security/
│   └── ir.model.access.csv
└── *.csv (import data files)
```

## Dependencies
- base, contacts, account
- plasticos_facility_profile

## Models
| Model | Description |
|-------|-------------|
| `plasticos.partner.import.service` | Import processing service |
| `plasticos.partner.import.validation` | Import validation rules |

## Tier
integration
