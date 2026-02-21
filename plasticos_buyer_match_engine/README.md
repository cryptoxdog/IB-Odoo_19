---
component_id: "PLASTICOS-BUYER-MATCH-001"
component_name: "PlasticOS Buyer Match Engine"
module_version: "19.0.1.0.0"
layer: "analytics"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Advanced buyer capability matching"
summary: "Capability-based buyer selection"
---

# PlasticOS Buyer Match Engine

## Purpose
Advanced buyer capability matching based on facility profiles and material requirements.

## Summary
- Buyer capability tracking
- Intake-to-buyer matching triggers
- Capability-based scoring

## Structure
```
├── __init__.py
├── __manifest__.py
├── models/
│   └── buyer_capability.py
├── security/
│   └── ir.model.access.csv
└── views/
    ├── buyer_capability_views.xml
    └── intake_button_views.xml
```

## Dependencies
- plasticos_intake, plasticos_material_profile
- plasticos_matching, plasticos_facility_profile

## Models
| Model | Description |
|-------|-------------|
| `plasticos.buyer.capability` | Buyer processing capabilities |

## Tier
analytics
