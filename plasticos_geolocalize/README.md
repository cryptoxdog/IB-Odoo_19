---
component_id: "PLASTICOS-GEO-001"
component_name: "PlasticOS Geolocalize"
module_version: "19.0.1.0.0"
layer: "automation"
domain: "plasticos"
type: "odoo_module"
status: "active"
purpose: "Geolocation backfill for intakes"
summary: "Address geocoding automation"
---

# PlasticOS Geolocalize

## Purpose
Automated geolocation backfill for intake records using address data.

## Summary
- Geocoding automation
- Coordinate backfill cron
- Integration with base_geolocalize

## Structure
```
├── __init__.py
├── __manifest__.py
├── data/
│   └── cron_geo_backfill.xml
└── views/
    └── intake_geo_views.xml
```

## Dependencies
- base, base_geolocalize
- plasticos_intake

## Tier
automation
