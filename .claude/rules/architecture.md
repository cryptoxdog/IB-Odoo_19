---
paths:
  - "plasticos_*/__manifest__.py"
  - "plasticos_*/models/**/*.py"
  - "config/**"
---
# PlasticOS Architecture — 5-Layer Module Map

## Layer Hierarchy (lower → higher, never reverse dependencies)

```
Layer 5: TRANSACTION
  plasticos_transaction, plasticos_logistics, plasticos_claims

Layer 4: COMPLIANCE
  plasticos_documents, plasticos_documents_native

Layer 3: COMMERCIAL
  plasticos_accounting, plasticos_offer, plasticos_order_lines
  plasticos_automation, plasticos_partner_import, plasticos_crm_bridge, plasticos_commission

Layer 2: CAPABILITY
  plasticos_facility_profile, plasticos_intake, plasticos_intake_normalizer
  plasticos_matching, plasticos_buyer_match_engine, plasticos_geolocalize
  plasticos_enrichment, plasticos_web_leads, plasticos_inference_engine

Layer 1: MATERIAL
  plasticos_base, plasticos_security_base
  plasticos_material_profile, plasticos_product
```

## Module Install Order (config/odoo_module_order.yaml)
Default: accounting → base → material_profile → logistics → facility_profile → intake → product → order_lines → transaction → documents → offer → claims → automation → intake_normalizer → partner_import → geolocalize → security_base

## Handler Pattern (engine/handlers.py equivalents)
Each module's `models/` directory contains:
- Main model (e.g., `transaction.py`)
- Bridge models (e.g., `intake_bridge.py`, `offer_bridge.py`)
- Service classes (e.g., `commission_service.py`, `transaction_import_service.py`)
- Odoo model inherits (e.g., `sale_inherit.py`, `purchase_inherit.py`)

## Manifest Rules
- `depends`: list ALL modules whose models you reference
- `data`: list ALL XML/CSV files for seed data and views
- `pre_init_hook` / `post_init_hook`: only for migration/cleanup
- `installable`: False for dev-only and external microservice modules
