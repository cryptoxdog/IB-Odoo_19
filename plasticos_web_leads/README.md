---
component_id: "PLASTICOS-WEB-LEADS-001"
component_name: "PlasticOS Web Leads"
module_version: "19.0.1.0.0"
layer: "integration"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Web lead capture and routing"
summary: "Inbound lead processing"
---

# PlasticOS Web Leads

## Purpose
Web lead capture and routing for inbound material inquiries.

## Summary
- Web form lead capture
- Lead configuration
- Routing rules
- Integration with intake workflow

## Structure
```
├── __init__.py
├── __manifest__.py
├── data/
│   ├── logistics_ir_rules.xml
│   └── web_lead_config_data.xml
├── models/
│   ├── web_lead.py
│   └── web_lead_config.py
├── security/
│   └── ir.model.access.csv
└── views/
    ├── web_lead_config_views.xml
    └── web_lead_views.xml
```

## Dependencies
- base, mail
- plasticos_intake, plasticos_material_profile, purchase

## Models
| Model | Description |
|-------|-------------|
| `plasticos.web.lead` | Captured web lead |
| `plasticos.web.lead.config` | Lead routing configuration |

## Tier
integration
