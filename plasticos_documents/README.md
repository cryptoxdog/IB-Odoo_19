---
auto_generated: false
authority: derived-index
component_id: plasticos_documents
component_name: Plasticos Documents Engine
module_version: 19.0.2.1.15
layer: 4
installable: true
auto_install: true
application: true
depends:
  - base
  - mail
  - plasticos_base
  - plasticos_transaction
  - plasticos_logistics
models_owned:
  - plasticos.document
  - plasticos.document.rule
  - plasticos.document.tag
  - plasticos.document.validation.matrix
  - plasticos.compliance.service
models_extended:
  - ir.attachment
  - plasticos.transaction
  - plasticos.load
  - account.move
  - plasticos.midnight.recompute
crons:
  - cron_document_compliance_check
  - cron_check_missing_docs
  - cron_check_scale_tickets
---

# Plasticos Documents Engine

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` win on any conflict.

## What it does

Owns business document evidence for PlasticOS: which documents a transaction, load, order, or transfer needs; which documents are attached to exactly that subject; and whether each one is verified or overridden.

## How it works

- **Evidence row.** `plasticos.document` (`models/document.py`) links one file to one business subject (`res_model`, `res_id`) with a `tag_id`. Allowed subjects are `plasticos.transaction`, `plasticos.load`, `purchase.order`, `sale.order`, and `stock.picking`. `association_state` is `pending`, `accepted`, or `review`. Verification (`verified`, `verified_by`, `verified_at`) and manager override (`override`, `override_reason`, `override_by`) are recorded on the row.
- **Requirements.** `plasticos.document.rule` says which tag a model needs, optionally per purpose. `plasticos.document.tag` is the document type (BOL, invoice, scale ticket, photo, and others seeded in `data/document_tags_data.xml`). `plasticos.document.validation.matrix` holds ordered validation entries.
- **Missing documents.** `plasticos.compliance.service.get_missing_documents(res_model, res_id, purpose=None)` searches active rules for that model, then counts only documents on that exact record whose `association_state` is `accepted` and that are verified or overridden.
- **Transactions and loads.** `models/transaction_docs.py` adds document tracking and activities to `plasticos.transaction` and a scale-ticket check to `plasticos.load`. `models/transaction_docs_bridge.py` and `models/load_docs_bridge.py` add the bridge fields shown in the transaction and load views. The `account.move` extension reports document compliance on invoices.
- **Attachments.** The `ir.attachment` extension tracks evidence revisions.
- **Nightly pass.** The `plasticos.midnight.recompute` extension refreshes the stored document expiry flag and the transactions those rows name.
- **Install hook.** `post_init_hook` in `hooks.py` adds `group_documents_manager` to `plasticos_base.user_system_cron`.

## Models

| Model                                  | Kind                | File                                                |
| -------------------------------------- | ------------------- | --------------------------------------------------- |
| `plasticos.document`                   | owned               | `models/document.py`                                |
| `plasticos.document.rule`              | owned               | `models/document_rule.py`                           |
| `plasticos.document.tag`               | owned               | `models/document_tag.py`                            |
| `plasticos.document.validation.matrix` | owned               | `models/document_validation_matrix.py`              |
| `plasticos.compliance.service`         | owned, abstract     | `models/compliance_service.py`                      |
| `ir.attachment`                        | extended            | `models/document.py`                                |
| `plasticos.transaction`                | extended            | `transaction_docs.py`, `transaction_docs_bridge.py` |
| `plasticos.load`                       | extended            | `transaction_docs.py`, `load_docs_bridge.py`        |
| `account.move`                         | extended            | `models/transaction_docs_bridge.py`                 |
| `plasticos.midnight.recompute`         | extended (abstract) | `models/midnight_recompute.py`                      |

## Runtime

| Cron                             | File                         | Method                     | `active` |
| -------------------------------- | ---------------------------- | -------------------------- | -------- |
| `cron_document_compliance_check` | `data/cron.xml`              | `_cron_compliance_audit`   | false    |
| `cron_check_missing_docs`        | `data/cron_missing_docs.xml` | `cron_check_missing_docs`  | true     |
| `cron_check_scale_tickets`       | `data/scale_ticket_rule.xml` | `cron_check_scale_tickets` | true     |

Installing the module loads these records. It does not prove that any of them has run on a database.

`auto_install` and `application` are true.

## Boundaries

From [`AGENTS.md`](AGENTS.md):

- This module owns business evidence, verification and compliance policy, and exact links.
- It does not own native Enterprise document originals (`plasticos_documents_native`), external document-chasing sends (Linda, `plasticos_logistics`), physical inventory, commercial orders, or invoice posting.
- No invoice auto-post from a compliance recompute or a document upload. No fuzzy association.

## Requirements

The Documents BRS lives in [`business_rules/`](business_rules/README.md). The registry holds 44 installed verbatim rule texts. After the dated supersession in [`business_rules/SUPERSESSION.md`](business_rules/SUPERSESSION.md), 37 remain Documents-owned. External-send rules `BRS-POS-09-R006` through `BRS-POS-09-R012` moved to `plasticos_logistics`. Read that README before changing Documents code.

## Read next

- [`AGENTS.md`](AGENTS.md)
- [`business_rules/README.md`](business_rules/README.md)
- [`models/compliance_service.py`](models/compliance_service.py)
- [`../plasticos_documents_native/README.md`](../plasticos_documents_native/README.md)

<!-- prettier-ignore-start -->
<!-- PLASTICOS_DOCUMENTS_BRS_NATIVE_FIRST_20261026_BEGIN -->
## Native-first BRS policy (2026-10-26)

The module-local [Documents BRS](business_rules/README.md) is the implementation requirements index for business evidence, exact association, verification, internal Documents Requests, native automation clocks and finance side-effect prohibitions. Its 44 source-preserved BRS-POS-02/-03/-09 rules are paired with positive/negative acceptance cases. `plasticos_documents_native` consumes the same rules, not a duplicate copy. Read `AGENTS.md` and applicable accepted root ADRs before any Documents code changes. Installation does not activate Odoo actions or imply runtime proof.
<!-- PLASTICOS_DOCUMENTS_BRS_NATIVE_FIRST_20261026_END -->
<!-- prettier-ignore-end -->
