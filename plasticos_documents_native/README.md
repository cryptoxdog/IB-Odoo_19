---
component_id: "PLASTICOS-DOCS-NATIVE-001"
component_name: "PlasticOS Documents Native"
module_version: "19.0.1.0.0"
layer: "compliance"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Native Odoo Documents integration"
summary: "Odoo Documents module bridge"
---

# PlasticOS Documents Native

## Purpose
Bridge module for native Odoo Documents integration with PlasticOS workflows.

## Summary
- Document folder structure
- Document tag synchronization
- Native Documents module integration

## Structure
```
├── __init__.py
├── __manifest__.py
├── data/
│   ├── document_folders.xml
│   └── document_tags.xml
├── models/
│   └── document_sync.py
├── security/
│   └── ir.model.access.csv
└── views/
    └── document_native_views.xml
```

## Dependencies
- documents, documents_account
- plasticos_documents, plasticos_logistics, plasticos_transaction
- plasticos_intake, plasticos_material_profile, plasticos_security_base

## Models
| Model | Description |
|-------|-------------|
| `plasticos.document.sync` | Document synchronization service |

## Tier
compliance
