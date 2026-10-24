# Linda Logistics BRS supersession register

**Effective upon registration:** 2026-10-23. **Source:** explicit operator corrections in the October 23 conversation and the corrected Linda build plan; no claim of implementation or deployment.

These are **narrow amendments**, not edits to the preserved source BRS documents. The operator-directed alignment is implemented in module plan `../LINDA_BUILD_PLAN.md`; the full 60-rule/acceptance crosswalk is there, not in a competing requirements registry. A source heading that says `Candidate` remains untouched by design. All other BRS rules remain requirements.

## Governing interpretations

The physical movement can be one of four legitimate patterns: (1) PO-first pending SO, (2) SO-first pending PO, (3) PO to inventory/warehouse with no current SO, or (4) SO fulfilled from existing inventory without a new PO. Independently eligible purchase and sale orders can be issued and tracked before they match. A missing counterpart is ordinary timing, not a human-approval exception. Native commercial controls stay intact. Never create a fictitious order or company-less load to satisfy the old paired-order assumption.

| Rule ID | Current interpretation |
| --- | --- |
| `BRS-01-R001` | **Creation and issuance are separate**: Linda may resolve/create a native PO or SO only from a specific, complete, source-authorized commercial instruction through its pre-existing Odoo commercial owner, and never invents price, quantity, terms, counterpart or company. Order creation/draft alone cannot send externally. A separate legitimate native live confirmed-state release makes each order independently eligible for supplier/buyer issue, without matching counterpart, fabricated transaction/load or additional Linda-only approval. |
| `BRS-01-R002` | PO-only requests may be identified by company and exact PO without a load or transaction; SO-only requests may be identified by company and exact SO. Physical-movement commands require exact movement/facility identity before acting. |
| `BRS-01-R065` | The Approved-like **external issuance event is per native order**, not an assumed two-sided transaction event. Before creating an order, require a verifiable already-authorized source with complete material, commercial terms, company, counterparty and applicable onboarding/approval checks; otherwise **creation is blocked as an evidence gap**, not performed speculatively. Native live confirmation/approval alone governs issue after creation. |
| `BRS-02-R004` | For an **SO fulfilled from owned inventory**, native stock reservation proves supply but **not physical shipper READY**. The actual warehouse/pickup-site custodian is the shipper for that outbound load and must provide attributable current cargo/material/quantity readiness and available interval at the exact pickup site before physical dispatch. A non-existent supplier PO/confirmation is never created. For real third-party pickup, the real supplier's attributed READY remains required. |
| `BRS-02-R010` | Typed request evidence is order-scoped before a transaction/load exists; require a company and an exact native source order for PO-only or SO-only actions. Load-scoped requests continue to require load identity. **Source-authorized creation evidence** is distinct from a `po_issue`/`so_issue` external-send obligation; only the latter arises after native commercial release. |
| `BRS-02-R011` | PO-only supplier answers may be attributed against PO-scoped requests without fabricating a load/transaction; movement-specific readiness and dispatch still require the proper movement identity. |
| `BRS-02-R013` | Idempotency identity follows the actual action owner and revision: PO, SO, or load as applicable, not a mandatory company/load key for a PO-only request. |
| `BRS-02-R015` | Linda may **resolve/create** complete native commercial orders only through existing Odoo commercial ownership after source authorization is independently proven, and later issue/communicate each order on its **own valid native release**. This is not permission to derive a PO merely from a SO, select price/carrier/supplier, bypass native commercial checks, or mint speculative business facts. The WP00 source-binding gap blocks only creation if unresolved. Ordinary authorized coordination never needs another Linda approval. |
| `BRS-05-R029` | **Canonical load checks protect physical load dispatch, carrier packet release and physical load-state transitions**, including all direct/cron/wizard paths. Independent native PO/SO **commercial order emails** may occur before a load exists and instead require strict **order-scoped** release, company, recipient, revision and mail guards. Stock `assigned` alone never permits dispatch; this does not weaken the real physical-load guard. |
| `BRS-07-R047` | For **PO-only warehouse inbound**, bind authenticated incoming documents to **company + exact PO + request/message**. Classify/verify actual receipt only after linking the **correct incoming `stock.picking`, warehouse and movement** with matching company. If picking is absent, retain the PO-scoped document without falsely marking it received; ambiguous multiple pickings require clarification/review. For **SO-backed outbound**, continue requiring exact load association. No fake load, fuzzy PO/domain match, duplicated original document, or hash-only verification. |
| `BRS-06-R040` | An exception may be scoped to PO/SO while no physical load exists. A load/milestone key is required only when the exception concerns an actual load. |

## Binding source schedules (restatement, not supersession)

The following **existing BRS text is preserved**, not revised. Implement WP03/WP06/WP07/WP08 exactly as mapped in `../LINDA_BUILD_PLAN.md` section 6b and its 60-rule table:

- `BRS-02-R007`: not physically READY -> **one status request Monday morning in supplier-local time**, PO number and shipper, stop on READY/cancel/supersede. Exact hour remains runtime configuration within morning.
- `BRS-06-R039`: separate **supplier confirmation after 24h**, at most one/day, **three unanswered** follow-ups before escalation; separate buyer slot **24h/48h** thresholds; carrier packet ACK **T+2h reminder/T+4h carrier+ops escalation**; still-unacknowledged broker-facing **D-1 09:00 and D 08:00** origin-local; separate **ops-only D-1 13:00 and D 07:00** origin-local; broker-local routine **22:00–06:00 quiet hours**, not a silence requirement for urgent internal exceptions.
- `BRS-07-R051`: Monday–Friday business-day missing-document checks/escalations **supplier +1/+5 after pickup**, **carrier +2/+6 after pickup**, **buyer +1/+5 after delivery**; after due, at most one reminder per party per day, correct missing types/references, single native internal escalation activity to correct owner; stop on cleared/inapplicable/canceled/superseded. No new SMS or `docs@` transport.

These deadlines are business requirements, **not optional example configuration**. Existing Odoo scheduler/job/provider wiring and exact source-local time handling must still be evidenced in WP00; do not claim runtime conformance until cases are executed.

## Additional current operating limits

- Native PO/SO authorization remains required; there is **no blanket per-order Linda approval** and no bypass of native commercial policy.
- `plasticos.transaction.pending_supplier` applies only after actual fulfillment-route prerequisites for that transaction are proven. There is no `all([]) == true` vacuous handoff; for PO-only the supplier follow-up can live on the purchase order itself without a transaction/load.
- PO-only warehouse inventory uses Odoo purchase/receipt (`stock.picking`) evidence; a sale-order-backed `plasticos.load` must not be created without a real SO since `company_id` is derived from it in the inspected baseline.
- An SO can be issued before supply exists, but cannot be physically dispatched until procurement or reserved existing inventory proves supply.
- Supplier/counterparty contacts, freight rate awards, double-blind documents, physical evidence, idempotent outbound mail, and company isolation remain governed by their original relevant BRS rules.
- `BRS-02-R062` remains **deferred** for optional free-form LLM extraction under decision D-05: deterministic reply validation and automatic clarification are the implemented-plan path. Deferral does not erase the candidate clause.
- Unknown native Odoo/transport capabilities remain implementation facts for WP00, not permissions to invent a new approval engine or new transaction type.

## Change control

Amend this register only for an explicit operator decision or an admitted repository architectural ruling, cite exact BRS IDs, update any associated acceptance tests, and preserve source document bytes. In-scope rule proposals that are unresolved must be marked **proposed**, not disguised as accepted.
