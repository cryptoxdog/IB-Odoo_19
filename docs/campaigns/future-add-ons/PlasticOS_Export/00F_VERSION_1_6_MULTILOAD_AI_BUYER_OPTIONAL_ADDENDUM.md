# RecycleOS v1.6: multi-load export, in-transit sale and native AI booking update

**Status:** Working design/update to the accumulated pack; no repository, PR or live change.
**Authoritative rules:** `EXPORT_BRS/RULES/BRS-EXP-01..10.md`, with current rule registry and all acceptance NOT_RUN.
**Supersession scope:** `EXPORT_BRS/SUPERSESSION_v1_2.md`. All older RecycleOS expansion files remain as historical snapshots; wherever they imply universal buyer-required or PO-only operations, the v1.6 addendum and revised BRS govern. No unrelated commitments have changed.

## Operator-established business facts

- 30-load customer PO represented by **one native Sales Order** for MRP material; supplies from one or more vendor POs.
- Waste Management Charleston example: **one native Purchase Order for four loads**, supplier makes one load ready weekly, each ships against its **own Booking No.**. One supplier PO stays open with partial receipts/remaining quantities.
- Export material and valid dispatch can exist **before a buyer is assigned**, and cargo can be legitimately **sold when already on the water**. Sales-linked shipments retain genuine buyer; buyer is never physical terminal destination by implication.
- A booking is not a stock package, carrier drayage commitment, truck load or commercial order. Multiple containers can share a booking; one SO/PO can span many bookings.
- Odoo 19 **native AI Documents** must be used where verified available for booking extraction and exact linkage. Ambiguous association is review-required. Only authorized state owner actions can change transaction, freight, stock or invoice state.

## Distribution of responsibilities

Export: six booking fields, booking/container requirements, source revisions, applicability, linking, simple views/QWeb and document/operational status projections.
Documents: original bytes, metadata, version, exact evidence association, verification and document AI intake.
Logistics/Linda: movement type eligibility, carrier, rate, scheduling, sending, drayage work order, terminal delivery checkpoints.
Native Odoo: PO/SO quantities, partial stock receipts/deliveries/backorders, invoices, and custody.

## Change impact

Eight revised Export BRS rules; twenty-four added BRS-EXP-08 through BRS-EXP-10 rules, total **66**. Scoped proposals are maintained in the new `EXPORT_BRS/INTEROP/TARGET_OWNER_BRS_AMENDMENTS.md`; **the separate canonical native/Logistics BRS were NOT rewritten**.

**Proof:** ZIP hash/structural checks only; actual Odoo 19 AI extraction, end-to-end order fulfillment, and all BRS acceptance are NOT_RUN.
