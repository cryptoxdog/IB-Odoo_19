---
auto_generated: false
authority: derived-index
component_id: plasticos_crm_sync
component_name: PlasticOS CRM Sync
module_version: 19.0.1.9.30
installable: true
auto_install: true
application: false
depends:
  - base
  - base_setup
  - crm
  - mail
  - utm
  - plasticos_base
  - plasticos_security_base
  - plasticos_material_profile
  - plasticos_crm_bridge
  - plasticos_facility_profile
models_owned:
  - plasticos.crm.connection
  - plasticos.crm.sync.run
  - plasticos.crm.sync.orphan
  - plasticos.crm.call.event
  - plasticos.crm.external.ref
  - plasticos.crm.external.table.row
models_extended:
  - res.partner
  - crm.lead
  - res.config.settings
crons:
  - cron_crm_sync_all
---

# PlasticOS CRM Sync

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` win on any conflict. `AGENTS.md` Project Structure does not list this module, so no layer is recorded here.

## What it does

API-first sync from an external CRM into Odoo. VanillaSoft is the only live provider. An unknown provider fails closed.

## How it works

- **Connection.** `plasticos.crm.connection` names a provider and holds its sync state. `action_test_connection`, `action_sync_now`, and `_cron_sync_all` are the entry points.
- **Adapter.** `adapters/registry.py` `get_adapter()` is the single admission point. It returns the VanillaSoft adapter (`adapters/vanillasoft/`) when the API key, root endpoint, and project id are all set, and raises `CrmAdapterError` for any other provider. There are no stub adapters.
- **Orchestrator.** `services/orchestrator.py` `SyncOrchestrator` is the DTO-to-ORM write path. `run_connection` takes a session advisory lock per connection, so the cron and the manual button exclude each other. It advances watermarks, buffers records it cannot place as `plasticos.crm.sync.orphan`, resolves approved identities through the crosswalk in `services/approved_identity.py`, maps owners in `services/owner_crosswalk.py`, and writes call history as `plasticos.crm.call.event`.
- **Records.** `plasticos.crm.sync.run` records each run. `plasticos.crm.external.ref` maps a provider id to an Odoo record. `plasticos.crm.external.table.row` stores provider custom-table rows against a lead.
- **Webhook.** `controllers/webhook.py` serves `POST /plasticos/crm_sync/vanillasoft/weblead`. It returns 401 unless the request token matches the `plasticos_crm_sync.webhook_token` system parameter.
- **Settings.** The `res.config.settings` extension stores the VanillaSoft credentials as system parameters.
- **Data.** `data/approved_contact_crosswalk.csv` is read by `services/approved_identity.py`. `data/vanillasoft_material_mapping.csv` is read by `scripts/build_material_mapping.py` at the repository root. Neither file is in the manifest `data` list.

## Operator command

`make import-vanillasoft` pipes [`scripts/import_vanillasoft_shell.py`](scripts/import_vanillasoft_shell.py) into `odoo shell` on `ODOO_DB_NAME`. It requires `VANILLASOFT_CALL_FLOOR`, runs a fail-closed preflight before any write, and writes a machine-readable summary (default `.l9/pr/import-vanillasoft-summary.json`). This is the command; it is not evidence that a live sync has run.

## Models

| Model                              | Kind                | File                               |
| ---------------------------------- | ------------------- | ---------------------------------- |
| `plasticos.crm.connection`         | owned               | `models/crm_connection.py`         |
| `plasticos.crm.sync.run`           | owned               | `models/crm_sync_run.py`           |
| `plasticos.crm.sync.orphan`        | owned               | `models/crm_sync_orphan.py`        |
| `plasticos.crm.call.event`         | owned               | `models/crm_call_event.py`         |
| `plasticos.crm.external.ref`       | owned               | `models/crm_external_ref.py`       |
| `plasticos.crm.external.table.row` | owned               | `models/crm_external_table_row.py` |
| `res.partner`                      | extended            | `models/res_partner_sync.py`       |
| `crm.lead`                         | extended            | `models/crm_lead_sync.py`          |
| `res.config.settings`              | extended, transient | `models/res_config_settings.py`    |

## Runtime

- Cron: `cron_crm_sync_all`, hourly, `active` false in `data/ir_cron_data.xml`. It calls `plasticos.crm.connection._cron_sync_all()` as `plasticos_base.user_system_cron`.
- `auto_install` is true. Odoo installs it once every dependency is installed.

## Boundaries

- No provider other than VanillaSoft is admitted.
- It does not match, score, or create offers. Opportunities it touches go through `plasticos_crm_bridge`.
- Credentials live in system parameters, never in this repository.

## Read next

- [`services/orchestrator.py`](services/orchestrator.py)
- [`adapters/registry.py`](adapters/registry.py)
- [`../plasticos_crm_bridge/README.md`](../plasticos_crm_bridge/README.md)
