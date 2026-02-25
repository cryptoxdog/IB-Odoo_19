---
component_id: "plasticos_partner_import"
component_name: "Plasticos Partner Import"
module_version: "19.0.1.2.0"
layer: "integration"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Partner and facility CSV import service"
summary: "Bulk partner data import"
---

# Plasticos Partner Import

## Purpose
Partner and facility CSV import service

## Summary
Bulk partner data import

## Structure
```
1. Counterparties - Parent - CORPORATE-Ready To Import.csv
2. Counterparties - Child - FACILITY LOCATIONS.csv
README.md
README.rst
__init__.py
__manifest__.py
models/
scripts/
security/
views/
wizards/
```

## Dependencies
base, contacts, account, plasticos_facility_profile, plasticos_intake

## Models
plasticos.partner.import.service, plasticos.partner.import.validation

## Tier
integration


## Related Documentation

- `ARCHITECTURE.md` — # ARCHITECTURE.md — PlasticOS System Architecture  **Repository**: cryptoxdog/IB...
- `DEPLOYMENT.md` — # DEPLOYMENT.md — PlasticOS Deployment Guide  **Repository**: cryptoxdog/IB-Odoo...
