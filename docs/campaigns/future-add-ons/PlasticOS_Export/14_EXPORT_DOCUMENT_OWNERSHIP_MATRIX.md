# PlasticOS Export: document ownership matrix

**Status:** locked product boundary, advisory implementation placement. **No code or PR authorized.** The existing Native-First BRS remains independently frozen/unadmitted.

| Fact / action | Sole authoritative owner | Export's allowed role | Forbidden duplicate |
| --- | --- | --- | --- |
| Original document bytes and versions | Native Odoo Documents / `ir.attachment`, conditional on installed capability | Display exact native original; link shipment | Export binary store or copied originals |
| Native inbox, alias, file organization, internal Requests | Native Documents and native Mail | Contextual link to inbox/request | Export upload portal, independent inbox or external Documents share |
| Business evidence type, party category and exact typed links | `plasticos_documents` | Specify export context and proposed link target; use approved typed association interface | Export-owned generic tag taxonomy or fuzzy attachment matching |
| Authoritative `verified`, `verified_by`, `verified_at`, override | `plasticos_documents` business verifier | Read status; request proper verification operation by authorized actor | Independent `verified` flag or direct write from export / native projection |
| Evidence validity, version, expiration and operation-scoped completeness | `plasticos_documents` compliance owner | Ask whether exact shipment/operation obligations are satisfied; show missing items | Second compliance verdict / blanket `all_docs_complete` flag |
| Export-specific document requirements and when they apply | `plasticos_export` shipment/booking context, *using* shared Docs validation | Declare applicable requirement/profile by phase, deal, destination, source and current operation; reuse shared verification | Generic Documents knows ocean-business lifecycle; export reimplements Docs validation |
| Booking No., Steamship Line, POL, POD, Cut Off, ERD | Existing validated native/PlasticOS owner if found, else minimal `plasticos_export` linkage | Preserve exact source, revision, timezone and event meaning | Duplicate source fields or overwrite revisions |
| Production of export-specific QWeb layout (booking sheet, packing manifest, shipping instructions) | `plasticos_export` template on native Odoo reporting | Render from existing authoritative data, with approved audience | New PDF engine, invented cargo count or shipment facts |
| PO/SO and commercial invoice data/approval | Native Odoo Sales/Purchase/Accounting | Reference and include permitted information in derived documents | Draft bypass, export-created accounting ledger or auto posting |
| Physical cargo and package scans, stock quantities, container links | Native Odoo Stock/Packages and existing Logistics | Read linked current physical records, show shipment view | Independent container-package inventory ledger |
| Transport load, freight award, rates, physical dispatch, BOL coordination | `plasticos_logistics` / Linda and native Odoo | Display, link, collect export-specific source requirements | Export transport state engine, carrier scheduler, invented dispatch |
| Outgoing physical-operation emails, carrier/forwarder correspondence, replies, reminders | Existing designated `plasticos_logistics` / Linda operation owner via native Odoo Mail | Prepare exact current export report and request authorized single send | Separate export email queue, timer, retry, sender or sender race |
| Internal unresolved exception/next action | Native `mail.activity` and where applicable native Documents Request | Show one shared current activity tied to exact obligation | Export task platform or repeated duplicate activity |
| Money, weight settlement, taxes and payments | Native Odoo Accounting + current PlasticOS weight/contract policy | Present documentary evidence; no consequential money write | Verification auto-post, scale overwrite of contractual AP/AR |
| External regulatory filing, ocean carrier B/L issuance | Designated authorized filer/carrier | Phase 2 records verified issued evidence and status | Export fabricates acceptance/filing, claims to issue carrier B/L |

## Suggested minimal UI (not extra business authority)

- **Export booking/shipment view:** existing relevant order/load/container links and six critical booking fields, with source version and responsible parties.
- **Documents tab:** filtered projection of the existing native originals and `plasticos_documents` evidence state, per exact booking/shipment. Current, missing, pending, superseded and exception are derived, not newly authoritative statuses.
- **Dates and exceptions view:** ERD and Cut Off with distinct source/revision/precision and validated responsible party; use native Odoo activity/calendar primitives where available.
- **Reports:** native Odoo QWeb templates for booking/dispatch reference and packing source; Phase 2 adds the appropriate shipping-instructions/report variants; no second report engine.

## Practical guardrails

Do not confuse a document sent with a document received, an uploaded original with verified evidence, a verified document with stock receipt, or verified receipt with accounting posting. Phase-specific applicability may vary by sales agreement; do not hard-code one worldwide checklist. The company and recipient audience are mandatory boundaries. The native Enterprise Document functionality and exact integrations remain **NOT_RUN** until verified on the installed Odoo deployment.
