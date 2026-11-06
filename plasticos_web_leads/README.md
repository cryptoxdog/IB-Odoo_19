---
auto_generated: false
authority: derived-index
component_id: plasticos_web_leads
component_name: PlasticOS Web Leads
module_version: 19.0.2.8.9
layer: 2
installable: true
auto_install: true
application: false
depends:
  - base
  - mail
  - utm
  - plasticos_facility_profile
  - plasticos_intake
  - plasticos_material_profile
  - purchase
models_owned:
  - plasticos.web.lead
  - plasticos.web.lead.config
  - plasticos.web.lead.review.snapshot
  - plasticos.web.lead.api.key.wizard
  - plasticos.web.lead.bulk.action.wizard
models_extended:
  - plasticos.web.lead
crons: []
---

# PlasticOS Web Leads

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` and `wizards/` win on any conflict.

## What it does

Takes inbound web-form submissions from a provider, normalizes them, and classifies each one HOT or COLD inside Odoo. A HOT lead becomes an intake for a broker to review. Triage stays in Odoo; it is not sent to Gate.

## How it works

- **Inbound port.** `controllers/web_lead_api.py` serves:
  - `POST /api/v1/web-lead/inbound/<provider_key>`: the provider-neutral entry;
  - `POST /api/v1/cognito-webhook`: an alias for the `cognito` provider;
  - `GET /api/v1/web-lead/health`: a health check that returns no secrets.
    The two POST routes compare a presented token with the `api_key` stored on `plasticos.web.lead.config` in constant time. Bad JSON returns 400, an unknown provider 404, a failed token 401. A payload the adapter rejects is recorded as a rejected lead and answered with 200.
- **Adapters.** `adapters/registry.py` maps a provider key to an adapter and fails closed for any other key. `adapters/cognito.py` is the only adapter. `adapters/base.py` defines the port, the inbound packet, and serialization that strips signed attachment URLs.
- **Admission.** `plasticos.web.lead.admit_inbound(provider_key, body)` (`models/web_lead.py`) classifies the provider event. A non-submission event creates or changes nothing. A submission becomes a packet and goes to `create_from_packet`, which is idempotent on the packet's idempotency key and creates the lead in state `received`. `create_from_cognito()` is a compatibility shim that calls `admit_inbound("cognito", ...)`.
- **Triage pipeline**, in order:
  - quantity normalization;
  - optional AI text normalization (`ai_enabled`);
  - optional attachment download and vision (`vision_enabled`);
  - evidence reconciliation;
  - economic eligibility;
  - classification in `models/classification_engine.py`, the deterministic HOT/COLD authority;
  - an advisory economic assessment.
    HOT goes to `_process_hot_lead_triage`; COLD sets `skipped`; an exception sets `error`.
- **HOT.** `_process_hot_lead_triage` creates a `plasticos.intake` with a pending company name and no partner, sets `state` to `intake_created`, and notifies the admin. This module defines no partner-creating helper; a partner is set later on the intake or the Opportunity.
- **CRM lead.** After a HOT intake, the lead calls `_create_crm_lead` only when that method exists. `plasticos_crm_bridge` provides it. This module does not depend on `plasticos_crm_bridge`.
- **Internal review handoff.** `mack_review_state` (`not_queued`, `queued`, `blocked`) records the internal review handoff for a HOT intake. Its help text says the field does not call Mack, matching, Gate, or any commercial operation.
- **Review snapshot.** `plasticos.web.lead.review.snapshot` records broker approval. Approval needs an internal user with write access, a HOT lead with an intake whose `source_lead_id` is this lead, and a completed economic assessment. Snapshots are created only through the approval path, their key fields are immutable, and they cannot be deleted.
- **Configuration.** `plasticos.web.lead.config` is the singleton seeded in `data/web_lead_config_data.xml`. It holds thresholds (`hot_min_lbs`, `cold_max_lbs`, `reusable_item_hot_min_lbs`), the reusable-item codes (default `PLASTIC_PALLETS`, `PALLETS`, `TOTES`, `CRATES`), the AI switches, and the per-role inference provider choices and their keys (system administrators only). `plasticos.web.lead.api.key.wizard` sets the inbound API key.
- **Bulk actions.** `plasticos.web.lead.bulk.action.wizard` acts on many leads at once.

## Record guards

- Once a lead's `state` is `intake_created`, `write` accepts only `state`, `error_message`, `triage_log`, the review fields (`review_status`, `review_notes`, `review_required_reason`), `review_snapshot_ids`, `crm_lead_id`, `mack_review_state`, and `mack_review_reason`. Any other field raises `UserError`, also when the same write changes `state`.
- `unlink` raises when `state` is `intake_created`. It checks `state`, not `intake_id`.

States: `received`, `intake_created`, `skipped`, `error`.

## Models

| Model                                   | Kind             | File                                 |
| --------------------------------------- | ---------------- | ------------------------------------ |
| `plasticos.web.lead`                    | owned            | `models/web_lead.py`                 |
| `plasticos.web.lead.config`             | owned            | `models/web_lead_config.py`          |
| `plasticos.web.lead.review.snapshot`    | owned            | `models/web_lead_review_snapshot.py` |
| `plasticos.web.lead.api.key.wizard`     | owned, transient | `models/web_lead_api_key_wizard.py`  |
| `plasticos.web.lead.bulk.action.wizard` | owned, transient | `wizards/lead_bulk_action_wizard.py` |
| `plasticos.web.lead`                    | extended         | `models/web_lead_bridge.py`          |

## Runtime

- No cron.
- Python dependencies: `anthropic`, `openai`, `requests` (manifest `external_dependencies`).
- `requests` is used only to download inbound attachments. HTTPS only, allowlisted hosts, public addresses, at most 10 files and 10 MB each.
- LLM calls happen only when the matching switch is on and the selected provider has a key.
- `data/logistics_ir_rules.xml` adds a logistics group and its record rules.
- `auto_install` is true.

## Boundaries

- No Gate call and no matching. Web-lead triage stays in Odoo.
- No partner creation.
- AI output is advisory input to the deterministic classifier, not a routing authority.
- Keys live in the config record, never in this repository.

## Read next

- [`models/web_lead.py`](models/web_lead.py)
- [`models/classification_engine.py`](models/classification_engine.py)
- [`controllers/web_lead_api.py`](controllers/web_lead_api.py)
- [`../tests/test_web_lead_adapter_contract.py`](../tests/test_web_lead_adapter_contract.py)
