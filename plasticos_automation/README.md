---
component_id: "PLASTICOS-AUTOMATION-001"
component_name: "PlasticOS Automation Layer"
module_version: "19.0.2.0.0"
layer: "automation"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Workflow automation, crons, and email triggers"
summary: "Automated workflows and notifications"
---

# PlasticOS Automation Layer

## Purpose
Deterministic workflow automation: approvals, reminders, logistics follow-ups, SLA monitoring.

## Summary
Automated workflows and notifications including:
- Sale approval automation
- Invoice reminders
- Contract renewal alerts
- Stock reorder alerts
- Supplier/trucker follow-ups
- Load SLA monitoring

## Structure
```
├── __init__.py
├── __manifest__.py
├── data/
│   ├── automation_config_data.xml
│   ├── config_parameters.xml
│   ├── cron_*.xml (multiple cron jobs)
│   ├── email_templates.xml
│   └── workflow_automations.xml
├── models/
│   ├── automation_config.py
│   ├── automation_log.py
│   ├── purchase_order_automation.py
│   ├── sale_order_automation.py
│   └── stock_picking_automation.py
├── security/
│   ├── ir.model.access.csv
│   └── security.xml
└── views/
    ├── automation_config_views.xml
    ├── automation_log_views.xml
    └── stock_picking_views.xml
```

## Dependencies
- base, mail, sale_management, account, stock, purchase
- plasticos_logistics, plasticos_transaction, plasticos_claims

## Models
| Model | Description |
|-------|-------------|
| `plasticos.automation.config` | Automation configuration settings |
| `plasticos.automation.log` | Automation execution log |

## Key Features
- **Trucker Tracking**: Follow-up automation for delivery confirmations
- **Email Templates**: 13 pre-configured email templates
- **Cron Jobs**: 8 scheduled automation tasks
- **Workflow Automations**: 4 base.automation rules

## Tier
automation
