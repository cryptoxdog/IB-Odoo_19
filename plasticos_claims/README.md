---
auto_generated: false
authority: derived-index
component_id: plasticos_claims
component_name: PlasticOS Claims
module_version: 19.0.1.1.10
layer: 5
installable: true
auto_install: true
application: true
depends:
  - base
  - mail
  - plasticos_base
  - plasticos_transaction
  - plasticos_documents
  - plasticos_logistics
models_owned:
  - plasticos.claim
  - plasticos.claim.bulk.update.wizard
models_extended:
  - plasticos.transaction
  - plasticos.document
  - plasticos.midnight.recompute
crons:
  - cron_claim_sla_check
---

# PlasticOS Claims

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` and `wizards/` win on any conflict.

## What it does

QC cases, buyer claims, freight chargebacks, and lightweight penalties against a transaction, with an SLA, escalation, reminders, and a resolution record.

## How it works

- **Case.** `plasticos.claim` (`models/claim.py`) carries a `case_type` (buyer claim, inspection, freight chargeback, lightweight penalty, other), a `severity`, an assignee, an SLA in hours, and an optional `source_document_id`.
- **State machine.** `state` is `pending` → `in_progress` → `escalated` → `resolved` → `archived`. The commands are `action_start`, `action_escalate`, `action_resolve`, `action_archive`, and `action_reopen`.
- **SLA cron.** `_cron_check_sla` takes the Postgres advisory lock `plasticos_claims.cron_claim_sla_check`, recomputes `is_overdue` for open claims, escalates `pending` claims past `opened_at + sla_hours`, and creates at most one reminder activity per open claim per day. It returns at once when another worker holds the lock.
- **Claim from a document.** The `plasticos.document` extension (`models/document_inherit.py`) creates one `buyer_claim` when a document tagged `claim_pics`, `claim_photo`, or `claim` is attached to a resolvable transaction, and links it through `source_document_id`. A second save does not create a second claim.
- **Transaction side.** `models/transaction_claims.py` adds claim counts, a quality-claim flag, and chargeback and penalty totals to `plasticos.transaction`. `models/transaction_claims_bridge.py` adds `action_view_claims()`.
- **Time fields.** The `plasticos.midnight.recompute` extension recomputes claim time-based fields in the nightly pass.
- **Bulk edits.** The transient `plasticos.claim.bulk.update.wizard` changes status, assigns, or escalates many claims at once.
- **Install hook.** `post_init_hook` in `hooks.py` adds `group_claims_manager` to `plasticos_base.user_system_cron` so the SLA cron runs with claims access.

The claim sequence, mail templates, menus, and the transaction bridge view are data for this workflow.

## Models

| Model                                | Kind                | File                                                    |
| ------------------------------------ | ------------------- | ------------------------------------------------------- |
| `plasticos.claim`                    | owned               | `models/claim.py`                                       |
| `plasticos.claim.bulk.update.wizard` | owned, transient    | `wizards/claim_bulk_update_wizard.py`                   |
| `plasticos.transaction`              | extended (2 files)  | `transaction_claims.py`, `transaction_claims_bridge.py` |
| `plasticos.document`                 | extended            | `models/document_inherit.py`                            |
| `plasticos.midnight.recompute`       | extended (abstract) | `models/midnight_recompute.py`                          |

## Runtime

- Cron: `cron_claim_sla_check`, hourly, `active` true in `data/claim_cron.xml`.
- `auto_install` and `application` are true.

## Boundaries

- It does not post invoices or credit notes. Chargeback and penalty totals are reported on the transaction.
- Document verification belongs to `plasticos_documents`. This module only reacts to a claim-photo tag.
- `action_view_claims()` lives in the bridge file, not in `plasticos_transaction`.

## Read next

- [`models/claim.py`](models/claim.py)
- [`models/document_inherit.py`](models/document_inherit.py)
- [`../plasticos_documents/README.md`](../plasticos_documents/README.md)
