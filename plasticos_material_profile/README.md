---
component_id: "PLASTICOS-MATERIAL-001"
component_name: "PlasticOS Material Profile"
module_version: "19.0.1.0.0"
layer: "domain"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Material taxonomy - polymers, forms, colors, sources"
summary: "Material specification and classification"
---

# PlasticOS Material Profile

## Purpose
Comprehensive material taxonomy for plastics industry including polymers, forms, colors, and sources.

## Summary
- Polymer definitions (PE, PP, PET, etc.)
- Material forms (pellet, regrind, flake, etc.)
- Color classifications
- Source types (post-consumer, post-industrial, etc.)
- Process types

## Structure
```
├── __init__.py
├── __manifest__.py
├── data/
│   ├── material_color_data.xml
│   ├── material_form_data.xml
│   ├── polymer_data.xml
│   ├── process_type_data.xml
│   └── source_type_data.xml
├── models/
│   ├── material_color.py
│   ├── material_form.py
│   ├── material_profile.py
│   ├── polymer.py
│   ├── process_type.py
│   └── source_type.py
├── security/
│   └── ir.model.access.csv
└── views/
    ├── material_color_views.xml
    ├── material_form_views.xml
    ├── material_profile_views.xml
    ├── polymer_views.xml
    ├── process_type_views.xml
    └── source_type_views.xml
```

## Dependencies
- base, contacts, mail

## Models
| Model | Description |
|-------|-------------|
| `plasticos.material.profile` | Complete material specification |
| `plasticos.polymer` | Polymer type definitions |
| `plasticos.material.form` | Material form classifications |
| `plasticos.material.color` | Color definitions |
| `plasticos.source.type` | Source type (post-consumer, etc.) |
| `plasticos.process.type` | Processing type definitions |

## Tier
domain
