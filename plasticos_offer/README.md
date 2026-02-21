---
component_id: "PLASTICOS-OFFER-001"
component_name: "PlasticOS Offer"
module_version: "19.0.1.0.0"
layer: "core"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Offer generation and tracking for matched intakes"
summary: "Offer lifecycle from draft to acceptance"
---

# PlasticOS Offer

## Purpose
Offer generation and tracking for matched intakes through the sales cycle.

## Summary
- Offer creation from matches
- State management (draft → sent → accepted/rejected)
- Pricing and terms tracking

## Structure
```
├── __init__.py
├── __manifest__.py
├── models/
│   └── offer.py
├── security/
│   └── ir.model.access.csv
└── views/
    └── offer_views.xml
```

## Dependencies
- base, mail
- plasticos_intake, plasticos_matching

## Models
| Model | Description |
|-------|-------------|
| `plasticos.offer` | Offer with state management |

## Tier
core
