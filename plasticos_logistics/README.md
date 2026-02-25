---
component_id: "plasticos_logistics"
component_name: "Plasticos Logistics"
module_version: "19.0.1.0.0"
layer: "core"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Load management, dispatch, and delivery tracking"
summary: "Logistics coordination with trucker communications"
---

# Plasticos Logistics

## Purpose
Load management, dispatch, and delivery tracking

## Summary
Logistics coordination with trucker communications

## Structure
```
BOL - DELIVERY-59422.pdf
BOL - PICKUP-59422.pdf
DELIVERY ORDER-59422.pdf
README.rst
__init__.py
__manifest__.py
data/
models/
report/
security/
services/
templates for logistics/
views/
wizards/
```

## Dependencies
sale_management, stock, mail

## Models
plasticos.dispatch, plasticos.rate.memory, plasticos.load

## Tier
core
