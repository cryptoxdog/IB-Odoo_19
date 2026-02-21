---
component_id: "PLASTICOS-DEV-TOOLS-001"
component_name: "PlasticOS Dev Tools"
module_version: "19.0.1.0.0"
layer: "dev"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Development utilities, validators, and test tools"
summary: "Developer tooling and forbidden/quarantined code"
---

# PlasticOS Dev Tools

## Purpose
Development utilities including validators, test tools, and quarantined legacy code.

## Summary
- Index export tools
- Seed validators
- Test utilities
- Forbidden/quarantined code (not for production)

## Structure
```
├── __init__.py
├── __manifest__.py
├── forbidden/           # Quarantined legacy code
│   ├── README.md
│   ├── offer_handler.py
│   ├── system_state_registry_v6.0C.py
│   ├── trust_index_calculator_v6.0C.py
│   └── ... (other deprecated files)
├── tests/
│   ├── README.md
│   └── test_*.py
└── tools/
    ├── index_export.py
    └── seed_validator.py
```

## Dependencies
- base

## ⚠️ Warning
The `forbidden/` directory contains quarantined code that is NOT production-ready.
These files are preserved for reference but should not be used in production.

## Tier
dev
