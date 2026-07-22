# ADR-004: Navigation & Menu Architecture

**Status:** Accepted  
**Date:** 2026-03-13  
**Deciders:** Igor Beylin  
**Scope:** All PlasticOS modules

## Context

PlasticOS spans 20+ custom modules, each contributing models, views, and actions to the Odoo UI. A consistent navigation strategy is needed to decide which models get standalone sidebar menu items versus being reachable only via smart buttons, and how top-level app menus are organized.

## Decision

### Tier 1 — Standalone menu under PlasticOS root

Operational models that users browse, search, and filter as **independent lists** get a submenu under `plasticos_intake.plasticos_root_menu`:

| Module | Menu label | Sequence | Rationale |
|--------|-----------|----------|-----------|
| `plasticos_intake` | Intake | 1 | Primary workflow entry point |
| `plasticos_web_leads` | Web Leads | 10 | Triage queue, browsed independently |
| `plasticos_matching` | Matching | 20 | Match results reviewed in bulk |
| `plasticos_offer` | Offers | 25 | Pricing pipeline, browsed independently |
| `plasticos_transaction` | Transactions | 30 | Full lifecycle tracking, global view needed |
| `plasticos_partner_import` | Import Partners | 90 | Import wizard, infrequent but direct access |

### Tier 2 — Separate top-level Odoo app

Cross-cutting operational domains that serve multiple workflows and benefit from their own app namespace:

| Module | Top-level menu | Rationale |
|--------|---------------|-----------|
| `plasticos_logistics` | Logistics | Loads span transactions, partners, and carriers |
| `plasticos_documents` | Documents | Document management across all record types |
| `plasticos_claims` | Claims | Claims workflow independent of transaction flow |
| `plasticos_automation` | Automation | Cron jobs and workflow rules, admin-focused |

### Tier 3 — Smart-button-only (no standalone menu)

Models that are **contextual to a parent record** and have no meaningful "browse all" use case:

| Module | Model(s) | Reached via | Rationale |
|--------|----------|-------------|-----------|
| `plasticos_material_profile` | `plasticos.material.profile` | Smart button on partner/intake | A profile describes one facility's material spec — browsing all profiles globally is not a useful workflow |
| `plasticos_facility_profile` | `plasticos.facility.profile`, `plasticos.partner.type` | Tab on partner form | Facility details are attributes of a specific partner |

### Tier 4 — Reference data (no menu, managed via Settings or parent forms)

Master data models (polymers, colors, forms, source types) seeded via XML data files. Users extend them through the Odoo Settings UI or inline form lookups. A top-level menu would clutter navigation for rarely-touched configuration:

| Module | Model(s) | Managed via |
|--------|----------|-------------|
| `plasticos_material_profile` | `plasticos.polymer`, `plasticos.material.color`, `plasticos.material.form`, `plasticos.source.type`, etc. | Settings or inline "Create and Edit" |

### Tier 5 — Background / invisible

Modules that operate silently with no user-facing views at all:

| Module | Purpose | Rationale |
|--------|---------|-----------|
| `plasticos_intake_normalizer` | AI-powered field normalization on intake records | Runs automatically on create/write; config via `plasticos.normalizer.config` is developer-only |
| `plasticos_crm_bridge` | Extends CRM lead form with PlasticOS smart buttons | No own models, purely extends existing views |
| `plasticos_geolocalize` | Adds geocoding fields to partners | Extends partner form only |
| `plasticos_product` | Extends product views with polymer fields | Extends existing views only |
| `plasticos_order_lines` | Extends SO/PO lines with material fields | Extends existing views only |
| `plasticos_enrichment` | Partner enrichment runs | Menu under Contacts (where it belongs) |
| `plasticos_commission` | Commission calculation engine | Backend computation, no UI |
| `plasticos_security_base` | RBAC roles and record rules | Configuration only, no browsable records |
| `plasticos_dev_tools` | Developer utilities | `installable: False` in production |

## Menu Hierarchy (current state)

```
PlasticOS                          (plasticos_intake.plasticos_root_menu, seq 5)
├── Intake                         (seq 1)
├── Web Leads                      (seq 10)
│   └── All Web Leads
├── Matching                       (seq 20)
│   └── All Match Results
├── Offers                         (seq 25)
│   └── All Offers
├── Transactions                   (seq 30)
│   ├── All Transactions           (seq 1)
│   └── Import Transactions (CSV)  (seq 10)
└── Import Partners                (seq 90)

Logistics                          (separate top-level app)
├── Loads
└── ...

Documents                          (separate top-level app)
├── All Documents
└── Validation Matrix

Claims                             (separate top-level app)
└── Claims

Automation                         (separate top-level app)
├── Configuration
└── Logs
```

## Consequences

### Positive

- Users can directly browse all operational record types without hunting through smart buttons
- Logical grouping under PlasticOS keeps the sidebar manageable
- Background modules stay invisible, reducing noise

### Negative

- Adding a new operational model requires an explicit menu decision
- Tier 2 apps outside PlasticOS may feel disconnected (acceptable trade-off for their cross-cutting nature)

## Compliance

When adding a new `plasticos_*` module:

1. Determine its tier using the criteria above
2. Tier 1 modules MUST define a `<menuitem>` under `plasticos_intake.plasticos_root_menu`
3. Tier 2 modules MUST define their own top-level `<menuitem>` with `web_icon`
4. Tier 3–5 modules MUST NOT define standalone menus for their primary models
5. Document any exceptions in this ADR
