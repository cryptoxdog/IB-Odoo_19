# ADR-002: Module Installation and Display Configuration

**Status:** Accepted
**Date:** 2026-03-17
**Deciders:** Igor Beylin
**Scope:** All PlasticOS modules

## Context

PlasticOS consists of 20+ custom Odoo modules deployed on Odoo.sh. Two key manifest settings control module behavior:

1. **`installable`** — Whether the module can be installed at all
2. **`application`** — Whether the module appears as a tile on the Odoo dashboard

Incorrect configuration of these settings has caused:
- Modules not appearing in Apps list (`installable: False`)
- Dashboard clutter from unwanted app tiles (`application: True` on utility modules)
- Confusion about which modules are production-ready vs. disabled

## Decision

### Modules to Install AND Display (Dashboard Tiles)

These modules have `installable: True` AND `application: True`:

| Module | Name | Purpose |
|--------|------|---------|
| `plasticos_base` | PlasticOS Base | Main PlasticOS entry point |
| `plasticos_transaction` | Plasticos Transaction Spine | Core transaction lifecycle |
| `plasticos_claims` | PlasticOS Claims | QC cases and chargebacks |
| `plasticos_automation` | PlasticOS Automation Layer | Workflow automation |
| `plasticos_logistics` | Plasticos Logistics Engine | Load management |
| `plasticos_documents` | Plasticos Documents Engine | Document management |

### Modules to Install but NOT Display (Hidden/Utility)

These modules have `installable: True` AND `application: False`:

| Module | Name | Purpose |
|--------|------|---------|
| `plasticos_accounting` | PlasticOS Accounting | Accounting extensions |
| `plasticos_commission` | PlasticOS Commission Engine | Commission calculations |
| `plasticos_crm_bridge` | PlastOS CRM Bridge | CRM integration |
| `plasticos_facility_profile` | PlasticOS Facility Profile | Facility data |
| `plasticos_geolocalize` | PlasticOS Geolocalize | Geolocation |
| `plasticos_intake` | PlasticOS Intake | Intake forms |
| `plasticos_intake_normalizer` | Plasticos Intake Normalizer | Data normalization |
| `plasticos_material_profile` | PlasticOS Material Profile | Material master data |
| `plasticos_offer` | PlasticOS Offer | Offer management |
| `plasticos_order_lines` | PlasticOS Order Lines | Order line extensions |
| `plasticos_partner_import` | Plasticos Partner Import | Partner data import |
| `plasticos_product` | PlasticOS Product Catalog | Product extensions |
| `plasticos_security_base` | Plasticos Security Base | Security groups |
| `plasticos_web_leads` | PlasticOS Web Leads | Web lead capture |

### Modules NOT Installable (Disabled)

These modules have `installable: False`:

| Module | Reason |
|--------|--------|
| `plasticos_buyer_match_engine` | External microservice |
| `plasticos_dev_tools` | Development only |
| `plasticos_documents_native` | Requires Odoo Enterprise Documents |
| `plasticos_enrichment` | External microservice |
| `plasticos_enrichment_bridge` | External microservice |
| `plasticos_inference_engine` | External microservice |
| `plasticos_matching` | External microservice |
| `plasticos_website` | Website branding (disabled) |

## Consequences

### Positive
- Clear separation between user-facing apps and utility modules
- Dashboard shows only relevant tiles (6 PlasticOS + Contacts + CRM)
- Disabled modules don't clutter the Apps list

### Negative
- Must manually update this ADR when adding new modules
- Manifest files for displayed modules are now PROTECTED (see below)

## Protected Files

The following manifest files are **PROTECTED** and must not be modified without explicit approval:

```
plasticos_base/__manifest__.py
plasticos_transaction/__manifest__.py
plasticos_claims/__manifest__.py
plasticos_automation/__manifest__.py
plasticos_logistics/__manifest__.py
plasticos_documents/__manifest__.py
```

**Rationale:** These control dashboard display. Accidental changes cause user confusion and wasted debugging time.

## Odoo.sh Deployment Notes

1. **Modules do NOT auto-install** on Odoo.sh staging/production database rebuilds
2. After a database rebuild, install modules via:
   - Apps UI: Update Apps List → search "plasticos" → install `plasticos_base` first
   - Shell: `odoo-bin -d $PGDATABASE -i plasticos_base,plasticos_transaction,... --stop-after-init`
3. Once installed, modules persist across code pushes (only database rebuilds require reinstall)
4. **Never use `auto_install: True`** on application modules — it's for glue modules only

## References

- [Odoo.sh Branches Documentation](https://www.odoo.com/documentation/19.0/administration/odoo_sh/getting_started/branches.html)
- [Odoo Manifest Documentation](https://www.odoo.com/documentation/19.0/developer/reference/backend/module.html)
