---
component_id: "PLASTICOS-FACILITY-001"
component_name: "PlasticOS Facility Profile"
module_version: "19.0.1.0.0"
layer: "domain"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Facility profiles with equipment and capabilities"
summary: "Partner facility specifications"
---

# PlasticOS Facility Profile

## Purpose
Facility profiles capturing equipment, capabilities, and operational details for partners.

## Summary
- Facility profile management
- Equipment type tracking
- Partner type classification
- Operational capabilities

## Structure
```
├── __init__.py
├── __manifest__.py
├── data/
│   ├── equipment_type_data.xml
│   └── partner_type_data.xml
├── models/
│   ├── equipment_type.py
│   ├── facility_profile.py
│   └── partner_type.py
├── security/
│   └── ir.model.access.csv
└── views/
    ├── facility_profile_views.xml
    └── partner_type_views.xml
```

## Dependencies
- base, contacts, mail, sale_management
- plasticos_material_profile

## Models
| Model | Description |
|-------|-------------|
| `plasticos.facility.profile` | Facility specifications and capabilities |
| `plasticos.equipment.type` | Equipment type definitions |
| `plasticos.partner.type` | Partner type classifications |

## Tier
domain
