# BRS integration without ownership drift

## Accepted source inventory / statuses

1. In `Staging@04bd0594...`, `plasticos_logistics/business_rules/` contains the 60-rule Linda source/effective rule concern, seven preserved BRS chapters, narrow `SUPERSESSION.md` and Documents interop. Requirement presence does **not** prove live behavior.
2. `plasticos_documents/business_rules/` is the single local home for 44 Documents-owned BRS-POS rules, in chapters 02/03/09, and cross-domain references to 126 non-owned BRS-POS rules. `plasticos_documents_native` is a **consumer**, not a second BRS publisher.
3. Uploaded donor's **Export BRS v1.6.0** contains **111 stable BRS-EXP IDs** and **111 NOT_RUN acceptance cases**. They remain private **future design**, not admitted repository work or urgent backlog. Keep their IDs, histories, acceptance and original source provenance in donor pack; integrate meaning via narrow owner-level proposals below only. Do **not** ship private source originals into Odoo.

## One owner per fact

| Concern | Existing owner | Planning action (no implementation) |
|---|---|---|
| Original bytes, version, folder, alias, internal native Requests | Enterprise native Documents + `ir.attachment` via `plasticos_documents_native` | Prove real installed API, entitlement and access; no second file store or external share |
| Exact source association, verified document evidence, override, operation-specific compliance | `plasticos_documents` | Proposed BRS-POS-02/-03/-09 clarification; one verifier; candidate-vs-verified separation; per-PO/picking and multiple real links |
| Supplier readiness, carrier ACK, party-appropriate outbound, rate, transport planning | `plasticos_logistics` Linda with native Mail | Proposed BRS-01/02/05/07 crosswalk; one sender/retry; no Export second sender |
| Commercial order lifecycles and quantities | Native Purchase/Sales; transaction policy owns its domain bridge | Keep independent PO/SO and authorized native confirmation; don't manufacture order counterpart |
| Custody, inventory, receipt, shipping and partial delivery | Native Stock/Inventory; MRP only when admitted | Do not infer physical events from mail/docs/QR; eventual per-movement allocation design, not current work |
| Invoices, claims' economic recognition, credit/debit, settlement | Native Accounting + existing authorized settlement writer | Documents provides evidence, never auto-post; cutover decision independent |
| Parsing/classification and field extraction | Native Odoo Documents AI or deterministic extractor when eligible | Typed, revision-bound candidates only; business owner validates all consequential changes |
| Matching/scoring/inference intelligence | EIE/CEG behind Gate + Gate_SDK | No direct worker calls or shadow engine in Export or Documents |
| Booking-specific fields, optional export views/reports, applicability context | Future thin `plasticos_export` | Park BRS-EXP-01..14; add no model/job/report now |

## Proposed narrow BRS amendments, not competing source copies

- Documents BRS-POS-02/03: assert `one original -> many exact typed evidence associations`; identify authorizing document verification writer; candidate match status not verified; PO-only must link native PO/picking without fictional load. The current native bridge has independent `verified`/`action_verify` and partner-recency `_auto_link_partner`; document *owners* must resolve before future use.
- Documents BRS-POS-09: native internal Requests and Activities stay internal; Linda remains the sole external chaser. AI extraction does not authorize invoice/stock state updates.
- Linda BRS-01/02: PO-only and SO-only independently valid; distinguish supplier READY and accepted current booking/candidate; inbound reply binds exact request/party/revision, no sole From-address authority.
- Linda BRS-03/04: future carrier planning consumes exact current cutoff/ERD equipment, location, timezone and revision, with supplier-delivered shipment not presumed to require broker-paid carrier booking.
- Linda BRS-05: separately issued PO and later booking have distinct authorized issuance obligations. Order reissue and booking revisions never auto-resend each other. Linda owns recipient/packet/retry and party privacy; current domestic sends unaffected.
- Linda BRS-06/07: real partial movement milestones and per-quantity receiving/closeout. Never infer downstream completed voyages from supplier booking email; no automatic accounting chargeback.
- Future Export BRS-EXP-01..14: retain 111 candidate source rules and falsifying cases. Only reopen their chapter/owner mappings when a separate Export planning/implementation decision is issued. Native Odoo QWeb, pivots and reports stay preferred; no duplicate finance/report engine.

## Specific source-observed deferrals, NOT change requests

- `plasticos_documents/models/document.py`: one business `verified` writer today and compliance/expiry logic; investigate independent native `documents.document` verification in `plasticos_documents_native/models/document_native.py` before any merge, not via Export.
- `plasticos_documents_native/models/document_native.py::_auto_link_partner`: newest open transaction for partner; currently unsuitable for exact booking/PO attribution; mark a future safety remediation independently of Export, with business-owner review.
- `plasticos_logistics/models/transaction_inherit.py`: singular `transaction.load_id` plus buyer constraint. `plasticos_logistics/models/load.py`: company derives from SO. Future buyerless partial movement cannot simply repurpose these without a design/migration contract. Do not remove existing guards in this planning exercise.
- `plasticos_documents/models/document_rule.py` and `document_validation_matrix.py`: current applicability schema is not proven adequate for exact operation, load quantity, revision or booking. Source-analyze before any future generalized amendment.

**Negative controls:** A booking can arrive weeks after the approved PO; one PO can serve multiple releases; one booking can serve several supplier orders; one PDF can prove one covered movement but not all movements; one late schedule update may affect only a subset; AI suggestions and native Requests must not send, post, verify, dispatch or invent a buyer.
