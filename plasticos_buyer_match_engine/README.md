---
component_id: "plasticos_buyer_match_engine"
component_name: "Plasticos Buyer Match Engine"
module_version: "19.0.2.0.0"
layer: "analytics"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Advanced buyer capability matching"
summary: "Capability-based buyer selection"
---

# Plasticos Buyer Match Engine

## Purpose
Advanced buyer capability matching

## Summary
Capability-based buyer selection

## Structure
```
Knowledge Base V8.0/
Mack_agent_buyer_matching v7.0.py
README.md
README.rst
Readme-IB.md
__init__.py
__manifest__.py
doc/
models/
security/
services/
tests/
views/
```

## Dependencies
plasticos_intake, plasticos_material_profile, plasticos_facility_profile, plasticos_matching, plasticos_transaction

## Models
plasticos.buyer.matcher, plasticos.graph.service, plasticos.graph.sync.log, plasticos.match.exclusion

## Tier
analytics


## Related Documentation

- `ARCHITECTURE.md` — # ARCHITECTURE.md — PlasticOS System Architecture  **Repository**: cryptoxdog/IB...
- `DEPLOYMENT.md` — # DEPLOYMENT.md — PlasticOS Deployment Guide  **Repository**: cryptoxdog/IB-Odoo...
