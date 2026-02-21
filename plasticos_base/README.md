---
component_id: "PLASTICOS-BASE-001"
component_name: "PlasticOS Base"
module_version: "19.0.1.0.0"
layer: "foundation"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Base configuration, tags, and sales rep assignments"
summary: "Foundation data and partner categorization"
---

# PlasticOS Base

## Purpose
Base configuration module providing foundation data for all PlasticOS modules.

## Summary
- Material taxonomy tags
- Partner categorization tags
- Sales representative assignments

## Structure
```
├── __init__.py
├── __manifest__.py
└── data/
    ├── material_taxonomy.xml
    ├── partner_tags.xml
    └── sales_reps.xml
```

## Dependencies
- base, contacts, sale_management

## Tier
foundation
