---
auto_generated: false
authority: derived-index
component_id: plasticos_documents_native
component_name: Plasticos Documents — Native Bridge
module_version: 19.0.1.3.1
layer: 4
installable: true
auto_install: true
application: true
depends:
  - documents
  - documents_account
  - account
  - account_invoice_extract
  - plasticos_documents
  - plasticos_logistics
  - plasticos_transaction
  - plasticos_intake
  - plasticos_material_profile
  - plasticos_security_base
models_owned:
  - plasticos.document.sync
models_extended:
  - account.move
  - documents.document
  - plasticos.document
crons: []
---

# Plasticos Documents — Native Bridge

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` win on any conflict.

## What it does

Connects Odoo Enterprise Documents (`documents`, `documents_account`) to PlasticOS. A native document can carry plastics links and a document type, and can be associated with an exact business subject through `plasticos_documents`. Verification stays in `plasticos_documents`.

## How it works

- **Native fields.** The `documents.document` extension (`models/document_native.py`) adds `polymer_id`, `load_id`, `transaction_id`, `intake_id`, `doc_type`, and `plasticos_doc_id`, the link to the matching `plasticos.document` row. Native fields such as `attachment_id`, `folder_id`, `tag_ids`, and `partner_id` are not duplicated.
- **Native to legacy.** `plasticos.document.sync` (`models/document_sync.py`) creates or updates the `plasticos.document` row for a native document that has an attachment. Its module docstring calls native → legacy the primary direction. When the row is not yet `accepted`, it schedules one review activity for an Operations Manager (`plasticos_security_base.group_operations_manager`: the lowest-id active internal member in the document's company), not for the uploader. With no eligible manager it logs an error and posts one note on the document. `batch_sync_unlinked()` is the operator backfill for native documents that have a `doc_type` and an attachment but no link. No cron calls it.
- **Hold on arrival.** Creating a `documents.document`, or writing its `doc_type` or file, calls the same sync when a type is set and a binary file exists. It only creates or finds the pending row and the review activity. It never associates, accepts, or verifies. A failed hold is logged and does not lose the upload.
- **Reference matching.** `models/reference_match.py` reads reference numbers from the originating email's subject, its unquoted body and the file name, using patterns built from the live `ir.sequence` rows (`plasticos.transaction`, `plasticos.load`, `sale.order`, `purchase.order`, and each outgoing picking type's sequence). Tokens are matched by exact name inside the document's company. Quoted reply or forward text is read only when the fresh text carries no reference. Exactly one agreed transaction (or one matched record) pre-fills the draft subject and draft source reference on the pending row and the native form, unless the email's sender is a known partner that is not a party of it; an unknown sender is noted in the pending reason. The row stays pending. Disagreeing references are written to the pending reason and reach the manager activity. No match changes nothing.
- **Digitized vendor bills.** `models/account_move.py` adds no extraction; that is native `account_invoice_extract`. A vendor bill or refund that came from digitization or email (`extract_state` set, or `invoice_source_email`) is held in draft by `action_post` with one manager activity, and refused by `_post`, while any of these holds: digitization was requested and is unfinished or failed; no vendor; no bill reference; no bill date; lines plus tax differ from `plasticos_document_total`; that total is not recorded; a native duplicate (`duplicated_ref_ids`) with the same bill reference exists (a bill of the same vendor, amount and date with another reference is only noted on the bill, once); the references disagree; one reference resolved but the vendor is not a party of it; or the source document is empty and nothing identifies one. An emailed bill that was never sent for digitization may post on that review. The check runs on every post. `_autopost_bill` does nothing for these bills. `plasticos_document_total` is the extracted total when digitization supplies one, and an Operations Manager can correct it on the bill form.
- **Bill source document.** With exactly one resolved reference, an empty `invoice_origin`, and a vendor that is the matched record's transaction supplier or carrier, purchase order vendor, or load carrier, a draft bill gets the matched sale or purchase order name (else the transaction's order, else its number) as source document, with a note naming the token and the email. A bill with no reference cannot be told from an equipment purchase, so it is held: an Operations Manager fills the source document, or ticks `plasticos_not_load_related` with a reason. That record lifts only the missing-source-document reason and cannot be changed once the bill is posted.
- **Association.** `action_associate_exact()` builds or reuses that row and delegates the exact association to it. It does not verify and does not copy the original.
- **Verification is a projection.** The native `verified` and `override` fields are read from the linked business row, and only when the native document is a binary, not a shortcut, not under review, and its attachment has exactly that one business row. A direct write of a decision field raises `AccessError`. `action_verify()` and `action_override()` check the `plasticos_documents` user and manager groups and delegate to the legacy row. The `plasticos.document` extension invalidates the native projection when the business row changes.
- **Partner without subject.** A document with only a partner is not associated with a transaction or load.
- **Seed data.** `data/document_folders.xml` creates the PlasticOS folder tree (root, inbox, BOLs, vendor bills, scale tickets, loading pictures, customer orders, compliance). `data/document_tags.xml` seeds native tags.

## Models

| Model                     | Kind            | File                        |
| ------------------------- | --------------- | --------------------------- |
| `plasticos.document.sync` | owned, abstract | `models/document_sync.py`   |
| `documents.document`      | extended        | `models/document_native.py` |
| `account.move`            | extended        | `models/account_move.py`    |
| `plasticos.document`      | extended        | `models/document_native.py` |

## Runtime

- Requires Odoo Enterprise `documents`, `documents_account` and `account_invoice_extract` on the host.
- `installable`, `application`, and `auto_install` are true. Odoo installs it once Enterprise Documents, Documents Accounting, and the PlasticOS dependencies are installed.
- No cron.
- [`AGENTS.md`](AGENTS.md) records that installed native Documents and AI behavior is unproven. Nothing in this module's Python classifies a document by AI; the hold runs only for documents whose `doc_type` is already set.

## Boundaries

From [`AGENTS.md`](AGENTS.md):

- This bridge owns integration with native `documents.document`, `ir.attachment`, versions and shortcuts, internal Requests, folder aliases, and the read-only business evidence projection.
- Verification and compliance belong to `plasticos_documents`. Linda owns external document-chasing mail. A native auto-sort or Request fulfilment is not verified business evidence.
- No external Documents links, no duplicated originals, no finance auto-post.
- No copy of the BRS lives here. The rules are in `plasticos_documents/business_rules/`.

## Read next

- [`AGENTS.md`](AGENTS.md)
- [`models/document_sync.py`](models/document_sync.py)
- [`../plasticos_documents/README.md`](../plasticos_documents/README.md)
- [`../plasticos_documents/business_rules/README.md`](../plasticos_documents/business_rules/README.md)

<!-- prettier-ignore-start -->
<!-- PLASTICOS_DOCUMENTS_BRS_NATIVE_FIRST_20261026_BEGIN -->
## Shared module-local Documents BRS (2026-10-26)

The canonical rules live in [`plasticos_documents/business_rules/`](../plasticos_documents/business_rules/README.md). This module consumes original-file ownership, internal folder aliases/Requests, versions/shortcuts and projection boundaries. `AGENTS.md` binds the same 44 rule IDs and acceptance requirements. Native business verification remains in `plasticos_documents`, and Linda remains the sole authorized external document-reminder sender. No independent BRS copy is installed here. Installed Enterprise Documents and AI behavior is unproven, and this page does not activate Requests, mail, cron, or finance.
<!-- PLASTICOS_DOCUMENTS_BRS_NATIVE_FIRST_20261026_END -->
<!-- prettier-ignore-end -->
