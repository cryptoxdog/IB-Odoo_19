# Phase 1 Export: bounded architecture resolution candidate

**Date:** 2026-10-28  |  **Subject:** `cryptoxdog/IB-Odoo_19` `Staging@04bd0594a7c9dcad53d9c45fc65276d76817c112`
**Status:** DESIGN RESOLUTION / NOT ADMITTED / NOT IMPLEMENTED / NOT RUNTIME PROVEN.
**Decision authority:** Operator business intent is locked; technical selection is a bounded architectural recommendation awaiting source-owner adoption, validation and operator freeze.
**Read before:** Export BRS-EXP-01/02/03/08/09/10/11 and existing Logistics BRS/SUPERSESSION/NATIVE_DOCUMENTS_INTEROP, Odoo repository `INVARIANTS.md` v2.2.0.

## Decision C-01: preserve per-shipment transaction-to-load identity

**Selected smallest sufficient candidate:** Preserve the existing unique one-to-one `plasticos.transaction.load_id` link for an individual physical outbound container/load. A native SO may be referenced by many transaction records; a native supplier PO may be referenced by many transactions and separate native receipts. Never force an SO, PO, booking or shipment to be 1:1. The one-to-one transaction/load relationship is NOT the same as one-to-one order/load.

- For the example SO = 30 loads, PO = 4 loads, create four separate actual shipment/transaction/load executions with four bookings, each referring to real source lines. Do not clone PO/SO or book all 30 when one ships.
- For booking 6509024800, one reservation covers five distinct physical container/load executions, sourced from four POs. Each has independently attributable container, seal, weight, supplier, fulfillment and documents.
- A bookable ocean-carrier reservation is irreducible to a sale order or drayage load because it exists before physical allocation, can hold multiple containers from different commercial sources, and has independent carrier revisions. Therefore a narrowly scoped `plasticos.export.booking` is justified ONLY if no existing stable booking owner is confirmed in source inspection. One booking may have many load references. A load has at most one *current* applicable ocean booking; historical reassignments and all source notices persist as immutable evidence.
- Requested equipment counts are booking requirements; actual ISO container number/seal, equipment, loaded quantity and physical execution live on the existing authorized load/physical evidence paths. No duplicate container stock ledger; native stock packages remain different from ISO shipping container identities.
- Quantity allocation must bind exact PO/SO *lines* and actual per-shipment executed quantities. Use native stock.move/stock.picking lines where real; a legitimate third-party FAS/dropship movement must not invent company-owned stock. For a movement without a stock operation, explicitly attribute physical execution to its real source order line and documents, keeping invoicing and cost quantities under native owners. Do not treat a shared order reference as proof of line-level fulfilled quantity.
- Delete/disable the existing `load.create` heuristic that chooses the first transaction by `sale_order_id`; creation/binding must be exact and deterministic. Preserve historical transaction/load identities and add upgrade-safe reconciliation for existing associations, not reassign them silently.

**Rejected alternative:** Replacing `transaction.load_id` with a one-to-many purely to support many shipments per SO. It changes the meaning of a transaction and may harm existing financial/state code when a plurality of transactions per SO already expresses the example.
**Discriminator/stop:** If a single physical outbound shipment must contain multiple independently dispatched loads AND these cannot be represented through real feeder movements and one final outbound export container/load, this candidate must be revisited before code freeze. Never fake a second transaction or merge multiple moves into one falsely delivered load.

## Decision C-02: allow exact, company-scoped buyer-unassigned movements

- Buyer and SO are optional until a real sale is approved. An actual buyer-linked sale still uses full native sales guards. Purchase, inventory custody/title, and physical shipment authority are independently justified.
- `plasticos.load.company_id` SHALL have a validated, stored, explicit company identity from the real commercial/movement source; it cannot be solely `related` to `sale_order_id.company_id`. Verify cross-company equality with any linked SO, PO, picking, transaction and booking. Migrate existing sale-backed loads deterministically from their current company with an exception queue for mismatches.
- No generic deletion of the supplier/buyer guard: replace the current universal `transaction.load_id` buyer-required constraint with movement-specific eligibility. Sale-backed paths require their actual buyer/approved SO; approved supplier/owned-cargo pathways may proceed without them, subject to company, true supplier or inventory ownership, route, facility, destination, exact load identity and all applicable dispatch guards.
- A physical load may have no sales order; `load.create` must not auto-link to an arbitrary transaction by SO, and no company-less load, imaginary SO, buyer or picking is permitted. A later sale creates a true sales allocation without rewriting historical pickup, carrier, custody or scale events.
- FAS supplier-delivered cargo may involve NO Linda-booked truck. Export still tracks booking, equipment, supplier paperwork, terminal acceptance and evidence; Linda performs drayage carrier dispatch only when the company actually owns that operation.

