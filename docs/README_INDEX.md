# PlasticOS IB-Odoo 19 — README Bundle Index

**Generated:** 2026-03-22
**Branch:** staging
**Scope:** Modules with significant development, debugging, and architectural work performed during the pre-launch optimization phase.

---

## Architecture & Roadmap

| File | Topic |
|---|---|
<!-- roadmap:index:architecture:start -->
| [ADR-002-gate-hub-phased-autonomy.md](ADR-002-gate-hub-phased-autonomy.md) | Why Gate is the hub, why Odoo local is fallback, what agents must not ship in Phase 1 |
| [GATE_AUTONOMY_ROADMAP.md](GATE_AUTONOMY_ROADMAP.md) | Gate → CEG matching, human-in-loop phases, autonomy graduation, implementation scope |
<!-- roadmap:index:architecture:end -->

Managed by `make roadmap` — see [roadmap/README.md](roadmap/README.md).

## Bundle Contents

| File | Module / Topic | Deploy Trigger |
|---|---|---|
| `README_plasticos_intake.md` | `plasticos_intake` — Core pipeline entry point | `-u plasticos_intake` |
| `README_plasticos_intake_normalizer.md` | `plasticos_intake_normalizer` — CEG packet assembly | `-u plasticos_intake_normalizer` |
| `README_plasticos_offer.md` | `plasticos_offer` — Offer lifecycle | `-u plasticos_offer` |
| `README_plasticos_transaction.md` | `plasticos_transaction` — Deal record, financials, compliance | `-u plasticos_transaction` |
| `README_plasticos_facility_profile.md` | `plasticos_facility_profile` — Facility capability profiles | `-u plasticos_facility_profile` |
| `README_plasticos_material_profile.md` | `plasticos_material_profile` — Material master + registries | `-u plasticos_material_profile` |
| `README_plasticos_commission.md` | `plasticos_commission` — Broker commission + payout + dashboard | `-u plasticos_commission` |
| `README_plasticos_partner_import.md` | `plasticos_partner_import` — Bulk CSV import tooling | `-u plasticos_partner_import` |
| `README_backup_github_actions.md` | GitHub Actions S3 disaster recovery | N/A — infra |

---

## Module Dependency Chain (simplified)

```
plasticos_base
  └─ plasticos_material_profile          ← owns PROCESS_SELECTION, is_facility field
       └─ plasticos_facility_profile     ← facility capability profiles
            └─ plasticos_intake          ← pipeline entry
                 └─ plasticos_intake_normalizer
                 └─ plasticos_offer      ← offer lifecycle
                      └─ plasticos_transaction  ← deal record
                           └─ plasticos_commission  ← broker payout
                           └─ plasticos_logistics
                           └─ plasticos_accounting
  └─ plasticos_security_base             ← groups, ACL base
  └─ plasticos_partner_import            ← standalone import tooling
```

---

## Critical Architecture Decisions (Cross-Module)

### 1. `process_codes.py` lives in `plasticos_material_profile`
Canonical import: `from odoo.addons.plasticos_material_profile.process_codes import PROCESS_SELECTION`
Do NOT move it back to `plasticos_facility_profile` — circular dependency.

### 2. `is_facility` computed field lives in `plasticos_material_profile`
Both `plasticos_facility_profile` and `plasticos_intake` use this field for tab visibility and facility selection. It is defined once in `plasticos_material_profile.models.res_partner`. Do not redefine.

### 3. `action_view_claims()` lives in `plasticos_claims` bridge
The claims bridge uses `_inherit = 'plasticos.transaction'` to inject this method. Do not add it to `transaction.py` — it would shadow the bridge and break module separation.

### 4. Boolean material flags (`has_metal`, `is_metalized`, `has_fr`) are computed
These are `@api.depends('material_attribute_ids')`, `store=True`. `material_attribute_ids` is the single source of truth. Old bidirectional `onchange` sync was removed. Do not reintroduce separate stored booleans.

### 5. `plasticos.material.profile` has no `name` field
Profile identity = `(partner_id, polymer_id)`. Never set `name` in create vals. Use `display_name` for chatter body.

### 6. x_ field cleanup completed
All `x_` prefixed fields were migration artifacts. All live code references corrected:
- `x_preferred_contact_id` → `preferred_contact_id` (intake, contract tests)
- `x_vanillasoft_id` → `vanillasoft_id` (partner import)
- `x_facility_role` → `facility_role` (partner import wizard)
- `x_plasticos_doc_id` etc. → cleaned in `documents_native` and `documents`

---

## Ignored / Out-of-Scope Modules

These are **gitignored and cursorignored**. Do not reference, import from, or add dependencies to them:

| Module | Reason |
|---|---|
| `plasticos_buyer_match_engine` | Future microservice — external repo (`Cognitive.Engine.Graphs`) |
| `plasticos_inference_engine` | Future microservice — `pipeline_v2.py` is broken, never activate |
| `plasticos_graph_engine` | Future microservice |
| `plasticos_graph_intelligence` | Future microservice |
| `plasticos_graph_integration` | Future microservice |
| `plasticos_graph_3d_embedding` | Future microservice |
| `plasticos_enrichment` | Out of scope for launch |
| `plasticos_enrichment_bridge` | Out of scope for launch |
| `plasticos_website` | Out of scope for launch |
| `plasticos_dev_tools` | Dev-only — never install in production |
| `plasticos_documents_native` | Uninstallable — enterprise layer fallback |

---

## Active Crons (as of 2026-03-17)

16 active PlasticOS crons confirmed in DB. Key ones:

| Cron | Module | Schedule |
|---|---|---|
| PlasticOS Invoice Overdue Reminder | `plasticos_accounting` | Daily |
| PlasticOS Load SLA Breach Check | `plasticos_logistics` | Daily |
| PlasticOS Supplier Readiness Follow-up | `plasticos_automation` | Every 6 hours |
| PlasticOS Sale Approval Flag | `plasticos_transaction` | Daily |
| PlasticOS Midnight Time-Based Field Recompute | `plasticos_transaction` | Daily 00:05 |
| PlasticOS Offer Expiry | `plasticos_offer` | Daily |
| PlasticOS Contract Renewal Alert | `plasticos_automation` | Daily |
| PlasticOS Escalation Monitor | `plasticos_automation` | Every 2 hours |

---

## Config Parameters Required Before Go-Live

| Key | Module | Description |
|---|---|---|
| `plasticos.graphengine.url` | `plasticos_intake` | CEG endpoint URL |
| `plasticos.graphengine.apikey` | `plasticos_intake` | CEG bearer token |
| `plasticos.matching.engine.enabled` | `plasticos_intake` | `True` to enable live matching |
| `plasticos.offer.expiry_days` | `plasticos_offer` | Default: 14 |
| `plasticos.intake.expiry_days` | `plasticos_intake` | Default: 90 |
| `plasticos.commission.default_rate_pct` | `plasticos_commission` | Fallback rate if no rule matches |

---

## Go-Live Gates

- [ ] Remove `--dev=reload` from `docker-compose.yml` command
- [ ] Set `admin_passwd` to non-default strong password in `odoo.conf`
- [ ] Set `list_db = False` in `odoo.conf`
- [ ] Set `db_filter = ^odoo$` in `odoo.conf`
- [ ] Set `proxy_mode = True` (behind nginx)
- [ ] Set `workers = 2`, `max_cron_threads = 1` in `odoo.conf`
- [ ] Confirm `plasticos_dev_tools` is uninstallable/disabled
- [ ] CEG config params set in Settings → Technical → System Parameters
- [ ] GitHub Actions backup workflow deployed and first backup confirmed in S3

