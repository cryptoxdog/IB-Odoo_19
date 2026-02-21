---
component_id: "PLASTICOS-NORMALIZER-001"
component_name: "PlasticOS Intake Normalizer"
module_version: "19.0.1.0.0"
layer: "automation"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Batch normalization of intake records"
summary: "Material specification standardization"
---

# PlasticOS Intake Normalizer

## Purpose
Batch normalization of intake records to standardize material specifications.

## Summary
- Normalizer configuration
- Batch processing cron
- Material specification standardization

## Structure
```
├── __init__.py
├── __manifest__.py
├── data/
│   ├── cron_batch_normalize.xml
│   └── normalizer_config_data.xml
├── models/
│   └── normalizer_config.py
├── security/
│   └── ir.model.access.csv
└── views/
    ├── intake_normalizer_views.xml
    └── normalizer_config_views.xml
```

## Dependencies
- plasticos_intake, plasticos_material_profile, plasticos_base

## Models
| Model | Description |
|-------|-------------|
| `plasticos.normalizer.config` | Normalization configuration |

## Tier
automation