## Decision C-03: one native original, one verification writer, one approved sender

- Native Odoo Enterprise Documents / `ir.attachment`: original bytes, versions, inbound email and document UI. Existing `plasticos.document` business classification, exact typed applicability and verified/override action are the single business authority; multiple typed associations may refer to one native original. `plasticos_documents_native` exposes a projection/delegated action and must NOT independently write `verified` or `override`. A single native document has no universally valid verified boolean when it serves several independently scoped obligations.
- Remove or constrain `_auto_link_partner`'s newest-open-transaction association. Match exact company, booking/source revision, carrier, PO/SO, container/seal/ticket when supplied, and recipient/party roles. A booking can contain several suppliers: company plus booking number alone is insufficient to assign one physical load. Ambiguous candidates remain unapplied with a review activity.
- Native AI extracts candidate facts and provenance from messages/PDFs/sheets. Deterministic owner validators can accept correctly matched, authorized low-risk booking fields; `plasticos_export` owns effective booking field changes and source-revision precedence. Documents owns evidence validity. AI may not directly write `stock`, invoice, buyer weights, `load.state`, `transaction.state`, or `verified` and must not resolve a rate/price conflict without the appropriate owner.
- Linda in Logistics is the ONE external mail sender. Its existing order issuance may send a real approved PO before a booking exists. Add a distinct booking-send obligation only at the Linda owner, with exact booking/source revision/party and recipient-scope/idempotency; separate carrier work order packet when drayage is actually company-managed. A later booking amendment must revalidate only affected pending commitments and mail. Old send outcomes/acknowledgments are retained. No second Export mail queue or Documents portal.
- Booking received != ready, supplier reported loaded != gate-in, gate-in != vessel sailed, sailing != buyer received, and none automatically implies financial posting.

## Decision C-04: constitution and admission split

- Current repository constitutional authority is `INVARIANTS.md` v2.2.0 at the inspected Staging revision. The user-supplied `v3.0.0 DRAFT r3` and pack `v3.1.0 DRAFT r1` remain candidates. `POS-INV-21..23` clarify the product semantics without having authority to override v2.2.0. `BAN001` remains binding without waiver.
- Do NOT block Export's conceptual architecture on unrelated constitutional reform: obey v2.2.0's stricter existing enforcement for seed data, ACL/record rules, and graph failure handling while reconciling the future v3.x admission separately. No new export model is exempt from existing module names, manifest, access rules, XML/registry and Enterprise install requirements.
- A product-local architectural conclusion is not constitutional admission, independent semantic compiler proof, Enterprise runtime acceptance or production activation. Owner BRSs and accepted ADRs must approve any changed effective rule. No implementation or PR is authorized by this document.

## Placement and dependencies

| Fact or operation | Owner | Consumer |
| --- | --- | --- |
| PO/SO and order line quantity | Native Purchase/Sales | Transaction, Export, Logistics views |
| Actual quantity, custody and pickings where applicable | Native Odoo Stock | Transaction, export fulfillment report |
| Business shipment / commercial execution record | Existing PlasticOS Transaction | Export view and exact load relation |
| One physical load, carrier rate, dispatch, destination and checkpoint | PlasticOS Logistics / Linda | Export readiness projection |
| Ocean reservation, source schedule revisions, equipment count | Thin `plasticos_export` | Logistics feasibility and reports |
| Original file / inbound mail | Native Odoo Documents / Mail | PlasticOS Documents, Export, Linda |
| Typed evidence, verification and document compliance | PlasticOS Documents | Export, Logistics and transaction guards |
| External supplier/carrier communications | Logistics/Linda via native Odoo Mail | Export displays current send evidence |
| Invoice, actual costs, settlement, credit | Native Accounting | Commercial profitability / report projection |

## Four phase-1 convergence conditions

1. **Cardinality:** One SO/PO many independent transactions; one booking many loads; per-load exact source-line quantity and no accidental shared-order auto-link.
2. **Buyer optional:** Company identity and dispatch authorization have a non-SO source without relaxing sale-specific protections.
3. **Documents/Linda:** Unique evidence writer and external sender; deterministic exact matching, scoped verification, guarded state transitions, change-specific invalidation.
4. **Constitution:** v2.2.0 remains effective, v3.1 candidate not represented as admitted, and exact owner corrections accepted under current applicable ADR/BRS before freezing code scope.

**Disposition:** Architectural resolution candidate selected. User-confirmed business semantics retained. Formal GAR/L9 convergence, independent architectural break-test acceptance, target-owner BRS admission, Enterprise registry proof, code freeze and implementation readiness are NOT ESTABLISHED in this working artifact.
