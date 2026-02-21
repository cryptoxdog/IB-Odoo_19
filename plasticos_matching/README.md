---
component_id: "PLASTICOS-MATCHING-001"
component_name: "PlasticOS Matching"
module_version: "19.0.1.0.0"
layer: "analytics"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Buyer-intake matching engine"
summary: "Match scoring and result tracking"
---

# PlasticOS Matching

## Purpose
Core matching engine for connecting intakes with potential buyers.

## Summary
- Match result tracking
- Score-based ranking
- Match lifecycle management

## Structure
```
├── __init__.py
├── __manifest__.py
├── models/
│   └── match_result.py
├── security/
│   └── ir.model.access.csv
└── views/
    └── match_result_views.xml
```

## Dependencies
- base, mail
- plasticos_intake, plasticos_facility_profile

## Models
| Model | Description |
|-------|-------------|
| `plasticos.match.result` | Match result with scoring |

## Tier
analytics
